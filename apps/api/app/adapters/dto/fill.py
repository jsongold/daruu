"""DTOs for the /fill endpoint."""

from typing import Any

from pydantic import BaseModel, Field


class FillValueDTO(BaseModel):
    """A value to fill into a field."""

    field_id: str = Field(..., description="Target field ID")
    value: str = Field(..., description="Value to fill")

    model_config = {"frozen": True}


class RenderParamsDTO(BaseModel):
    """Rendering parameters for overlay drawing."""

    font_name: str = Field(default="Helvetica", description="Font family name")
    font_size: float = Field(default=12.0, gt=0, description="Font size in points")
    font_color: list[float] = Field(
        default=[0, 0, 0],
        min_length=3,
        max_length=3,
        description="RGB color [0-1, 0-1, 0-1]",
    )
    alignment: str = Field(default="left", description="Text alignment (left/center/right)")
    line_height: float = Field(default=1.2, gt=0, description="Line height multiplier")

    model_config = {"frozen": True}


class FillRequestDTO(BaseModel):
    """Request body for POST /api/v1/fill.

    Fill target document with values.
    Supports AcroForm filling or overlay drawing.
    """

    document_id: str = Field(..., description="Target document ID")
    values: list[FillValueDTO] = Field(
        ..., min_length=1, description="Values to fill"
    )
    method: str = Field(
        default="auto",
        description="Fill method: auto, acroform, or overlay",
    )
    render_params: RenderParamsDTO | None = Field(
        None, description="Default rendering parameters for overlay mode"
    )
    field_params: dict[str, RenderParamsDTO] | None = Field(
        None, description="Field-specific rendering parameters"
    )
    options: dict[str, Any] | None = Field(None, description="Additional options")

    model_config = {"frozen": True}


class IssueDTO(BaseModel):
    """An issue detected during filling."""

    field_id: str = Field(..., description="Field ID with issue")
    issue_type: str = Field(
        ..., description="Issue type (overflow, overlap, missing, etc.)"
    )
    message: str = Field(..., description="Human-readable issue description")
    severity: str = Field(..., description="Severity (info, warning, error)")

    model_config = {"frozen": True}


class FillResponseDTO(BaseModel):
    """Response body for POST /api/v1/fill."""

    document_id: str = Field(..., description="Target document ID")
    output_url: str = Field(..., description="URL to download filled PDF")
    filled_count: int = Field(..., ge=0, description="Number of fields filled")
    failed_count: int = Field(..., ge=0, description="Number of fields that failed")
    issues: list[IssueDTO] = Field(
        default_factory=list, description="Issues detected during filling"
    )
    method_used: str = Field(..., description="Fill method that was used")

    model_config = {"frozen": True}
