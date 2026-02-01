"""Task-related models for async processing.

These models support the Celery task queue integration.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of an async task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AsyncJobCreate(BaseModel):
    """Request to create a job with async processing.

    This model extends JobCreate with async-specific options.
    """

    mode: str = Field(..., description="Job mode (transfer or scratch)")
    source_document_id: str | None = Field(
        None, description="ID of source document (required for transfer mode)"
    )
    target_document_id: str = Field(..., description="ID of target document")
    rules: dict[str, Any] | None = Field(None, description="Custom rules for processing")
    thresholds: dict[str, float] | None = Field(None, description="Confidence thresholds")

    # Async-specific options
    async_processing: bool = Field(
        default=True,
        description="Whether to process asynchronously (enqueue task)",
    )
    run_mode: str = Field(
        default="until_done",
        description="How to run the job: step, until_blocked, until_done",
    )
    max_steps: int | None = Field(
        None,
        ge=1,
        description="Maximum steps to execute",
    )

    model_config = {"frozen": True}


class AsyncJobResponse(BaseModel):
    """Response after creating an async job.

    Includes task information for tracking.
    """

    job_id: str = Field(..., description="Unique job ID")
    task_id: str | None = Field(None, description="Celery task ID for tracking")
    status: str = Field(..., description="Initial job status")
    async_processing: bool = Field(..., description="Whether job is processing async")

    model_config = {"frozen": True}


class TaskStatusResponse(BaseModel):
    """Response for task status inquiry."""

    task_id: str = Field(..., description="Celery task ID")
    status: TaskStatus = Field(..., description="Current task status")
    progress: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Progress percentage",
    )
    job_id: str | None = Field(None, description="Associated job ID")
    stage: str | None = Field(None, description="Current processing stage")
    message: str | None = Field(None, description="Status message")
    error: str | None = Field(None, description="Error message if failed")
    result: dict[str, Any] | None = Field(None, description="Task result if completed")
    started_at: datetime | None = Field(None, description="When task started")
    completed_at: datetime | None = Field(None, description="When task completed")

    model_config = {"frozen": True}


class RunAsyncRequest(BaseModel):
    """Request to run a job asynchronously."""

    run_mode: str = Field(
        default="until_done",
        description="How to run: step, until_blocked, until_done",
    )
    max_steps: int | None = Field(
        None,
        ge=1,
        description="Maximum steps to execute",
    )

    model_config = {"frozen": True}


class RunAsyncResponse(BaseModel):
    """Response after enqueuing a job run."""

    job_id: str = Field(..., description="Job ID")
    task_id: str = Field(..., description="Celery task ID for tracking")
    status: str = Field(..., description="Job status (should be 'running')")
    message: str = Field(default="Job processing started", description="Status message")

    model_config = {"frozen": True}
