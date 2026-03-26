"""Domain models for the Structure/Labelling service.

These models represent the core domain entities used in structure detection
and label-to-position linking. All models use frozen=True for immutability.

Domain Entities:
- TextBlock: Native PDF text extraction with position
- BoxCandidate: Detected input box/field region
- TableCandidate: Detected table structure
- LabelCandidate: Potential label text with position
- LinkedField: Result of linking a label to a field position
- StructureEvidence: Evidence supporting a field linkage decision
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import BBox


class EvidenceKind(str, Enum):
    """Kind of evidence supporting a field linking decision."""

    LLM_LINKING = "llm_linking"
    OCR_MATCH = "ocr_match"
    PDF_TEXT = "pdf_text"
    PROXIMITY = "proximity"
    SEMANTIC = "semantic"
    TABLE_STRUCTURE = "table_structure"
    LOCAL_DETECTION = "local_detection"  # Heuristic-based detection without LLM


class TextBlock(BaseModel):
    """A block of native PDF text with position.

    Extracted directly from PDF content stream without OCR.
    Used as input for structure detection and label matching.
    """

    id: str = Field(..., description="Unique identifier for this text block")
    text: str = Field(..., description="Text content")
    bbox: BBox = Field(..., description="Bounding box location in the document")
    font_name: str | None = Field(None, description="Font name if available")
    font_size: float | None = Field(None, ge=0, description="Font size in points")
    is_bold: bool = Field(default=False, description="Whether text is bold")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")

    model_config = {"frozen": True}


class BoxCandidate(BaseModel):
    """A detected input box or field region candidate.

    Detected via OpenCV line/contour detection or PDF form field analysis.
    Represents a potential input field that may be linked to a label.
    """

    id: str = Field(..., description="Unique identifier for this box")
    bbox: BBox = Field(..., description="Bounding box location")
    box_type: str = Field(
        default="input",
        description="Type of box (input, checkbox, signature, etc.)",
    )
    has_border: bool = Field(default=True, description="Whether box has visible border")
    fill_color: str | None = Field(None, description="Fill color if detected (hex format)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")
    neighboring_text: list[str] = Field(default_factory=list, description="Nearby text for context")

    model_config = {"frozen": True}


class TableCell(BaseModel):
    """A single cell within a detected table.

    Contains position and content information for table structure analysis.
    """

    row: int = Field(..., ge=0, description="Row index (0-indexed)")
    col: int = Field(..., ge=0, description="Column index (0-indexed)")
    bbox: BBox = Field(..., description="Cell bounding box")
    text: str | None = Field(None, description="Cell text content if extracted")
    is_header: bool = Field(default=False, description="Whether cell is a header")
    rowspan: int = Field(default=1, ge=1, description="Number of rows spanned")
    colspan: int = Field(default=1, ge=1, description="Number of columns spanned")

    model_config = {"frozen": True}


class TableCandidate(BaseModel):
    """A detected table structure candidate.

    Represents a table with rows, columns, and cell structure.
    Used for linking table headers to input cells.
    """

    id: str = Field(..., description="Unique identifier for this table")
    bbox: BBox = Field(..., description="Overall table bounding box")
    rows: int = Field(..., ge=1, description="Number of rows")
    cols: int = Field(..., ge=1, description="Number of columns")
    cells: tuple[TableCell, ...] = Field(default=(), description="Table cells (immutable tuple)")
    has_header_row: bool = Field(default=False, description="Whether first row is header")
    has_header_col: bool = Field(default=False, description="Whether first column is header")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")

    model_config = {"frozen": True}


class LabelCandidate(BaseModel):
    """A potential label text with position.

    Represents text that might be a field label, found via OCR or PDF extraction.
    Will be linked to BoxCandidates by the FieldLabellingAgent.
    """

    id: str = Field(..., description="Unique identifier for this label")
    text: str = Field(..., description="Label text content")
    bbox: BBox = Field(..., description="Label bounding box")
    source: str = Field(default="ocr", description="Source of label (ocr, pdf_text, etc.)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")
    semantic_hints: list[str] = Field(
        default_factory=list,
        description="Semantic hints (e.g., 'name', 'date', 'address')",
    )

    model_config = {"frozen": True}


class StructureEvidence(BaseModel):
    """Evidence supporting a field linking decision.

    Records the reasoning and source information for auditability.
    Required for every linked field per PRD contract.
    """

    id: str = Field(..., description="Unique evidence identifier")
    kind: EvidenceKind = Field(..., description="Kind of evidence")
    field_id: str = Field(..., description="ID of field this evidence supports")
    document_id: str | None = Field(None, description="Source document ID")
    page: int = Field(..., ge=1, description="Page number")
    bbox: BBox | None = Field(None, description="Relevant bounding box")
    text: str | None = Field(None, description="Relevant text snippet")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evidence confidence score")
    rationale: str = Field(..., description="Explanation of why this evidence supports the linking")
    metadata: dict[str, Any] | None = Field(None, description="Additional evidence metadata")

    model_config = {"frozen": True}


class LinkedField(BaseModel):
    """Result of linking a label to a field position.

    Represents a confirmed field with its name (from label), type, position,
    and the anchor (label) position. This is the primary output of the
    FieldLabellingAgent.
    """

    id: str = Field(..., description="Unique field identifier")
    name: str = Field(..., description="Field name (from linked label)")
    field_type: str = Field(default="text", description="Field type (text, checkbox, date, etc.)")
    page: int = Field(..., ge=1, description="Page number")
    bbox: BBox = Field(..., description="Field input area bounding box")
    anchor_bbox: BBox | None = Field(None, description="Anchor/label bounding box")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall linking confidence")
    needs_review: bool = Field(
        default=False,
        description="Whether field needs human review (low confidence)",
    )
    evidence_refs: tuple[str, ...] = Field(
        default=(), description="IDs of supporting evidence (immutable tuple)"
    )
    label_candidate_id: str | None = Field(None, description="ID of linked label candidate")
    box_candidate_id: str | None = Field(None, description="ID of linked box candidate")
    table_id: str | None = Field(None, description="ID of containing table (if in table)")

    model_config = {"frozen": True}


class DetectedStructures(BaseModel):
    """Aggregated structure detection results.

    Contains all detected candidates from structure detection phase,
    before label-to-position linking.
    """

    page: int = Field(..., ge=1, description="Page number")
    text_blocks: tuple[TextBlock, ...] = Field(default=(), description="Native PDF text blocks")
    box_candidates: tuple[BoxCandidate, ...] = Field(default=(), description="Detected input boxes")
    table_candidates: tuple[TableCandidate, ...] = Field(default=(), description="Detected tables")
    label_candidates: tuple[LabelCandidate, ...] = Field(
        default=(), description="Potential label texts"
    )

    model_config = {"frozen": True}
