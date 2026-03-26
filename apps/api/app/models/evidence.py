"""Evidence models."""

from pydantic import BaseModel, Field

from app.models.common import BBox


class Evidence(BaseModel):
    """Evidence supporting a field extraction."""

    id: str = Field(..., description="Unique evidence ID")
    field_id: str = Field(..., description="ID of field this evidence supports")
    source: str = Field(..., description="Source of evidence (e.g., 'ocr', 'llm', 'user')")
    bbox: BBox | None = Field(None, description="Bounding box in source document")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    text: str | None = Field(None, description="Extracted text")
    document_id: str = Field(..., description="ID of source document")

    model_config = {"frozen": True}


class EvidenceResponse(BaseModel):
    """Response containing evidence for a field."""

    field_id: str = Field(..., description="ID of the field")
    evidence: list[Evidence] = Field(default_factory=list, description="List of evidence items")

    model_config = {"frozen": True}
