"""Pipeline and orchestration models."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Re-export OrchestratorConfig from config for backward compatibility
# This allows existing imports like `from app.models.orchestrator import OrchestratorConfig`
# to continue working while centralizing the definition in config.py
from app.config import OrchestratorConfig as OrchestratorConfig  # noqa: F401
from app.models.field import FieldModel
from app.models.job import Activity, Issue


class PipelineStage(str, Enum):
    """Stages in the document processing pipeline."""

    INGEST = "ingest"
    STRUCTURE = "structure"
    LABELLING = "labelling"
    MAP = "map"
    EXTRACT = "extract"
    ADJUST = "adjust"
    FILL = "fill"
    REVIEW = "review"


# Define the standard pipeline sequence
PIPELINE_SEQUENCE: tuple[PipelineStage, ...] = (
    PipelineStage.INGEST,
    PipelineStage.STRUCTURE,
    PipelineStage.LABELLING,
    PipelineStage.MAP,
    PipelineStage.EXTRACT,
    PipelineStage.ADJUST,
    PipelineStage.FILL,
    PipelineStage.REVIEW,
)


class NextActionType(str, Enum):
    """Types of next actions the orchestrator can recommend."""

    CONTINUE = "continue"  # Continue to next stage
    ASK = "ask"  # Ask user for input
    MANUAL = "manual"  # Require manual intervention
    RETRY = "retry"  # Retry a specific stage
    DONE = "done"  # Job is complete
    BLOCKED = "blocked"  # Job is blocked (cannot proceed)


class NextAction(BaseModel):
    """Represents the next action to take in the pipeline."""

    action: Literal["continue", "ask", "manual", "retry", "done", "blocked"] = Field(
        ..., description="Type of action to take"
    )
    stage: PipelineStage | None = Field(
        None, description="Target stage (for continue/retry actions)"
    )
    reason: str = Field(..., description="Reason for this action")
    field_ids: list[str] = Field(
        default_factory=list, description="Field IDs related to this action"
    )

    @field_validator("field_ids", mode="before")
    @classmethod
    def filter_none_field_ids(cls, v: Any) -> list[str]:
        """Filter out None values from field_ids.

        This allows callers to pass [issue.field_id for issue in issues]
        without manually filtering None values (for stage-level issues).
        """
        if v is None:
            return []
        return [fid for fid in v if fid is not None]

    model_config = {"frozen": True}


class StageResult(BaseModel):
    """Result from executing a pipeline stage."""

    stage: PipelineStage = Field(..., description="Stage that was executed")
    success: bool = Field(..., description="Whether the stage succeeded")
    issues: list[Issue] = Field(
        default_factory=list, description="Issues detected during stage execution"
    )
    activities: list[Activity] = Field(
        default_factory=list, description="Activities generated during stage execution"
    )
    updated_fields: list[FieldModel] = Field(
        default_factory=list, description="Fields updated by this stage"
    )
    error_message: str | None = Field(None, description="Error message if stage failed")

    model_config = {"frozen": True}


def get_next_stage(
    current_stage: PipelineStage | None,
    skip_stages: set[PipelineStage] | None = None,
) -> PipelineStage | None:
    """Get the next stage in the pipeline sequence.

    Args:
        current_stage: The current pipeline stage, or None if not started.
        skip_stages: Optional set of stages to skip.

    Returns:
        The next stage, or None if at the end of the pipeline.
    """
    if current_stage is None:
        return PIPELINE_SEQUENCE[0]

    skip = skip_stages or set()

    try:
        current_index = PIPELINE_SEQUENCE.index(current_stage)
        # Find next non-skipped stage
        for next_index in range(current_index + 1, len(PIPELINE_SEQUENCE)):
            next_stage = PIPELINE_SEQUENCE[next_index]
            if next_stage not in skip:
                return next_stage
        return None
    except ValueError:
        return None


# Stages to skip when PDF has AcroForm fields (TRANSFER mode)
# AcroForm provides pre-defined input areas, so no need to:
# - ADJUST: locate/create input boxes (AcroForm already has them)
# - FILL: fill text into boxes (AcroForm has its own fill mechanism)
# - REVIEW: check layout issues (AcroForm defines the layout)
ACROFORM_TRANSFER_SKIP_STAGES: set[PipelineStage] = {
    PipelineStage.ADJUST,
    PipelineStage.FILL,
    PipelineStage.REVIEW,
}

# Stages to skip when PDF has AcroForm fields AND mode is SCRATCH
# In scratch mode with AcroForm:
# - No source document to map from
# - No text to extract (blank form for user to fill)
# - AcroForm already defines field locations
# Pipeline: INGEST -> STRUCTURE -> LABELLING -> done
ACROFORM_SCRATCH_SKIP_STAGES: set[PipelineStage] = {
    PipelineStage.MAP,
    PipelineStage.EXTRACT,
    PipelineStage.ADJUST,
    PipelineStage.FILL,
    PipelineStage.REVIEW,
}

# Backward compatibility alias
ACROFORM_SKIP_STAGES = ACROFORM_TRANSFER_SKIP_STAGES


def get_stage_index(stage: PipelineStage) -> int:
    """Get the index of a stage in the pipeline sequence.

    Args:
        stage: The pipeline stage.

    Returns:
        The index of the stage (0-based).

    Raises:
        ValueError: If the stage is not in the sequence.
    """
    return PIPELINE_SEQUENCE.index(stage)
