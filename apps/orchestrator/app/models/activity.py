"""Activity models for event tracking."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.pipeline import PipelineStage


class ActivityAction(str, Enum):
    """Type of activity action for tracking events."""

    # Job lifecycle
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_BLOCKED = "job_blocked"

    # Pipeline stages
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"
    STAGE_SKIPPED = "stage_skipped"
    STAGE_RETRIED = "stage_retried"

    # Document operations
    DOCUMENT_INGESTED = "document_ingested"
    STRUCTURE_ANALYZED = "structure_analyzed"
    FIELDS_LABELED = "fields_labeled"

    # Mapping and extraction
    MAPPING_CREATED = "mapping_created"
    MAPPING_CONFIRMED = "mapping_confirmed"
    FIELD_EXTRACTED = "field_extracted"
    EXTRACTION_COMPLETED = "extraction_completed"

    # Adjustment and filling
    LAYOUT_ADJUSTED = "layout_adjusted"
    FIELD_FILLED = "field_filled"
    PDF_RENDERED = "pdf_rendered"

    # Review and issues
    REVIEW_STARTED = "review_started"
    REVIEW_COMPLETED = "review_completed"
    ISSUE_DETECTED = "issue_detected"
    ISSUE_RESOLVED = "issue_resolved"

    # User interactions
    USER_INPUT_REQUESTED = "user_input_requested"
    USER_INPUT_RECEIVED = "user_input_received"
    FIELD_EDITED = "field_edited"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"

    # Errors and retries
    ERROR_OCCURRED = "error_occurred"
    RETRY_SCHEDULED = "retry_scheduled"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"


class Activity(BaseModel):
    """An activity record in the job timeline.

    Activities provide a detailed event history for:
    - UI display (progress tracking)
    - Debugging and monitoring
    - Log-Learn system for improving future processing
    """

    id: str = Field(..., description="Unique activity ID")
    timestamp: datetime = Field(..., description="When the activity occurred")
    action: ActivityAction = Field(..., description="Type of action")
    stage: PipelineStage | None = Field(None, description="Related pipeline stage")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")
    field_id: str | None = Field(None, description="Related field ID if applicable")
    field_ids: list[str] = Field(default_factory=list, description="Multiple related field IDs")
    duration_ms: int | None = Field(None, ge=0, description="Duration if timed operation")
    error: str | None = Field(None, description="Error message if applicable")

    model_config = {"frozen": True}


def create_activity(
    activity_id: str,
    action: ActivityAction,
    *,
    stage: PipelineStage | None = None,
    details: dict[str, Any] | None = None,
    field_id: str | None = None,
    field_ids: list[str] | None = None,
    duration_ms: int | None = None,
    error: str | None = None,
) -> Activity:
    """Factory function to create an activity with timestamp.

    Args:
        activity_id: Unique identifier for the activity
        action: Type of action being recorded
        stage: Related pipeline stage
        details: Additional context data
        field_id: Single related field ID
        field_ids: Multiple related field IDs
        duration_ms: Duration of timed operation
        error: Error message if applicable

    Returns:
        New Activity instance with current timestamp
    """
    return Activity(
        id=activity_id,
        timestamp=datetime.utcnow(),
        action=action,
        stage=stage,
        details=details or {},
        field_id=field_id,
        field_ids=field_ids or [],
        duration_ms=duration_ms,
        error=error,
    )
