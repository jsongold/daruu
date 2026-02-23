"""Domain models for the FillPlan — output of FillPlanner.

FillPlan describes what to do with each field: fill, skip, or ask the user.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class FillActionType(StrEnum):
    """Type of action to take for a field."""

    FILL = "fill"
    SKIP = "skip"
    ASK_USER = "ask_user"


class FieldFillAction(BaseModel):
    """Action for a single field in the fill plan."""

    field_id: str = Field(..., description="Target form field ID")
    action: FillActionType = Field(..., description="Action type")
    value: str | None = Field(
        None, description="Value to fill (only when action=fill)"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score"
    )
    source: str | None = Field(
        None, description="Data source that provided the value"
    )
    reason: str | None = Field(
        None, description="Reason for skipping or asking user"
    )

    model_config = {"frozen": True}


class FillPlan(BaseModel):
    """Plan for filling a form — output of FillPlanner.

    Contains an action for every field in the form context.
    """

    document_id: str = Field(..., description="Target document ID")
    actions: tuple[FieldFillAction, ...] = Field(
        ..., min_length=1, description="Per-field fill actions"
    )
    model_used: str | None = Field(
        None, description="LLM model used for planning"
    )
    raw_llm_response: str | None = Field(
        None, description="Raw LLM response (for debugging)"
    )

    model_config = {"frozen": True}
