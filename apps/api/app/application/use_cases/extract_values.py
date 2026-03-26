"""Extract Values Use Case.

This use case handles value extraction from source documents:
- Extract values from PDF native text
- Use OCR when native text is insufficient
- Use LLM for ambiguity resolution and normalization
"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.application.ports.llm_gateway import (
    AmbiguityResolutionResult,
    EvidenceRef,
    FieldContext,
    LLMGateway,
)
from app.application.ports.llm_gateway import (
    OCRToken as LLMOCRToken,
)
from app.application.ports.ocr_gateway import OCRGateway, OCRResult


class ExtractionTarget(BaseModel):
    """A field to extract a value for."""

    field_id: str = Field(..., description="Field ID")
    field_name: str = Field(..., description="Field name/label")
    field_type: str = Field(..., description="Field type")
    page: int = Field(..., ge=1, description="Page number")
    bbox: tuple[float, float, float, float] = Field(..., description="Field bounding box")
    expected_format: str | None = Field(None, description="Expected value format")
    validation_rules: dict[str, str] | None = Field(None, description="Validation rules")

    model_config = {"frozen": True}


class ExtractRequest(BaseModel):
    """Request to extract values."""

    job_id: str = Field(..., description="Job ID")
    document_id: str = Field(..., description="Source document ID")
    document_ref: str = Field(..., description="Reference to source document")
    page_image_refs: dict[int, str] = Field(
        ..., description="Map of page number to image reference"
    )
    targets: list[ExtractionTarget] = Field(..., description="Fields to extract values for")
    native_text: dict[int, str] | None = Field(
        None, description="Optional pre-extracted native PDF text per page"
    )
    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence for auto-accept"
    )

    model_config = {"frozen": True}


class ExtractedValue(BaseModel):
    """An extracted value for a field."""

    field_id: str = Field(..., description="Field ID")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source: str = Field(..., description="Source of extraction (native_text, ocr, llm)")
    evidence: list[EvidenceRef] = Field(default_factory=list, description="Supporting evidence")
    needs_review: bool = Field(default=False, description="Whether manual review is needed")
    normalized: bool = Field(default=False, description="Whether value was normalized")

    model_config = {"frozen": True}


class ExtractResult(BaseModel):
    """Result of value extraction."""

    job_id: str = Field(..., description="Job ID")
    document_id: str = Field(..., description="Source document ID")
    extractions: list[ExtractedValue] = Field(default_factory=list, description="Extracted values")
    failed_fields: list[str] = Field(
        default_factory=list, description="Field IDs that failed extraction"
    )
    success: bool = Field(..., description="Whether extraction succeeded")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")

    model_config = {"frozen": True}


@dataclass(frozen=True)
class ExtractValuesUseCase:
    """Use case for extracting values from source documents.

    Extraction Pipeline (following PRD):
    1. Try native PDF text extraction
    2. If missing/low-confidence: Run OCR on field region
    3. If still ambiguous: Use LLM for resolution/normalization
    4. Compute confidence and mark for review if needed

    LLM is used for:
    - Ambiguity resolution (multiple candidates)
    - Value normalization (dates, addresses, names)
    - Conflict detection
    - Question generation for missing fields
    """

    llm_gateway: LLMGateway
    ocr_gateway: OCRGateway

    async def execute(
        self,
        request: ExtractRequest,
    ) -> ExtractResult:
        """Execute value extraction.

        Args:
            request: Extraction request with targets and document refs

        Returns:
            Extraction result with values and confidence scores
        """
        extractions: list[ExtractedValue] = []
        failed_fields: list[str] = []
        errors: list[str] = []

        for target in request.targets:
            try:
                extraction = await self._extract_field(request, target)
                extractions.append(extraction)
            except Exception as e:
                failed_fields.append(target.field_id)
                errors.append(f"Field {target.field_id}: {str(e)}")

        return ExtractResult(
            job_id=request.job_id,
            document_id=request.document_id,
            extractions=extractions,
            failed_fields=failed_fields,
            success=len(errors) == 0,
            errors=errors,
        )

    async def _extract_field(
        self,
        request: ExtractRequest,
        target: ExtractionTarget,
    ) -> ExtractedValue:
        """Extract value for a single field.

        Follows the extraction pipeline:
        1. Native text -> 2. OCR -> 3. LLM (if ambiguous)
        """
        # Step 1: Try native PDF text if available
        native_value = self._get_native_text_value(request, target)
        if native_value and native_value[1] >= request.confidence_threshold:
            return ExtractedValue(
                field_id=target.field_id,
                value=native_value[0],
                confidence=native_value[1],
                source="native_text",
                evidence=[
                    EvidenceRef(
                        id=f"ev_{target.field_id}_native",
                        kind="native_text",
                        document="source",
                        page=target.page,
                        bbox=target.bbox,
                        text=native_value[0],
                        confidence=native_value[1],
                    )
                ],
                needs_review=False,
                normalized=False,
            )

        # Step 2: Run OCR on field region
        page_image_ref = request.page_image_refs.get(target.page)
        if not page_image_ref:
            raise ValueError(f"No page image for page {target.page}")

        ocr_result = await self.ocr_gateway.extract_text(
            image_ref=page_image_ref,
            crop_bbox=target.bbox,
        )

        # If OCR confidence is high enough, use it directly
        if ocr_result.average_confidence >= request.confidence_threshold:
            return ExtractedValue(
                field_id=target.field_id,
                value=ocr_result.ocr_text,
                confidence=ocr_result.average_confidence,
                source="ocr",
                evidence=[
                    EvidenceRef(
                        id=f"ev_{target.field_id}_ocr",
                        kind="ocr",
                        document="source",
                        page=target.page,
                        bbox=target.bbox,
                        text=ocr_result.ocr_text,
                        confidence=ocr_result.average_confidence,
                    )
                ],
                needs_review=ocr_result.average_confidence < 0.9,
                normalized=False,
            )

        # Step 3: Use LLM for ambiguity resolution
        resolution = await self._resolve_with_llm(target, ocr_result)

        return ExtractedValue(
            field_id=target.field_id,
            value=resolution.value,
            confidence=resolution.confidence,
            source="llm",
            evidence=resolution.evidence,
            needs_review=resolution.confidence < request.confidence_threshold,
            normalized=True,  # LLM typically normalizes values
        )

    def _get_native_text_value(
        self,
        request: ExtractRequest,
        target: ExtractionTarget,
    ) -> tuple[str, float] | None:
        """Extract value from native PDF text.

        This is a simplified implementation. In production, this would:
        - Search the native text for content within the target bbox
        - Use text extraction libraries like pdfplumber or PyMuPDF
        """
        if not request.native_text:
            return None

        page_text = request.native_text.get(target.page)
        if not page_text:
            return None

        # Placeholder: In real implementation, would search for text
        # within the target.bbox coordinates
        return None

    async def _resolve_with_llm(
        self,
        target: ExtractionTarget,
        ocr_result: OCRResult,
    ) -> AmbiguityResolutionResult:
        """Use LLM to resolve extraction ambiguity."""
        field_context = FieldContext(
            field_id=target.field_id,
            field_name=target.field_name,
            field_type=target.field_type,
            expected_format=target.expected_format,
            validation_rules=target.validation_rules,
        )

        # Convert OCR tokens to LLM format
        ocr_tokens = [
            LLMOCRToken(
                text=token.text,
                bbox=token.bbox,
                confidence=token.confidence,
            )
            for token in ocr_result.ocr_tokens
        ]

        return await self.llm_gateway.resolve_ambiguity(
            field_context=field_context,
            ocr_tokens=ocr_tokens,
            context={
                "ocr_text": ocr_result.ocr_text,
                "ocr_language": ocr_result.ocr_language,
                "average_confidence": ocr_result.average_confidence,
            },
        )
