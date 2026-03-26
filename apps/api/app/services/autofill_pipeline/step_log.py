"""PipelineStepLog — per-step execution log for pipeline observability."""

from typing import Any

from pydantic import BaseModel, Field


class PipelineStepLog(BaseModel):
    """Execution log for a single pipeline step.

    Captures timing, status, a human-readable summary, and
    step-specific structured details for debugging and prompt tuning.
    """

    step_name: str = Field(
        ...,
        description="Step identifier: context_build, rule_analyze, fill_plan, render",
    )
    status: str = Field(
        ...,
        description="Step outcome: success, error, skipped",
    )
    duration_ms: int = Field(..., ge=0, description="Time spent on this step in milliseconds")
    summary: str = Field(..., description="Human-readable 1-line summary of what happened")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Step-specific structured data for drill-down",
    )
    error: str | None = Field(None, description="Error message if status=error")

    model_config = {"frozen": True}
