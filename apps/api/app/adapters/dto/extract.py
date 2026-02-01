"""DTOs for the /extract endpoint."""

from typing import Any

from pydantic import BaseModel, Field


class ExtractFieldDTO(BaseModel):
    """A field to extract a value for."""

    field_id: str = Field(..., description="Field ID")
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Field bounding box [x0, y0, x1, y1]",
    )

    model_config = {"frozen": True}


class ExtractRequestDTO(BaseModel):
    """Request body for POST /api/v1/extract.

    Extract values from a source document.
    Uses OCR if needed, LLM for ambiguity resolution.
    """

    document_id: str = Field(..., description="Source document ID")
    fields: list[ExtractFieldDTO] | None = Field(
        None,
        description="Specific fields to extract. If None, extracts all detected fields.",
    )
    use_ocr: bool = Field(
        default=True, description="Whether to use OCR for extraction"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for auto-accept",
    )
    options: dict[str, Any] | None = Field(None, description="Extraction options")

    model_config = {"frozen": True}


class EvidenceDTO(BaseModel):
    """Evidence supporting an extracted value."""

    id: str = Field(..., description="Evidence ID")
    kind: str = Field(
        ..., description="Evidence kind (native_text, ocr, llm, user_input)"
    )
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Bounding box [x0, y0, x1, y1]",
    )
    text: str | None = Field(None, description="Extracted text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evidence confidence")

    model_config = {"frozen": True}


class ExtractedValueDTO(BaseModel):
    """An extracted value for a field."""

    field_id: str = Field(..., description="Field ID")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    source: str = Field(
        ..., description="Source of extraction (native_text, ocr, llm)"
    )
    evidence: list[EvidenceDTO] = Field(
        default_factory=list, description="Supporting evidence"
    )
    needs_review: bool = Field(
        default=False, description="Whether manual review is recommended"
    )

    model_config = {"frozen": True}


class ExtractResponseDTO(BaseModel):
    """Response body for POST /api/v1/extract."""

    document_id: str = Field(..., description="Source document ID")
    extractions: list[ExtractedValueDTO] = Field(
        default_factory=list, description="Extracted values"
    )
    failed_fields: list[str] = Field(
        default_factory=list, description="Field IDs that failed extraction"
    )
    needs_questions: list[str] = Field(
        default_factory=list,
        description="Field IDs that need user input",
    )
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings generated"
    )

    model_config = {"frozen": True}
