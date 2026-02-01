"""Extract Service routes.

POST /api/v1/extract-service - Extract values using the Extract Service.
Uses native PDF text extraction, OCR, and LLM for value extraction.

This is the new Clean Architecture implementation that uses:
- NativeTextExtractorPort for PDF text extraction
- OcrServicePort for OCR processing
- ValueExtractionAgentPort for LLM assistance
"""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.models import ApiResponse
from app.models.common import BBox
from app.models.extract import (
    ExtractField,
    ExtractRequest,
    ExtractResult,
    PageArtifact,
)
from app.services.extract.adapters import PaddleOcrAdapter, PdfPlumberTextAdapter
from app.agents.extract import LangChainValueExtractionAgent
from app.services.extract.service import ExtractService

router = APIRouter(tags=["extract-service"])


# Request/Response DTOs for the API
from pydantic import BaseModel, Field as PydanticField


class ExtractFieldInput(BaseModel):
    """Input field definition for extraction."""

    field_id: str = PydanticField(..., description="Unique field identifier")
    name: str = PydanticField(..., description="Field name/label")
    field_type: str = PydanticField(
        default="text",
        description="Expected type (text, number, date, checkbox)",
    )
    page: int = PydanticField(..., ge=1, description="Page number")
    bbox: list[float] | None = PydanticField(
        None,
        min_length=4,
        max_length=5,
        description="Bounding box [x, y, width, height, page] or [x, y, width, height]",
    )
    validation_pattern: str | None = PydanticField(
        None, description="Regex pattern for validation"
    )

    model_config = {"frozen": True}


class PageArtifactInput(BaseModel):
    """Input page artifact for OCR."""

    page: int = PydanticField(..., ge=1, description="Page number")
    image_ref: str = PydanticField(..., description="Storage reference to page image")
    width: int = PydanticField(..., gt=0, description="Image width in pixels")
    height: int = PydanticField(..., gt=0, description="Image height in pixels")

    model_config = {"frozen": True}


class ExtractServiceRequest(BaseModel):
    """Request body for POST /api/v1/extract-service."""

    document_ref: str = PydanticField(
        ..., description="Reference/path to the document"
    )
    fields: list[ExtractFieldInput] = PydanticField(
        ..., min_length=1, description="Fields to extract"
    )
    artifacts: list[PageArtifactInput] | None = PydanticField(
        None, description="Rendered page images for OCR"
    )
    user_rules: dict[str, Any] | None = PydanticField(
        None, description="User-defined extraction rules"
    )
    use_ocr: bool = PydanticField(
        default=True, description="Whether to use OCR"
    )
    use_llm: bool = PydanticField(
        default=True, description="Whether to use LLM for ambiguity resolution"
    )
    confidence_threshold: float = PydanticField(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-accept",
    )

    model_config = {"frozen": True}


class EvidenceOutput(BaseModel):
    """Evidence output in API response."""

    id: str = PydanticField(..., description="Evidence ID")
    kind: str = PydanticField(..., description="Evidence kind")
    page: int = PydanticField(..., description="Page number")
    bbox: list[float] | None = PydanticField(None, description="Bounding box")
    text: str | None = PydanticField(None, description="Source text")
    confidence: float = PydanticField(..., description="Confidence score")

    model_config = {"frozen": True}


class ExtractionOutput(BaseModel):
    """Extraction output in API response."""

    field_id: str = PydanticField(..., description="Field identifier")
    value: str = PydanticField(..., description="Extracted value")
    normalized_value: str | None = PydanticField(
        None, description="Normalized value"
    )
    confidence: float = PydanticField(..., description="Confidence score")
    source: str = PydanticField(..., description="Source of extraction")
    evidence: list[EvidenceOutput] = PydanticField(
        default_factory=list, description="Supporting evidence"
    )
    needs_review: bool = PydanticField(
        default=False, description="Whether review is needed"
    )
    conflict_detected: bool = PydanticField(
        default=False, description="Whether conflicts were detected"
    )

    model_config = {"frozen": True}


class OcrRequestOutput(BaseModel):
    """OCR request output in API response."""

    field_id: str = PydanticField(..., description="Field ID")
    page: int = PydanticField(..., description="Page number")
    bbox: list[float] = PydanticField(..., description="Region to OCR")
    reason: str = PydanticField(..., description="Reason OCR is needed")

    model_config = {"frozen": True}


class FollowupQuestionOutput(BaseModel):
    """Followup question output in API response."""

    field_id: str = PydanticField(..., description="Field ID")
    question: str = PydanticField(..., description="Question text")
    candidates: list[str] = PydanticField(
        default_factory=list, description="Possible answers"
    )
    reason: str = PydanticField(..., description="Reason for question")

    model_config = {"frozen": True}


class ExtractErrorOutput(BaseModel):
    """Error output in API response."""

    field_id: str = PydanticField(..., description="Field ID")
    code: str = PydanticField(..., description="Error code")
    message: str = PydanticField(..., description="Error message")

    model_config = {"frozen": True}


class ExtractServiceResponse(BaseModel):
    """Response body for POST /api/v1/extract-service."""

    document_ref: str = PydanticField(..., description="Document reference")
    success: bool = PydanticField(..., description="Whether extraction completed")
    extractions: list[ExtractionOutput] = PydanticField(
        default_factory=list, description="Extracted values"
    )
    evidence: list[EvidenceOutput] = PydanticField(
        default_factory=list, description="All evidence"
    )
    ocr_requests: list[OcrRequestOutput] = PydanticField(
        default_factory=list, description="OCR requests"
    )
    followup_questions: list[FollowupQuestionOutput] = PydanticField(
        default_factory=list, description="Questions for user"
    )
    errors: list[ExtractErrorOutput] = PydanticField(
        default_factory=list, description="Extraction errors"
    )

    model_config = {"frozen": True}


def _convert_to_bbox(bbox_list: list[float] | None, page: int) -> BBox | None:
    """Convert bbox list to BBox model."""
    if bbox_list is None:
        return None
    if len(bbox_list) == 4:
        return BBox(
            x=bbox_list[0],
            y=bbox_list[1],
            width=bbox_list[2],
            height=bbox_list[3],
            page=page,
        )
    elif len(bbox_list) == 5:
        return BBox(
            x=bbox_list[0],
            y=bbox_list[1],
            width=bbox_list[2],
            height=bbox_list[3],
            page=int(bbox_list[4]),
        )
    return None


def _bbox_to_list(bbox: BBox | None) -> list[float] | None:
    """Convert BBox model to list."""
    if bbox is None:
        return None
    return [bbox.x, bbox.y, bbox.width, bbox.height]


@router.post(
    "/extract-service",
    response_model=ApiResponse[ExtractServiceResponse],
    status_code=status.HTTP_200_OK,
    summary="Extract values using Extract Service",
    description="""
Extract values from a document using the Extract Service.

The extraction pipeline follows these steps:
1. Try native PDF text extraction (fastest, highest confidence)
2. If insufficient: Run OCR on field region
3. If ambiguous: Use LLM for resolution/normalization

LLM is used for:
- Ambiguity resolution (multiple candidates)
- Value normalization (dates, addresses, names)
- Conflict detection
- Question generation for missing fields

Note: This is a stub implementation. Full implementation requires:
- PDF library (pdfplumber/PyMuPDF)
- OCR engine (PaddleOCR/Tesseract)
- LLM (OpenAI/Claude via LangChain)
""",
)
async def extract_values_service(
    request: ExtractServiceRequest,
) -> ApiResponse[ExtractServiceResponse]:
    """Extract values from document using the Extract Service.

    Args:
        request: Extraction request with document and field definitions

    Returns:
        Extraction result with values, evidence, and any issues

    Raises:
        HTTPException: If extraction fails
    """
    # Convert input DTOs to domain models
    fields = tuple(
        ExtractField(
            field_id=f.field_id,
            name=f.name,
            field_type=f.field_type,
            page=f.page,
            bbox=_convert_to_bbox(f.bbox, f.page),
            validation_pattern=f.validation_pattern,
        )
        for f in request.fields
    )

    artifacts = tuple(
        PageArtifact(
            page=a.page,
            image_ref=a.image_ref,
            width=a.width,
            height=a.height,
        )
        for a in (request.artifacts or [])
    )

    extract_request = ExtractRequest(
        document_ref=request.document_ref,
        fields=fields,
        artifacts=artifacts,
        user_rules=request.user_rules,
        use_ocr=request.use_ocr,
        use_llm=request.use_llm,
        confidence_threshold=request.confidence_threshold,
    )

    # Create service with adapters
    # NOTE: In production, these would be injected via dependency injection
    native_extractor = PdfPlumberTextAdapter()
    ocr_service = PaddleOcrAdapter()
    extraction_agent = LangChainValueExtractionAgent()

    service = ExtractService(
        native_extractor=native_extractor,
        ocr_service=ocr_service,
        extraction_agent=extraction_agent,
    )

    try:
        result = await service.extract(extract_request)
    except NotImplementedError as e:
        # Return stub response indicating implementation is pending
        return ApiResponse(
            success=True,
            data=ExtractServiceResponse(
                document_ref=request.document_ref,
                success=False,
                extractions=[],
                evidence=[],
                ocr_requests=[],
                followup_questions=[],
                errors=[
                    ExtractErrorOutput(
                        field_id="*",
                        code="NOT_IMPLEMENTED",
                        message=f"Service not fully implemented: {str(e)}",
                    )
                ],
            ),
            meta={
                "stub": True,
                "message": "Extract service adapters are stub implementations",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )

    # Convert result to response DTOs
    extractions = [
        ExtractionOutput(
            field_id=ex.field_id,
            value=ex.value,
            normalized_value=ex.normalized_value,
            confidence=ex.confidence,
            source=ex.source.value,
            evidence=[
                EvidenceOutput(
                    id=ev.id,
                    kind=ev.kind.value,
                    page=ev.page,
                    bbox=_bbox_to_list(ev.bbox),
                    text=ev.text,
                    confidence=ev.confidence,
                )
                for ev in ex.evidence
            ],
            needs_review=ex.needs_review,
            conflict_detected=ex.conflict_detected,
        )
        for ex in result.extractions
    ]

    evidence = [
        EvidenceOutput(
            id=ev.id,
            kind=ev.kind.value,
            page=ev.page,
            bbox=_bbox_to_list(ev.bbox),
            text=ev.text,
            confidence=ev.confidence,
        )
        for ev in result.evidence
    ]

    ocr_requests = [
        OcrRequestOutput(
            field_id=ocr.field_id,
            page=ocr.page,
            bbox=_bbox_to_list(ocr.bbox) or [],
            reason=ocr.reason,
        )
        for ocr in result.ocr_requests
    ]

    followup_questions = [
        FollowupQuestionOutput(
            field_id=q.field_id,
            question=q.question,
            candidates=list(q.candidates),
            reason=q.reason,
        )
        for q in result.followup_questions
    ]

    errors = [
        ExtractErrorOutput(
            field_id=err.field_id,
            code=err.code.value,
            message=err.message,
        )
        for err in result.errors
    ]

    response = ExtractServiceResponse(
        document_ref=result.document_ref,
        success=result.success,
        extractions=extractions,
        evidence=evidence,
        ocr_requests=ocr_requests,
        followup_questions=followup_questions,
        errors=errors,
    )

    return ApiResponse(
        success=True,
        data=response,
        meta={
            "total_fields": len(request.fields),
            "extracted_count": len(extractions),
            "error_count": len(errors),
        },
    )
