"""Pydantic models for the Adjust service API contract.

All models use frozen=True for immutability, following project conventions.
These models define the input/output contract for the /adjust endpoint.
"""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import BBox
from app.models.field import FieldEdit, FieldModel
from app.models.job import Issue


class PatchType(str, Enum):
    """Type of adjustment patch.

    Defines what kind of correction is being applied to a field.
    """

    BBOX_MOVE = "bbox_move"  # Move bbox position (x, y change)
    BBOX_RESIZE = "bbox_resize"  # Resize bbox (width, height change)
    BBOX_FULL = "bbox_full"  # Full bbox replacement
    RENDER_PARAMS = "render_params"  # Only render parameter changes
    COMBINED = "combined"  # Both bbox and render param changes


class AdjustErrorCode(str, Enum):
    """Error codes for adjust operation failures."""

    NO_FIELDS = "NO_FIELDS"
    INVALID_BBOX = "INVALID_BBOX"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    OVERLAP_UNRESOLVABLE = "OVERLAP_UNRESOLVABLE"


class RenderParams(BaseModel):
    """Rendering parameters for text/value display.

    Controls how a field value should be rendered in the target document.
    """

    font_size: float | None = Field(default=None, gt=0, le=72, description="Font size in points")
    line_height: float | None = Field(default=None, gt=0, description="Line height multiplier")
    wrap: bool | None = Field(default=None, description="Enable text wrapping")
    max_lines: int | None = Field(default=None, ge=1, description="Maximum number of lines")
    alignment: str | None = Field(
        default=None,
        description="Text alignment (left, center, right, justify)",
    )
    overflow_mode: str | None = Field(
        default=None,
        description="How to handle overflow (truncate, shrink, wrap)",
    )

    model_config = {"frozen": True}


class FieldPatch(BaseModel):
    """A patch representing adjustments to a field.

    Contains the difference/delta to apply to a field's bbox and/or
    rendering parameters. The patch is designed to be mergeable
    and reviewable before application.
    """

    field_id: str = Field(..., min_length=1, description="ID of the field to patch")
    patch_type: PatchType = Field(..., description="Type of patch being applied")
    original_bbox: BBox | None = Field(default=None, description="Original bbox before adjustment")
    adjusted_bbox: BBox | None = Field(default=None, description="New bbox after adjustment")
    render_params: RenderParams | None = Field(
        default=None, description="Render parameter adjustments"
    )
    reason: str = Field(..., description="Human-readable reason for adjustment")
    issue_id: str | None = Field(default=None, description="ID of the issue this patch addresses")
    confidence_delta: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Change in confidence from this adjustment",
    )

    model_config = {"frozen": True}


class ConfidenceUpdate(BaseModel):
    """Confidence score update for a field.

    Tracks confidence changes resulting from adjustments.
    """

    field_id: str = Field(..., min_length=1, description="ID of the field")
    original_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence before adjustment"
    )
    updated_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence after adjustment"
    )
    reason: str = Field(..., description="Reason for confidence change")

    model_config = {"frozen": True}


class PageMetaInput(BaseModel):
    """Page metadata input for adjustment calculations.

    Contains page dimensions needed for boundary checking.
    """

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    width: float = Field(..., gt=0, description="Page width in points")
    height: float = Field(..., gt=0, description="Page height in points")

    model_config = {"frozen": True}


class AdjustRequest(BaseModel):
    """Request to adjust field bboxes and rendering parameters.

    This is the input contract for the /adjust endpoint.
    Accepts fields, issues, page metadata, and optional user edits.
    """

    fields: tuple[FieldModel, ...] = Field(
        ..., min_length=1, description="Fields to potentially adjust"
    )
    issues: tuple[Issue, ...] = Field(
        default=(), description="Issues to address (overflow, overlap, etc.)"
    )
    page_meta: tuple[PageMetaInput, ...] = Field(
        ..., min_length=1, description="Page metadata for boundary calculations"
    )
    user_edits: tuple[FieldEdit, ...] = Field(
        default=(), description="User-provided manual edits to incorporate"
    )
    max_iterations: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum adjustment iterations for convergence",
    )
    overlap_threshold: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Minimum overlap ratio to consider as issue",
    )

    model_config = {"frozen": True}


class AdjustError(BaseModel):
    """Error detail for adjustment failures."""

    code: AdjustErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    field_id: str | None = Field(default=None, description="Field ID if error is field-specific")

    model_config = {"frozen": True}


class AdjustResult(BaseModel):
    """Result of the adjust operation.

    This is the output contract for the /adjust endpoint.
    Contains the patches to apply and any confidence updates.
    """

    success: bool = Field(..., description="Whether adjustment completed successfully")
    field_patches: tuple[FieldPatch, ...] = Field(
        default=(), description="Patches to apply to fields (immutable tuple)"
    )
    confidence_updates: tuple[ConfidenceUpdate, ...] = Field(
        default=(), description="Confidence score updates (immutable tuple)"
    )
    resolved_issue_ids: tuple[str, ...] = Field(
        default=(), description="IDs of issues addressed by patches"
    )
    remaining_issue_count: int = Field(
        default=0, ge=0, description="Number of issues that could not be resolved"
    )
    iterations_used: int = Field(
        default=1, ge=0, description="Number of adjustment iterations performed"
    )
    errors: tuple[AdjustError, ...] = Field(
        default=(), description="Errors encountered during adjustment"
    )

    model_config = {"frozen": True}
