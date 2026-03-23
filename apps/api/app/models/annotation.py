"""Annotation pair models for label-bbox pairing persistence."""

from datetime import datetime

from pydantic import BaseModel


class AnnotationBBox(BaseModel):
    """Normalized 0-1 bounding box coordinates."""

    x: float
    y: float
    width: float
    height: float


class AnnotationPairModel(BaseModel):
    """Full annotation pair as stored in the database."""

    id: str
    document_id: str
    label_id: str
    label_text: str
    label_bbox: AnnotationBBox
    label_page: int
    field_id: str
    field_name: str
    field_bbox: AnnotationBBox
    field_page: int
    confidence: float = 100.0
    status: str = "confirmed"
    is_manual: bool = True
    created_at: datetime | None = None


class AnnotationPairCreate(BaseModel):
    """Request body for creating an annotation pair."""

    label_id: str
    label_text: str
    label_bbox: AnnotationBBox
    label_page: int
    field_id: str
    field_name: str
    field_bbox: AnnotationBBox
    field_page: int
    confidence: float = 100.0
    status: str = "confirmed"
    is_manual: bool = True


class AnnotationPairsResponse(BaseModel):
    """Response wrapper for a list of annotation pairs."""

    pairs: list[AnnotationPairModel]
