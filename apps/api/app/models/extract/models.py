"""Pydantic models for Extract service requests and responses.

These models define the contract for the Extract service API:
- ExtractRequest: Input for extraction
- ExtractResult: Output with extractions, evidence, and follow-ups

All models use frozen=True for immutability, following project conventions.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import BBox


class EvidenceKind(str, Enum):
    """Kind of evidence supporting an extracted value.

    Shared between API models and service domain.
    """

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    LLM = "llm"
    USER_INPUT = "user_input"


class ExtractionEvidence(BaseModel):
    """Evidence supporting a value extraction.

    Tracks the source and confidence of extracted values,
    enabling traceability and review.
    """

    id: str = Field(..., description="Unique evidence ID")
    kind: EvidenceKind = Field(..., description="Type of evidence")
    page: int = Field(..., ge=1, description="Page number")
    bbox: BBox | None = Field(None, description="Bounding box of source region")
    text: str | None = Field(None, description="Source text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evidence confidence")

    model_config = {"frozen": True}


class ExtractionSource(str, Enum):
    """Source of the extracted value."""

    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    LLM = "llm"
    USER_INPUT = "user_input"


class ExtractErrorCode(str, Enum):
    """Error codes for extraction failures."""

    NO_TEXT_FOUND = "NO_TEXT_FOUND"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    OCR_FAILED = "OCR_FAILED"
    INVALID_FIELD = "INVALID_FIELD"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    REGION_OUT_OF_BOUNDS = "REGION_OUT_OF_BOUNDS"


class PageArtifact(BaseModel):
    """Reference to a rendered page image artifact.

    Used for OCR processing when native text extraction
    is insufficient.
    """

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    image_ref: str = Field(..., description="Storage reference to page image")
    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")

    model_config = {"frozen": True}


class ExtractField(BaseModel):
    """A field definition for extraction.

    Specifies what to extract and where to look for it.
    """

    field_id: str = Field(..., min_length=1, description="Unique field identifier")
    name: str = Field(..., min_length=1, description="Field name/label")
    field_type: str = Field(
        default="text",
        description="Expected type (text, number, date, checkbox)",
    )
    page: int = Field(..., ge=1, description="Page number to extract from")
    bbox: BBox | None = Field(None, description="Bounding box region to extract from")
    validation_pattern: str | None = Field(None, description="Regex pattern for validation")

    model_config = {"frozen": True}


class ExtractRequest(BaseModel):
    """Request to extract values from a document.

    Input contract for the Extract service.
    """

    document_ref: str = Field(..., min_length=1, description="Reference/path to the document")
    fields: tuple[ExtractField, ...] = Field(..., min_length=1, description="Fields to extract")
    artifacts: tuple[PageArtifact, ...] = Field(
        default=(), description="Rendered page images for OCR"
    )
    user_rules: dict[str, Any] | None = Field(None, description="User-defined extraction rules")
    use_ocr: bool = Field(default=True, description="Whether to use OCR for extraction")
    use_llm: bool = Field(
        default=True,
        description="Whether to use LLM for ambiguity resolution",
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-accept",
    )

    model_config = {"frozen": True}


class Extraction(BaseModel):
    """An extracted value with confidence and evidence.

    Represents a successfully extracted field value.
    """

    field_id: str = Field(..., description="Field identifier")
    value: str = Field(..., description="Extracted value")
    normalized_value: str | None = Field(None, description="Normalized/standardized value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source: ExtractionSource = Field(..., description="Source of extraction")
    evidence: tuple[ExtractionEvidence, ...] = Field(default=(), description="Supporting evidence")
    needs_review: bool = Field(default=False, description="Whether manual review is recommended")
    conflict_detected: bool = Field(
        default=False, description="Whether conflicting values were found"
    )

    model_config = {"frozen": True}


class OcrRequest(BaseModel):
    """Request for OCR processing of a region.

    Used when native text extraction is insufficient and
    OCR is needed for a specific region.
    """

    field_id: str = Field(..., description="Field requiring OCR")
    page: int = Field(..., ge=1, description="Page number")
    bbox: BBox = Field(..., description="Region to OCR")
    reason: str = Field(..., description="Reason OCR is needed")

    model_config = {"frozen": True}


class FollowupQuestion(BaseModel):
    """A question to ask the user for clarification.

    Generated when extraction cannot be completed automatically.
    """

    field_id: str = Field(..., description="Field requiring clarification")
    question: str = Field(..., description="Question to ask the user")
    candidates: tuple[str, ...] = Field(default=(), description="Possible answer candidates")
    reason: str = Field(..., description="Why clarification is needed")

    model_config = {"frozen": True}


class ExtractError(BaseModel):
    """Error detail for extraction failures.

    Provides structured error information for fields
    that could not be extracted.
    """

    field_id: str = Field(..., description="Field that failed")
    code: ExtractErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")

    model_config = {"frozen": True}


class ExtractResult(BaseModel):
    """Result of the extraction operation.

    Output contract for the Extract service.
    """

    document_ref: str = Field(..., description="Document reference from request")
    success: bool = Field(..., description="Whether extraction completed")
    extractions: tuple[Extraction, ...] = Field(
        default=(), description="Successfully extracted values"
    )
    evidence: tuple[ExtractionEvidence, ...] = Field(
        default=(), description="All evidence collected"
    )
    ocr_requests: tuple[OcrRequest, ...] = Field(
        default=(), description="OCR requests for regions needing OCR"
    )
    followup_questions: tuple[FollowupQuestion, ...] = Field(
        default=(), description="Questions for user clarification"
    )
    errors: tuple[ExtractError, ...] = Field(default=(), description="Extraction errors")

    model_config = {"frozen": True}
