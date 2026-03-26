"""Domain models for the RenderReport — output of FormRenderer.

RenderReport captures per-field rendering results and the reference
to the filled PDF document.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class RenderStatus(StrEnum):
    """Status of a single field render operation."""

    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


class ValidationResult(BaseModel):
    """Validation result for a rendered field value."""

    valid: bool = Field(..., description="Whether the value passed validation")
    message: str | None = Field(None, description="Validation message (if invalid)")

    model_config = {"frozen": True}


class FieldRenderResult(BaseModel):
    """Result of rendering a single field."""

    field_id: str = Field(..., description="Field ID that was rendered")
    status: RenderStatus = Field(..., description="Render status")
    value_written: str | None = Field(None, description="Actual value written to PDF")
    validation: ValidationResult | None = Field(None, description="Validation result")
    error_message: str | None = Field(None, description="Error message (if status=failed)")

    model_config = {"frozen": True}


class RenderReport(BaseModel):
    """Report from FormRenderer after filling a PDF.

    Contains the filled document reference and per-field results.
    """

    success: bool = Field(..., description="Whether rendering completed")
    filled_document_ref: str | None = Field(
        None, description="Reference to the filled PDF (if successful)"
    )
    field_results: tuple[FieldRenderResult, ...] = Field(
        default=(), description="Per-field render results"
    )
    filled_count: int = Field(default=0, ge=0, description="Number of fields successfully rendered")
    failed_count: int = Field(default=0, ge=0, description="Number of fields that failed to render")
    error_message: str | None = Field(
        None, description="Top-level error message (if success=False)"
    )

    model_config = {"frozen": True}
