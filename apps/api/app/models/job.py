"""Job and workflow models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.common import BBox, CostSummaryModel
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.field import FieldModel, Mapping


class JobMode(str, Enum):
    """Mode of job operation."""

    TRANSFER = "transfer"  # Copy data from source to target
    SCRATCH = "scratch"  # Fill target from scratch (no source)


class JobStatus(str, Enum):
    """Current status of a job."""

    CREATED = "created"
    RUNNING = "running"
    BLOCKED = "blocked"  # Cannot proceed without manual intervention
    AWAITING_INPUT = "awaiting_input"  # Waiting for user input/answer
    DONE = "done"
    FAILED = "failed"


class RunMode(str, Enum):
    """Mode for running a job."""

    STEP = "step"  # Execute single step
    UNTIL_BLOCKED = "until_blocked"  # Run until blocked or done
    UNTIL_DONE = "until_done"  # Run until done (may auto-answer)


class ActivityAction(str, Enum):
    """Type of activity action."""

    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"  # Job execution started
    DOCUMENT_UPLOADED = "document_uploaded"
    EXTRACTION_STARTED = "extraction_started"
    EXTRACTION_COMPLETED = "extraction_completed"
    MAPPING_CREATED = "mapping_created"
    FIELD_EXTRACTED = "field_extracted"
    QUESTION_ASKED = "question_asked"
    ANSWER_RECEIVED = "answer_received"
    FIELD_EDITED = "field_edited"
    RENDERING_STARTED = "rendering_started"
    RENDERING_COMPLETED = "rendering_completed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    ERROR_OCCURRED = "error_occurred"
    RETRY_STARTED = "retry_started"  # Stage retry initiated


class IssueType(str, Enum):
    """Type of issue encountered."""

    LOW_CONFIDENCE = "low_confidence"
    MISSING_VALUE = "missing_value"
    VALIDATION_ERROR = "validation_error"
    MAPPING_AMBIGUOUS = "mapping_ambiguous"
    FORMAT_MISMATCH = "format_mismatch"
    LAYOUT_ISSUE = "layout_issue"  # Overflow/overlap issues


class IssueSeverity(str, Enum):
    """Severity level of an issue."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"
    ERROR = "error"  # Backward compatibility alias for high


class Activity(BaseModel):
    """An activity record in the job timeline."""

    id: str = Field(..., description="Unique activity ID")
    timestamp: datetime = Field(..., description="When the activity occurred")
    action: ActivityAction = Field(..., description="Type of action")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")
    field_id: str | None = Field(None, description="Related field ID if applicable")

    model_config = {"frozen": True}


class Issue(BaseModel):
    """An issue or problem with a field."""

    id: str = Field(..., description="Unique issue ID")
    field_id: str | None = Field(
        None, description="ID of field with issue (optional for stage-level issues)"
    )
    issue_type: IssueType = Field(..., description="Type of issue")
    message: str = Field(..., description="Human-readable issue description")
    severity: IssueSeverity = Field(..., description="Severity level")
    suggested_action: str | None = Field(None, description="Suggested action to resolve")

    model_config = {"frozen": True}


class Extraction(BaseModel):
    """An extracted value for a field."""

    id: str = Field(..., description="Unique extraction ID")
    field_id: str = Field(..., description="ID of target field")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of supporting evidence")

    model_config = {"frozen": True}


class JobCreate(BaseModel):
    """Request to create a new job."""

    mode: JobMode = Field(..., description="Job mode (transfer or scratch)")
    source_document_id: str | None = Field(
        None, description="ID of source document (required for transfer mode)"
    )
    target_document_id: str = Field(..., description="ID of target document")
    rules: dict[str, Any] | None = Field(None, description="Custom rules for processing")
    thresholds: dict[str, float] | None = Field(None, description="Confidence thresholds")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "mode": "transfer",
                    "source_document_id": "550e8400-e29b-41d4-a716-446655440001",
                    "target_document_id": "550e8400-e29b-41d4-a716-446655440002",
                },
                {
                    "mode": "scratch",
                    "target_document_id": "550e8400-e29b-41d4-a716-446655440002",
                    "thresholds": {"auto_accept": 0.9, "review_required": 0.7},
                },
            ]
        },
    }


class JobContext(BaseModel):
    """Full context of a job, including all state."""

    id: str = Field(..., description="Unique job ID")
    mode: JobMode = Field(..., description="Job mode")
    status: JobStatus = Field(..., description="Current status")
    source_document: Document | None = Field(None, description="Source document")
    target_document: Document = Field(..., description="Target document")
    fields: list[FieldModel] = Field(default_factory=list, description="All fields")
    mappings: list[Mapping] = Field(default_factory=list, description="Field mappings")
    extractions: list[Extraction] = Field(default_factory=list, description="Extracted values")
    evidence: list[Evidence] = Field(default_factory=list, description="Supporting evidence")
    issues: list[Issue] = Field(default_factory=list, description="Current issues")
    activities: list[Activity] = Field(default_factory=list, description="Activity timeline")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Progress 0-1")
    current_step: str | None = Field(None, description="Current processing step")
    current_stage: str | None = Field(None, description="Current pipeline stage")
    next_actions: list[str] = Field(default_factory=list, description="Available next actions")
    iteration_count: int = Field(default=0, ge=0, description="Number of retry iterations")
    cost: CostSummaryModel = Field(
        default_factory=CostSummaryModel.empty,
        description="Cost tracking summary for LLM and OCR usage",
    )

    model_config = {"frozen": True}


class JobResponse(BaseModel):
    """Response after job creation."""

    job_id: str = Field(..., description="Unique job ID")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "job_id": "550e8400-e29b-41d4-a716-446655440010",
                }
            ]
        },
    }


class RunRequest(BaseModel):
    """Request to run a job."""

    run_mode: RunMode = Field(..., description="How to run the job")
    max_steps: int | None = Field(None, ge=1, description="Maximum steps to execute")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "run_mode": "step",
                },
                {
                    "run_mode": "until_done",
                    "max_steps": 10,
                },
            ]
        },
    }


class RunResponse(BaseModel):
    """Response after running a job."""

    status: JobStatus = Field(..., description="Current job status")
    job_context: JobContext = Field(..., description="Updated job context")
    next_actions: list[str] = Field(default_factory=list, description="Available next actions")

    model_config = {"frozen": True}


class ConfidenceSummary(BaseModel):
    """Summary of confidence scores across fields."""

    total_fields: int = Field(..., ge=0, description="Total number of fields")
    high_confidence: int = Field(..., ge=0, description="Fields with confidence >= 0.8")
    medium_confidence: int = Field(..., ge=0, description="Fields with confidence 0.5-0.8")
    low_confidence: int = Field(..., ge=0, description="Fields with confidence < 0.5")
    no_value: int = Field(..., ge=0, description="Fields with no value")
    average_confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence")

    model_config = {"frozen": True}


class PagePreview(BaseModel):
    """Preview information for a page."""

    page: int = Field(..., ge=1, description="Page number")
    document_id: str = Field(..., description="Document ID")
    url: str = Field(..., description="URL to fetch preview image")
    annotations: list[BBox] = Field(default_factory=list, description="Annotations on this page")

    model_config = {"frozen": True}


class ReviewResponse(BaseModel):
    """Response for job review endpoint."""

    issues: list[Issue] = Field(default_factory=list, description="Current issues")
    previews: list[PagePreview] = Field(default_factory=list, description="Page previews")
    fields: list[FieldModel] = Field(default_factory=list, description="All fields")
    confidence_summary: ConfidenceSummary = Field(..., description="Confidence summary")

    model_config = {"frozen": True}
