"""Instructor response schemas for FillPlanner LLM calls.

These models define the structured output that Instructor extracts
from the LLM. They are separate from the domain FillPlan model because
the LLM output schema differs from the internal domain representation.
"""

from pydantic import BaseModel, Field


class LLMFilledField(BaseModel):
    """A field the LLM decided to fill."""

    field_id: str = Field(..., description="Target form field ID")
    value: str = Field(..., description="Value to fill")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score")
    source: str | None = Field(None, description="Data source name that provided the value")


class LLMFillResponse(BaseModel):
    """Structured LLM response for autofill."""

    filled_fields: list[LLMFilledField] = Field(default_factory=list, description="Fields to fill")
    unfilled_fields: list[str] = Field(
        default_factory=list, description="Field IDs that could not be filled"
    )
    warnings: list[str] = Field(default_factory=list, description="Warnings about data quality")
