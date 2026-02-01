"""Pydantic models for the Structure/Labelling API.

Contract definition for the POST /structure_labelling endpoint.
Input: page_images, native_text_blocks, box/table candidates
Output: fields[] + evidence[]

All models use frozen=True for immutability.
"""

from typing import Any

from pydantic import BaseModel, Field


class PageImageInput(BaseModel):
    """Input page image reference.

    References a rendered page image for visual analysis by the agent.
    """

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    image_ref: str = Field(
        ..., description="Reference/path to the rendered page image"
    )
    width: int | None = Field(None, gt=0, description="Image width in pixels")
    height: int | None = Field(None, gt=0, description="Image height in pixels")

    model_config = {"frozen": True}


class TextBlockInput(BaseModel):
    """Native PDF text block input.

    Text extracted directly from PDF content stream (not OCR).
    """

    id: str = Field(..., description="Unique text block identifier")
    text: str = Field(..., description="Text content")
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x, y, width, height]",
    )
    font_name: str | None = Field(None, description="Font name")
    font_size: float | None = Field(None, ge=0, description="Font size in points")

    model_config = {"frozen": True}


class BoxCandidateInput(BaseModel):
    """Input box candidate detected by structure detector.

    Represents a potential input field region.
    """

    id: str = Field(..., description="Unique box identifier")
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x, y, width, height]",
    )
    box_type: str = Field(
        default="input",
        description="Box type (input, checkbox, signature, etc.)",
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Detection confidence"
    )

    model_config = {"frozen": True}


class TableCellInput(BaseModel):
    """Input table cell."""

    row: int = Field(..., ge=0, description="Row index")
    col: int = Field(..., ge=0, description="Column index")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Cell bounding box [x, y, width, height]",
    )
    text: str | None = Field(None, description="Cell text content")
    is_header: bool = Field(default=False, description="Whether cell is header")

    model_config = {"frozen": True}


class TableCandidateInput(BaseModel):
    """Input table candidate detected by structure detector.

    Represents a detected table structure.
    """

    id: str = Field(..., description="Unique table identifier")
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Table bounding box [x, y, width, height]",
    )
    rows: int = Field(..., ge=1, description="Number of rows")
    cols: int = Field(..., ge=1, description="Number of columns")
    cells: list[TableCellInput] = Field(
        default_factory=list, description="Table cells"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Detection confidence"
    )

    model_config = {"frozen": True}


class StructureLabellingRequest(BaseModel):
    """Request body for POST /structure_labelling.

    Input contract for the Structure/Labelling Service.
    Provides all necessary data for label-to-position linking.
    """

    document_id: str = Field(
        ..., min_length=1, description="Document identifier"
    )
    document_ref: str = Field(
        ..., min_length=1, description="Reference to original document"
    )
    page_images: list[PageImageInput] = Field(
        ..., min_length=1, description="Page images for visual analysis"
    )
    native_text_blocks: list[TextBlockInput] = Field(
        default_factory=list, description="Native PDF text blocks (optional)"
    )
    box_candidates: list[BoxCandidateInput] = Field(
        default_factory=list, description="Detected box candidates (optional)"
    )
    table_candidates: list[TableCandidateInput] = Field(
        default_factory=list, description="Detected table candidates (optional)"
    )
    options: dict[str, Any] | None = Field(
        None,
        description="Additional options (language, detection_mode, etc.)",
        examples=[{"language": "ja", "confidence_threshold": 0.7}],
    )

    model_config = {"frozen": True}


class EvidenceOutput(BaseModel):
    """Evidence supporting a field detection.

    Required for every field per PRD contract.
    """

    id: str = Field(..., description="Unique evidence identifier")
    kind: str = Field(
        ..., description="Evidence kind (llm_linking, ocr_match, etc.)"
    )
    field_id: str = Field(..., description="ID of field this evidence supports")
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Relevant bounding box",
    )
    text: str | None = Field(None, description="Relevant text snippet")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Evidence confidence"
    )
    rationale: str = Field(
        ..., description="Explanation for the linking decision"
    )

    model_config = {"frozen": True}


class FieldOutput(BaseModel):
    """Output field with linked label and position.

    Primary output of the Structure/Labelling Service.
    Contains name, type, bbox, anchor, confidence, and evidence refs.
    """

    id: str = Field(..., description="Unique field identifier")
    name: str = Field(..., description="Field name (from linked label)")
    field_type: str = Field(
        default="text", description="Field type (text, checkbox, date, etc.)"
    )
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Field bounding box [x, y, width, height]",
    )
    anchor_bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Anchor/label bounding box",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Linking confidence"
    )
    needs_review: bool = Field(
        default=False, description="Whether field needs human review"
    )
    evidence_refs: list[str] = Field(
        ..., min_length=1, description="IDs of supporting evidence"
    )
    box_candidate_id: str | None = Field(
        None, description="Original box candidate ID (for mapping back to AcroForm fields)"
    )

    model_config = {"frozen": True}


class StructureLabellingResult(BaseModel):
    """Response body for POST /structure_labelling.

    Output contract: fields[] + evidence[]
    Every field must have at least one evidence_ref per PRD requirement.
    """

    document_id: str = Field(..., description="Document identifier")
    success: bool = Field(..., description="Whether processing succeeded")
    fields: list[FieldOutput] = Field(
        default_factory=list, description="Detected and linked fields"
    )
    evidence: list[EvidenceOutput] = Field(
        default_factory=list, description="Evidence supporting field detections"
    )
    page_count: int = Field(..., ge=1, description="Number of pages processed")
    warnings: list[str] = Field(
        default_factory=list, description="Processing warnings"
    )
    errors: list[str] = Field(
        default_factory=list, description="Processing errors"
    )

    model_config = {"frozen": True}
