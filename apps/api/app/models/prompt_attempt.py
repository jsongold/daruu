"""Prompt attempt models for prompt tuning history.

A prompt attempt captures the full request (system prompt, user prompt,
custom rules) and raw LLM response for each autofill run, enabling
users to browse and compare attempts on the /prompting page.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ============================================
# Core Model
# ============================================


class PromptAttempt(BaseModel):
    """A single prompt tuning attempt."""

    id: str = Field(..., description="Unique attempt ID")
    conversation_id: str = Field(..., description="ID of the parent conversation")
    document_id: str = Field(..., description="ID of the target document")
    system_prompt: str = Field(..., description="System prompt sent to the LLM")
    user_prompt: str = Field(..., description="User prompt sent to the LLM")
    custom_rules: list[str] = Field(
        default_factory=list, description="Custom rules active during the attempt"
    )
    raw_response: str = Field(default="", description="Raw LLM response text")
    parsed_result: dict[str, Any] | None = Field(None, description="Parsed result JSON")
    success: bool = Field(default=False, description="Whether the attempt succeeded")
    error: str | None = Field(None, description="Error message if the attempt failed")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (model, processing_time_ms)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


# ============================================
# Response Models
# ============================================


class PromptAttemptResponse(BaseModel):
    """Response for a single prompt attempt (list view)."""

    id: str = Field(..., description="Unique attempt ID")
    conversation_id: str = Field(..., description="Conversation ID")
    document_id: str = Field(..., description="Document ID")
    success: bool = Field(..., description="Whether the attempt succeeded")
    error: str | None = Field(None, description="Error message if failed")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"frozen": True}

    @classmethod
    def from_attempt(cls, attempt: PromptAttempt) -> "PromptAttemptResponse":
        """Create response from PromptAttempt model."""
        return cls(
            id=attempt.id,
            conversation_id=attempt.conversation_id,
            document_id=attempt.document_id,
            success=attempt.success,
            error=attempt.error,
            metadata=attempt.metadata,
            created_at=attempt.created_at,
        )


class PromptAttemptListResponse(BaseModel):
    """Response for list of prompt attempts."""

    items: list[PromptAttemptResponse] = Field(..., description="List of attempts")
    total: int = Field(..., ge=0, description="Total count")

    model_config = {"frozen": True}
