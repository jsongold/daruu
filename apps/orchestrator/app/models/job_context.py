"""Job context and related models for orchestrator.

This module defines the core data structures for job processing,
including fields, mappings, extractions, evidence, and issues.
These are compatible with the contracts defined in apps/api but
tailored for orchestrator-specific needs.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.activity import Activity
from app.models.pipeline import PipelineStage, StageResult


class JobMode(str, Enum):
    """Mode of job operation."""

    TRANSFER = "transfer"  # Copy data from source to target
    SCRATCH = "scratch"  # Fill target from scratch (no source)


class JobStatus(str, Enum):
    """Current status of a job."""

    CREATED = "created"
    RUNNING = "running"
    BLOCKED = "blocked"  # Waiting for user input
    DONE = "done"
    FAILED = "failed"


class FieldType(str, Enum):
    """Type of form field."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    IMAGE = "image"
    UNKNOWN = "unknown"


class BBox(BaseModel):
    """Bounding box coordinates for a region on a page."""

    x: float = Field(..., description="X coordinate (left)")
    y: float = Field(..., description="Y coordinate (top)")
    width: float = Field(..., ge=0, description="Width of the box")
    height: float = Field(..., ge=0, description="Height of the box")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")

    model_config = {"frozen": True}


class DocumentMeta(BaseModel):
    """Metadata about a document."""

    page_count: int = Field(..., ge=1, description="Number of pages")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the document")
    filename: str = Field(..., description="Original filename")
    has_password: bool = Field(default=False, description="Whether document is password-protected")

    model_config = {"frozen": True}


class DocumentType(str, Enum):
    """Type of document in the workflow."""

    SOURCE = "source"
    TARGET = "target"


class Document(BaseModel):
    """A document in the system."""

    id: str = Field(..., description="Unique document ID")
    ref: str = Field(..., description="Document reference/path")
    document_type: DocumentType = Field(..., description="Type of document")
    meta: DocumentMeta = Field(..., description="Document metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"frozen": True}


class FieldModel(BaseModel):
    """A form field in a document."""

    id: str = Field(..., description="Unique field ID")
    name: str = Field(..., description="Field name/label")
    field_type: FieldType = Field(default=FieldType.TEXT, description="Type of field")
    value: str | None = Field(None, description="Current field value")
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score for extracted value"
    )
    bbox: BBox | None = Field(None, description="Bounding box location")
    document_id: str = Field(..., description="ID of document containing this field")
    page: int = Field(..., ge=1, description="Page number where field appears")
    is_required: bool = Field(default=False, description="Whether field is required")
    is_editable: bool = Field(default=True, description="Whether field can be edited")

    model_config = {"frozen": True}


class Mapping(BaseModel):
    """Mapping between source and target fields."""

    id: str = Field(..., description="Unique mapping ID")
    source_field_id: str = Field(..., description="ID of source field")
    target_field_id: str = Field(..., description="ID of target field")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this mapping")
    is_confirmed: bool = Field(default=False, description="Whether mapping is user-confirmed")

    model_config = {"frozen": True}


class Extraction(BaseModel):
    """An extracted value for a field."""

    id: str = Field(..., description="Unique extraction ID")
    field_id: str = Field(..., description="ID of target field")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of supporting evidence")

    model_config = {"frozen": True}


class Evidence(BaseModel):
    """Evidence supporting a field extraction."""

    id: str = Field(..., description="Unique evidence ID")
    field_id: str = Field(..., description="ID of field this evidence supports")
    source: str = Field(..., description="Source of evidence (e.g., 'ocr', 'llm', 'user')")
    bbox: BBox | None = Field(None, description="Bounding box in source document")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    text: str | None = Field(None, description="Extracted text")
    document_id: str = Field(..., description="ID of source document")

    model_config = {"frozen": True}


class IssueType(str, Enum):
    """Type of issue encountered during processing."""

    LOW_CONFIDENCE = "low_confidence"
    MISSING_VALUE = "missing_value"
    VALIDATION_ERROR = "validation_error"
    MAPPING_AMBIGUOUS = "mapping_ambiguous"
    FORMAT_MISMATCH = "format_mismatch"
    LAYOUT_ISSUE = "layout_issue"  # Overflow, overlap
    OCR_ERROR = "ocr_error"
    EXTRACTION_FAILED = "extraction_failed"


class IssueSeverity(str, Enum):
    """Severity level of an issue."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class Issue(BaseModel):
    """An issue or problem detected during processing."""

    id: str = Field(..., description="Unique issue ID")
    field_id: str | None = Field(None, description="ID of field with issue")
    issue_type: IssueType = Field(..., description="Type of issue")
    message: str = Field(..., description="Human-readable issue description")
    severity: IssueSeverity = Field(..., description="Severity level")
    suggested_action: str | None = Field(None, description="Suggested action to resolve")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional context")

    model_config = {"frozen": True}


class JobThresholds(BaseModel):
    """Configurable thresholds for job processing."""

    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum acceptable confidence"
    )
    mapping_confidence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum confidence for field mappings"
    )
    improvement_rate_threshold: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Minimum improvement rate per iteration"
    )

    model_config = {"frozen": True}


class JobContext(BaseModel):
    """Full context of a job, including all state for orchestration.

    This is the central data structure passed through the pipeline.
    It contains all information needed to:
    - Track current processing state
    - Make branching decisions
    - Store extraction results
    - Record issues and activities
    """

    # Identity
    id: str = Field(..., description="Unique job ID")
    mode: JobMode = Field(..., description="Job mode (transfer or scratch)")
    status: JobStatus = Field(default=JobStatus.CREATED, description="Current status")

    # Documents
    source_document: Document | None = Field(None, description="Source document (for transfer)")
    target_document: Document | None = Field(None, description="Target document to fill")

    # Fields and mappings
    source_fields: list[FieldModel] = Field(default_factory=list, description="Source fields")
    target_fields: list[FieldModel] = Field(default_factory=list, description="Target fields")
    mappings: list[Mapping] = Field(default_factory=list, description="Field mappings")

    # Extractions and evidence
    extractions: list[Extraction] = Field(default_factory=list, description="Extracted values")
    evidence: list[Evidence] = Field(default_factory=list, description="Supporting evidence")

    # Issues tracking
    issues: list[Issue] = Field(default_factory=list, description="Current issues")

    # Activity timeline
    activities: list[Activity] = Field(default_factory=list, description="Activity timeline")

    # Pipeline state
    current_stage: PipelineStage | None = Field(None, description="Current pipeline stage")
    completed_stages: list[PipelineStage] = Field(
        default_factory=list, description="Stages already completed"
    )
    stage_results: list[StageResult] = Field(
        default_factory=list, description="Results of each stage execution"
    )

    # Loop control
    iteration_count: int = Field(default=0, ge=0, description="Current iteration count")
    max_iterations: int = Field(default=10, ge=1, description="Maximum iterations allowed")
    previous_confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Previous average confidence (for improvement tracking)"
    )

    # Configuration
    thresholds: JobThresholds = Field(
        default_factory=JobThresholds, description="Processing thresholds"
    )
    rules: dict[str, Any] = Field(default_factory=dict, description="Custom processing rules")

    # Timestamps
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: datetime | None = Field(None, description="When processing started")
    completed_at: datetime | None = Field(None, description="When processing completed")

    # Progress tracking
    progress: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall progress 0-1")

    model_config = {"frozen": True}


class JobCreate(BaseModel):
    """Request to create a new job."""

    mode: JobMode = Field(..., description="Job mode (transfer or scratch)")
    source_document_id: str | None = Field(
        None, description="ID of source document (required for transfer mode)"
    )
    target_document_id: str = Field(..., description="ID of target document")
    rules: dict[str, Any] | None = Field(None, description="Custom rules for processing")
    thresholds: JobThresholds | None = Field(None, description="Custom thresholds")
    max_iterations: int = Field(default=10, ge=1, le=50, description="Maximum iterations")

    model_config = {"frozen": True}


class JobSummary(BaseModel):
    """Lightweight job summary for listing."""

    id: str = Field(..., description="Unique job ID")
    mode: JobMode = Field(..., description="Job mode")
    status: JobStatus = Field(..., description="Current status")
    progress: float = Field(..., ge=0.0, le=1.0, description="Overall progress")
    current_stage: PipelineStage | None = Field(None, description="Current stage")
    issue_count: int = Field(default=0, ge=0, description="Number of active issues")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


def compute_average_confidence(job_context: JobContext) -> float:
    """Compute the average confidence across all extractions.

    Args:
        job_context: The job context to analyze

    Returns:
        Average confidence score, or 1.0 if no extractions
    """
    if not job_context.extractions:
        return 1.0

    total_confidence = sum(e.confidence for e in job_context.extractions)
    return total_confidence / len(job_context.extractions)


def get_fields_below_threshold(
    job_context: JobContext,
    threshold: float | None = None,
) -> list[FieldModel]:
    """Get target fields with confidence below threshold.

    Args:
        job_context: The job context to analyze
        threshold: Confidence threshold (uses job threshold if not specified)

    Returns:
        List of fields with low confidence
    """
    threshold = threshold or job_context.thresholds.confidence_threshold

    # Build a map of field_id -> confidence from extractions
    extraction_confidence: dict[str, float] = {}
    for extraction in job_context.extractions:
        extraction_confidence[extraction.field_id] = extraction.confidence

    low_confidence_fields: list[FieldModel] = []
    for field in job_context.target_fields:
        confidence = extraction_confidence.get(field.id)
        if confidence is not None and confidence < threshold:
            low_confidence_fields.append(field)

    return low_confidence_fields
