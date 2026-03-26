"""Domain models for the FillPlan — output of FillPlanner.

FillPlan describes what to do with each field: fill, skip, or ask the user.
Also includes models for interactive Q&A in detailed autofill mode.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class FillActionType(StrEnum):
    """Type of action to take for a field."""

    FILL = "fill"
    SKIP = "skip"
    ASK_USER = "ask_user"


class QuestionType(StrEnum):
    """Type of question to ask the user."""

    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    FREE_TEXT = "free_text"
    CONFIRM = "confirm"


class QuestionOption(BaseModel):
    """An option in a question."""

    id: str = Field(..., description="Option identifier")
    label: str = Field(..., description="Option display text")

    model_config = {"frozen": True}


class FieldQuestion(BaseModel):
    """A question to ask the user about one or more fields."""

    id: str = Field(default="q0", description="Unique question identifier")
    text: str = Field(..., description="Question text")
    type: QuestionType = Field(..., description="Question type")
    options: tuple[QuestionOption, ...] = Field(
        default=(), description="Options for choice questions"
    )
    placeholder: str | None = Field(None, description="Placeholder text for free_text type")
    context: str | None = Field(None, description="Why the system is asking this question")

    model_config = {"frozen": True}


class FieldFillAction(BaseModel):
    """Action for a single field in the fill plan."""

    field_id: str = Field(..., description="Target form field ID")
    action: FillActionType = Field(..., description="Action type")
    value: str | None = Field(None, description="Value to fill (only when action=fill)")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    source: str | None = Field(None, description="Data source that provided the value")
    reason: str | None = Field(None, description="Reason for skipping or asking user")
    question: FieldQuestion | None = Field(None, description="Question for ASK_USER actions")

    model_config = {"frozen": True}


class FillPlan(BaseModel):
    """Plan for filling a form — output of FillPlanner.

    Contains an action for every field in the form context.
    """

    document_id: str = Field(..., description="Target document ID")
    actions: tuple[FieldFillAction, ...] = Field(
        ..., min_length=1, description="Per-field fill actions"
    )
    model_used: str | None = Field(None, description="LLM model used for planning")
    raw_llm_response: str | None = Field(None, description="Raw LLM response (for debugging)")
    system_prompt: str | None = Field(None, description="System prompt sent to LLM")
    user_prompt: str | None = Field(None, description="User prompt sent to LLM")

    model_config = {"frozen": True}
