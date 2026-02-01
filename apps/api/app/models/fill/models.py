"""Domain models for the Fill service.

All models use frozen=True for immutability, following project conventions.
These models represent the API contract for PDF filling operations.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import BBox


class FillMethod(str, Enum):
    """Method used for filling the PDF."""

    AUTO = "auto"
    ACROFORM = "acroform"
    OVERLAY = "overlay"


class FillErrorCode(str, Enum):
    """Error codes for fill operation failures."""

    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    FIELD_NOT_FOUND = "FIELD_NOT_FOUND"
    INVALID_VALUE = "INVALID_VALUE"
    RENDER_FAILED = "RENDER_FAILED"
    MERGE_FAILED = "MERGE_FAILED"
    FONT_NOT_FOUND = "FONT_NOT_FOUND"
    STORAGE_FAILED = "STORAGE_FAILED"
    UNSUPPORTED_FIELD_TYPE = "UNSUPPORTED_FIELD_TYPE"


class IssueSeverity(str, Enum):
    """Severity level for fill issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueType(str, Enum):
    """Type of issue detected during filling."""

    OVERFLOW = "overflow"
    OVERLAP = "overlap"
    TRUNCATED = "truncated"
    MISSING_FONT = "missing_font"
    LOW_CONTRAST = "low_contrast"
    OUT_OF_BOUNDS = "out_of_bounds"


class FillValue(BaseModel):
    """A value to fill into a specific field.

    Contains the field identifier and the value to be written,
    along with optional field-specific render parameters.
    """

    field_id: str = Field(..., min_length=1, description="Target field ID")
    value: str = Field(..., description="Value to fill into the field")
    bbox: BBox | None = Field(
        None, description="Optional explicit bounding box (overrides field definition)"
    )

    model_config = {"frozen": True}


class RenderParams(BaseModel):
    """Rendering parameters for text drawing.

    Controls how text is rendered when using overlay mode.
    All parameters have sensible defaults for general use.
    """

    font_name: str = Field(
        default="Helvetica", description="Font family name"
    )
    font_size: float = Field(
        default=12.0, gt=0, le=200, description="Font size in points"
    )
    font_color: tuple[float, float, float] = Field(
        default=(0.0, 0.0, 0.0),
        description="RGB color as tuple of floats (0-1 range)",
    )
    alignment: str = Field(
        default="left", pattern="^(left|center|right)$", description="Text alignment"
    )
    line_height: float = Field(
        default=1.2, gt=0, le=5, description="Line height multiplier"
    )
    word_wrap: bool = Field(
        default=True, description="Enable automatic word wrapping"
    )
    overflow_handling: str = Field(
        default="truncate",
        pattern="^(truncate|shrink|error)$",
        description="How to handle text overflow",
    )

    model_config = {"frozen": True}


class FillRequest(BaseModel):
    """Request to fill a PDF document with values.

    Supports both AcroForm filling and overlay drawing modes.
    The method determines how fields are filled in the PDF.
    """

    target_document_ref: str = Field(
        ..., min_length=1, description="Reference to the target PDF document"
    )
    fields: tuple[FillValue, ...] = Field(
        ..., min_length=1, description="Fields and values to fill"
    )
    render_params: RenderParams = Field(
        default_factory=RenderParams,
        description="Default rendering parameters for all fields",
    )
    field_params: dict[str, RenderParams] | None = Field(
        default=None, description="Field-specific rendering parameters (by field_id)"
    )
    method: FillMethod = Field(
        default=FillMethod.AUTO,
        description="Fill method: auto, acroform, or overlay",
    )
    options: dict[str, Any] | None = Field(
        default=None, description="Additional options for customization"
    )

    model_config = {"frozen": True}


class FillIssue(BaseModel):
    """An issue detected during the fill operation.

    Issues are problems that may affect the quality of the
    filled document but do not necessarily cause failure.
    """

    field_id: str = Field(..., description="Field ID where issue occurred")
    issue_type: IssueType = Field(..., description="Type of issue detected")
    severity: IssueSeverity = Field(..., description="Severity level")
    message: str = Field(..., description="Human-readable description")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional issue details"
    )

    model_config = {"frozen": True}


class FillError(BaseModel):
    """Error detail for fill operation failures.

    Represents a fatal error that prevented filling a field.
    """

    code: FillErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    field_id: str | None = Field(
        default=None, description="Field ID if error is field-specific"
    )

    model_config = {"frozen": True}


class RenderArtifact(BaseModel):
    """Reference to a rendering artifact produced during fill.

    Artifacts may include overlay PDFs, temporary files,
    or other intermediate outputs.
    """

    artifact_type: str = Field(..., description="Type of artifact (overlay, preview, etc.)")
    artifact_ref: str = Field(..., description="Storage reference/path to the artifact")
    page_number: int | None = Field(
        default=None, ge=1, description="Page number if artifact is page-specific"
    )

    model_config = {"frozen": True}


class FieldFillResult(BaseModel):
    """Result of filling a single field.

    Tracks whether the field was successfully filled
    and any issues encountered.
    """

    field_id: str = Field(..., description="Field ID that was filled")
    success: bool = Field(..., description="Whether field was filled successfully")
    value_written: str | None = Field(
        default=None, description="Actual value written (may differ from input)"
    )
    issues: tuple[FillIssue, ...] = Field(
        default=(), description="Issues encountered for this field"
    )

    model_config = {"frozen": True}


class FillResult(BaseModel):
    """Result of the fill operation.

    Contains the reference to the filled document and
    metadata about the fill operation including any issues.
    """

    success: bool = Field(..., description="Whether fill operation completed")
    filled_document_ref: str | None = Field(
        default=None, description="Reference to the filled PDF (if successful)"
    )
    method_used: FillMethod = Field(
        ..., description="Method that was actually used for filling"
    )
    field_results: tuple[FieldFillResult, ...] = Field(
        default=(), description="Per-field fill results"
    )
    filled_count: int = Field(
        default=0, ge=0, description="Number of fields successfully filled"
    )
    failed_count: int = Field(
        default=0, ge=0, description="Number of fields that failed to fill"
    )
    errors: tuple[FillError, ...] = Field(
        default=(), description="Fatal errors encountered"
    )
    artifacts: tuple[RenderArtifact, ...] = Field(
        default=(), description="Rendering artifacts produced"
    )

    model_config = {"frozen": True}
