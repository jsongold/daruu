"""Domain models for the Extract service.

These models represent the core domain concepts for value extraction:
- OCR results (tokens, lines, full page)
- Native PDF text extraction results
- Value candidates with confidence
- Extraction evidence

All models use frozen=True for immutability, following project conventions.
"""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import BBox
from app.models.extract.models import EvidenceKind, ExtractionEvidence

# Re-export for backward compatibility
__all__ = [
    "EvidenceKind",
    "ExtractionEvidence",
    "OcrToken",
    "OcrLine",
    "OcrResult",
    "NativeTextLine",
    "NativeTextResult",
    "ValueCandidate",
]


class OcrToken(BaseModel):
    """A single OCR token (word) with position and confidence.

    Represents the smallest unit of OCR output - typically a word
    with its bounding box and recognition confidence.
    """

    text: str = Field(..., description="Recognized text content")
    bbox: BBox = Field(..., description="Bounding box of the token")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="OCR confidence score"
    )

    model_config = {"frozen": True}


class OcrLine(BaseModel):
    """A line of OCR text composed of tokens.

    Groups tokens that belong to the same text line,
    with aggregate confidence and bounding box.
    """

    text: str = Field(..., description="Full line text (concatenated tokens)")
    tokens: tuple[OcrToken, ...] = Field(
        ..., description="Individual tokens in the line"
    )
    bbox: BBox = Field(..., description="Bounding box encompassing the line")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Aggregate line confidence"
    )

    model_config = {"frozen": True}


class OcrResult(BaseModel):
    """Complete OCR result for a region or page.

    Contains all recognized text organized as lines and tokens,
    with metadata about the OCR operation.
    """

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    lines: tuple[OcrLine, ...] = Field(
        ..., description="Recognized lines of text"
    )
    region_bbox: BBox | None = Field(
        None, description="Bounding box of the OCR region (None = full page)"
    )
    engine: str = Field(
        default="paddleocr", description="OCR engine used (paddleocr, tesseract)"
    )
    processing_time_ms: int | None = Field(
        None, description="Time taken for OCR processing in milliseconds"
    )

    model_config = {"frozen": True}

    @property
    def full_text(self) -> str:
        """Get all text concatenated with newlines."""
        return "\n".join(line.text for line in self.lines)

    @property
    def avg_confidence(self) -> float:
        """Calculate average confidence across all lines."""
        if not self.lines:
            return 0.0
        return sum(line.confidence for line in self.lines) / len(self.lines)


class NativeTextLine(BaseModel):
    """A line of text extracted from native PDF content.

    Represents text directly embedded in the PDF (not from OCR),
    typically from vector/text-based PDFs.
    """

    text: str = Field(..., description="Text content")
    bbox: BBox = Field(..., description="Bounding box of the text")
    font_name: str | None = Field(None, description="Font name if available")
    font_size: float | None = Field(None, description="Font size in points")

    model_config = {"frozen": True}


class NativeTextResult(BaseModel):
    """Native PDF text extraction result.

    Contains text directly extracted from the PDF document
    without OCR, preserving position and font information.
    """

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    lines: tuple[NativeTextLine, ...] = Field(
        ..., description="Extracted text lines"
    )
    region_bbox: BBox | None = Field(
        None, description="Bounding box of extraction region (None = full page)"
    )
    has_text_layer: bool = Field(
        default=True, description="Whether the PDF has a native text layer"
    )

    model_config = {"frozen": True}

    @property
    def full_text(self) -> str:
        """Get all text concatenated with newlines."""
        return "\n".join(line.text for line in self.lines)


# NOTE: ExtractionEvidence is now defined in app.models.extract.models
# and re-exported from this module for backward compatibility


class ValueCandidate(BaseModel):
    """A candidate value with confidence and evidence.

    Represents a potential extracted value before final selection,
    with supporting evidence and rationale.
    """

    value: str = Field(..., description="Candidate value string")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score"
    )
    rationale: str | None = Field(
        None, description="Explanation for this candidate"
    )
    evidence_refs: tuple[str, ...] = Field(
        default=(), description="IDs of supporting evidence"
    )

    model_config = {"frozen": True}
