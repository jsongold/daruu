"""DTOs for the /analyze endpoint."""

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequestDTO(BaseModel):
    """Request body for POST /api/v1/analyze.

    Analyze document structure and detect fields/anchors.
    Uses LLM for label-to-position linking.
    """

    document_id: str = Field(..., description="ID of document to analyze")
    options: dict[str, Any] | None = Field(
        None,
        description="Analysis options",
        examples=[{"detect_tables": True, "language": "ja"}],
    )

    model_config = {"frozen": True}


class FieldDTO(BaseModel):
    """A detected field in the document."""

    id: str = Field(..., description="Field ID")
    name: str = Field(..., description="Field name/label")
    field_type: str = Field(..., description="Field type (text, checkbox, etc.)")
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x0, y0, x1, y1]",
    )
    anchor_bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Anchor/label bounding box",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    is_required: bool = Field(default=False, description="Whether field is required")
    evidence_refs: list[str] = Field(
        default_factory=list, description="Evidence references"
    )

    model_config = {"frozen": True}


class AnalyzeResponseDTO(BaseModel):
    """Response body for POST /api/v1/analyze."""

    document_id: str = Field(..., description="Analyzed document ID")
    fields: list[FieldDTO] = Field(
        default_factory=list, description="Detected fields"
    )
    page_count: int = Field(..., ge=1, description="Number of pages analyzed")
    has_acroform: bool = Field(..., description="Whether document has AcroForm fields")
    warnings: list[str] = Field(
        default_factory=list, description="Any warnings generated"
    )

    model_config = {"frozen": True}
