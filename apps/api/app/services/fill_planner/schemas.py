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
    confidence: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Confidence score"
    )
    source: str | None = Field(
        None, description="Data source name that provided the value"
    )


class LLMFillResponse(BaseModel):
    """Structured LLM response for quick-mode autofill."""

    filled_fields: list[LLMFilledField] = Field(
        default_factory=list, description="Fields to fill"
    )
    unfilled_fields: list[str] = Field(
        default_factory=list, description="Field IDs that could not be filled"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings about data quality"
    )


class LLMQuestionOption(BaseModel):
    """An option in a question."""

    id: str
    label: str


class LLMQuestion(BaseModel):
    """A question for the user in detailed mode."""

    id: str = Field(default="q0")
    question: str
    question_type: str = Field(default="free_text")
    options: list[LLMQuestionOption] = Field(default_factory=list)
    context: str | None = None


class LLMDetailedQuestionsResponse(BaseModel):
    """LLM response: ask questions."""

    type: str = Field(default="questions")
    questions: list[LLMQuestion] = Field(default_factory=list)


class LLMDetailedFillResponse(BaseModel):
    """LLM response: fill plan (same as quick mode but with type field)."""

    type: str = Field(default="fill_plan")
    filled_fields: list[LLMFilledField] = Field(default_factory=list)
    unfilled_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LLMReasoningResponse(BaseModel):
    """Pre-check: should we ask more questions or fill now?"""

    decision: str = Field(..., pattern="^(ask|fill)$")
    reasoning: str = Field(..., description="1-2 sentence explanation")
