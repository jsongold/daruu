"""Pipeline stage and execution models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    """Pipeline processing stages in execution order."""

    INGEST = "ingest"
    STRUCTURE = "structure"
    LABELLING = "labelling"
    MAP = "map"
    EXTRACT = "extract"
    ADJUST = "adjust"
    FILL = "fill"
    REVIEW = "review"


# Ordered list of stages for sequential processing
PIPELINE_STAGE_ORDER: list[PipelineStage] = [
    PipelineStage.INGEST,
    PipelineStage.STRUCTURE,
    PipelineStage.LABELLING,
    PipelineStage.MAP,
    PipelineStage.EXTRACT,
    PipelineStage.ADJUST,
    PipelineStage.FILL,
    PipelineStage.REVIEW,
]


class StageStatus(str, Enum):
    """Status of a pipeline stage execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageResult(BaseModel):
    """Result of executing a pipeline stage."""

    stage: PipelineStage = Field(..., description="Pipeline stage executed")
    status: StageStatus = Field(..., description="Execution status")
    started_at: datetime = Field(..., description="When stage execution started")
    completed_at: datetime | None = Field(None, description="When stage execution completed")
    duration_ms: int | None = Field(None, ge=0, description="Execution duration in milliseconds")
    output: dict[str, Any] = Field(default_factory=dict, description="Stage output data")
    error_message: str | None = Field(None, description="Error message if failed")

    model_config = {"frozen": True}


class NextActionType(str, Enum):
    """Type of next action to take."""

    CONTINUE = "continue"  # Proceed to next stage
    ASK = "ask"  # Ask user for input
    MANUAL = "manual"  # Require manual intervention
    RETRY = "retry"  # Retry a specific stage
    DONE = "done"  # Pipeline complete
    BLOCKED = "blocked"  # Cannot proceed


class NextAction(BaseModel):
    """Describes the next action to take in the pipeline."""

    action: NextActionType = Field(..., description="Type of action to take")
    stage: PipelineStage | None = Field(None, description="Target stage (for continue/retry)")
    reason: str = Field(..., description="Explanation for this action")
    field_ids: list[str] = Field(default_factory=list, description="Related field IDs")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    model_config = {"frozen": True}


class RunMode(str, Enum):
    """Mode for running the pipeline."""

    STEP = "step"  # Execute single step
    UNTIL_BLOCKED = "until_blocked"  # Run until blocked or done
    UNTIL_DONE = "until_done"  # Run until done (may timeout)


class RunRequest(BaseModel):
    """Request to run a job."""

    run_mode: RunMode = Field(default=RunMode.STEP, description="How to run the job")
    max_steps: int | None = Field(None, ge=1, le=100, description="Maximum steps to execute")

    model_config = {"frozen": True}


class RunResponse(BaseModel):
    """Response after running a job."""

    status: str = Field(..., description="Current job status")
    steps_executed: int = Field(..., ge=0, description="Number of steps executed in this run")
    current_stage: PipelineStage | None = Field(None, description="Current pipeline stage")
    next_actions: list[NextAction] = Field(
        default_factory=list, description="Suggested next actions"
    )
    stage_results: list[StageResult] = Field(
        default_factory=list, description="Results of executed stages"
    )

    model_config = {"frozen": True}


def get_next_stage(current_stage: PipelineStage | None) -> PipelineStage | None:
    """Get the next stage in the pipeline sequence.

    Args:
        current_stage: Current pipeline stage, or None if at start

    Returns:
        Next stage in sequence, or None if at end
    """
    if current_stage is None:
        return PIPELINE_STAGE_ORDER[0]

    try:
        current_index = PIPELINE_STAGE_ORDER.index(current_stage)
        next_index = current_index + 1
        if next_index < len(PIPELINE_STAGE_ORDER):
            return PIPELINE_STAGE_ORDER[next_index]
        return None
    except ValueError:
        return None


def get_stage_index(stage: PipelineStage) -> int:
    """Get the index of a stage in the pipeline sequence.

    Args:
        stage: Pipeline stage

    Returns:
        Index of the stage (0-based)

    Raises:
        ValueError: If stage is not in the pipeline
    """
    return PIPELINE_STAGE_ORDER.index(stage)
