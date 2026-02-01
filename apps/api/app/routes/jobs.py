"""Job routes."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.models import (
    Activity,
    ApiResponse,
    AsyncJobResponse,
    Evidence,
    EvidenceResponse,
    FieldAnswer,
    FieldEdit,
    JobContext,
    JobCreate,
    JobResponse,
    JobStatus,
    ReviewResponse,
    RunAsyncRequest,
    RunAsyncResponse,
    RunMode,
    RunRequest,
    RunResponse,
    TaskStatus,
    TaskStatusResponse,
)
from app.services import JobService
from app.infrastructure.repositories import get_event_publisher

router = APIRouter(prefix="/jobs", tags=["jobs"])


def get_job_service() -> JobService:
    """Get job service instance."""
    return JobService()


# Request/Response models for this router
class AnswersRequest(BaseModel):
    """Request to submit answers."""

    answers: list[FieldAnswer] = Field(..., min_length=1, description="List of answers")


class EditsRequest(BaseModel):
    """Request to submit edits."""

    edits: list[FieldEdit] = Field(..., min_length=1, description="List of edits")


@router.post("", response_model=ApiResponse[JobResponse], status_code=status.HTTP_201_CREATED)
async def create_job(request: JobCreate) -> ApiResponse[JobResponse]:
    """Create a new job.

    Modes:
    - transfer: Copy data from source document to target document
    - scratch: Fill target document from scratch (no source)
    """
    service = get_job_service()

    try:
        job = service.create_job(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ApiResponse(
        success=True,
        data=JobResponse(job_id=job.id),
        meta={"mode": request.mode.value},
    )


@router.get("/{job_id}", response_model=ApiResponse[JobContext])
async def get_job(job_id: str) -> ApiResponse[JobContext]:
    """Get job context by ID.

    Returns full job state including:
    - Status and progress
    - Documents (source/target)
    - Fields, mappings, extractions
    - Issues and activities
    """
    service = get_job_service()
    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return ApiResponse(success=True, data=job)


@router.post("/{job_id}/run", response_model=ApiResponse[RunResponse])
async def run_job(job_id: str, request: RunRequest) -> ApiResponse[RunResponse]:
    """Run a job with the specified mode.

    Run modes:
    - step: Execute a single step
    - until_blocked: Run until blocked or done
    - until_done: Run until done (may auto-answer)
    """
    service = get_job_service()

    # Check job exists
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    try:
        updated_job = await service.run_job(
            job_id=job_id,
            run_mode=request.run_mode,
            max_steps=request.max_steps,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    return ApiResponse(
        success=True,
        data=RunResponse(
            status=updated_job.status,
            job_context=updated_job,
            next_actions=list(updated_job.next_actions),
        ),
    )


@router.post("/{job_id}/answers", response_model=ApiResponse[JobContext])
async def submit_answers(job_id: str, request: AnswersRequest) -> ApiResponse[JobContext]:
    """Submit answers for blocked fields.

    Used when the job is blocked waiting for user input.
    """
    service = get_job_service()

    # Check job exists
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    try:
        updated_job = service.submit_answers(job_id, request.answers)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ApiResponse(success=True, data=updated_job)


@router.post("/{job_id}/edits", response_model=ApiResponse[JobContext])
async def submit_edits(job_id: str, request: EditsRequest) -> ApiResponse[JobContext]:
    """Submit manual edits for fields.

    Used to manually correct or modify field values.
    """
    service = get_job_service()

    # Check job exists
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    try:
        updated_job = service.submit_edits(job_id, request.edits)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ApiResponse(success=True, data=updated_job)


@router.get("/{job_id}/review", response_model=ApiResponse[ReviewResponse])
async def get_review(job_id: str) -> ApiResponse[ReviewResponse]:
    """Get review data for a job.

    Returns:
    - Current issues
    - Page previews with annotations
    - Fields with their values
    - Confidence summary
    """
    service = get_job_service()

    try:
        review = service.get_review(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return ApiResponse(success=True, data=review)


@router.get("/{job_id}/activity", response_model=ApiResponse[list[Activity]])
async def get_activity(job_id: str) -> ApiResponse[list[Activity]]:
    """Get activity log for a job.

    Returns chronological list of all activities.
    """
    service = get_job_service()

    try:
        activities = service.get_activity(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return ApiResponse(success=True, data=activities)


@router.get("/{job_id}/evidence", response_model=ApiResponse[EvidenceResponse])
async def get_evidence(
    job_id: str,
    field_id: str = Query(..., description="Field ID to get evidence for"),
) -> ApiResponse[EvidenceResponse]:
    """Get evidence for a specific field.

    Returns all evidence supporting the field's extracted value.
    """
    service = get_job_service()

    try:
        evidence_list = service.get_evidence(job_id, field_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return ApiResponse(
        success=True,
        data=EvidenceResponse(
            field_id=field_id,
            evidence=evidence_list,
        ),
    )


@router.get("/{job_id}/output.pdf")
async def get_output_pdf(job_id: str) -> FileResponse:
    """Download the output PDF.

    For the current MVP, this returns the *target* document as-is once
    the job reaches status ``done``. The actual filled-output pipeline
    writes to a separate storage key and is not yet wired up here.
    """
    from pathlib import Path

    service = get_job_service()
    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    if job.status.value != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Output not available. Job status: {job.status.value}",
        )

    # NOTE:
    # - Documents are stored via DocumentService, which persists the
    #   underlying file using FileRepository.store(file_id, ...).
    # - The document's `ref` field holds the concrete file path, not
    #   the document_id used as a key in MemoryFileRepository.
    #
    # The previous implementation incorrectly tried to look up the file
    # via `get_path(job.target_document.id)`, which fails because the
    # file repository is keyed by the internal file_id, not by the
    # document_id. As a result, even completed jobs returned 404.
    #
    # Here we instead trust the stored ref path.
    target_ref = job.target_document.ref
    file_path = Path(target_ref)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Output file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"output_{job_id}.pdf",
    )


@router.get("/{job_id}/export.json")
async def export_job(job_id: str) -> JSONResponse:
    """Export job data as JSON.

    Includes all fields, mappings, extractions, evidence, and activities.
    """
    service = get_job_service()

    try:
        export_data = service.export_job(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f"attachment; filename=export_{job_id}.json",
        },
    )


@router.get("/{job_id}/events")
async def stream_events(job_id: str) -> StreamingResponse:
    """Stream real-time events for a job using Server-Sent Events (SSE).

    Events include:
    - job_started: Job execution started
    - step_completed: Processing step completed
    - status_changed: Job status changed
    - field_updated: Field value updated
    - job_completed: Job finished
    """
    service = get_job_service()
    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        event_publisher = get_event_publisher()
        queue = event_publisher.subscribe(job_id)

        try:
            # Send initial connection event
            yield _format_sse_event({
                "event": "connected",
                "job_id": job_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Keep connection alive and send events
            while True:
                try:
                    # Wait for event with timeout for keepalive
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _format_sse_event(event)
                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield _format_sse_event({
                        "event": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
        finally:
            event_publisher.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def _format_sse_event(data: dict[str, Any]) -> str:
    """Format data as an SSE event."""
    event_type = data.get("event", "message")
    json_data = json.dumps(data)
    return f"event: {event_type}\ndata: {json_data}\n\n"


# =============================================================================
# Cost Tracking Endpoints
# =============================================================================


class CostDetailedBreakdown(BaseModel):
    """Detailed cost breakdown for a job."""

    llm_tokens_input: int = Field(..., description="Total input tokens")
    llm_tokens_output: int = Field(..., description="Total output tokens")
    llm_calls: int = Field(..., description="Number of LLM calls")
    ocr_pages_processed: int = Field(..., description="Pages processed by OCR")
    ocr_regions_processed: int = Field(..., description="Regions processed by OCR")
    storage_bytes_uploaded: int = Field(..., description="Bytes uploaded")
    storage_bytes_downloaded: int = Field(..., description="Bytes downloaded")
    estimated_cost_usd: float = Field(..., description="Total estimated cost")
    breakdown: dict[str, float] = Field(..., description="Cost by category")
    model_name: str = Field(..., description="Primary LLM model")
    formatted_cost: str = Field(..., description="Human-readable cost")
    formatted_storage: dict[str, str] = Field(..., description="Human-readable storage")

    model_config = {"frozen": True}


@router.get("/{job_id}/cost", response_model=ApiResponse[CostDetailedBreakdown])
async def get_job_cost(job_id: str) -> ApiResponse[CostDetailedBreakdown]:
    """Get detailed cost breakdown for a job.

    Returns comprehensive cost information including:
    - LLM token usage and costs
    - OCR page and region processing costs
    - Storage upload/download costs
    - Human-readable formatted values
    """
    from app.services.cost_tracking import format_bytes, format_cost

    service = get_job_service()
    job = service.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    cost = job.cost
    breakdown = CostDetailedBreakdown(
        llm_tokens_input=cost.llm_tokens_input,
        llm_tokens_output=cost.llm_tokens_output,
        llm_calls=cost.llm_calls,
        ocr_pages_processed=cost.ocr_pages_processed,
        ocr_regions_processed=cost.ocr_regions_processed,
        storage_bytes_uploaded=cost.storage_bytes_uploaded,
        storage_bytes_downloaded=cost.storage_bytes_downloaded,
        estimated_cost_usd=cost.estimated_cost_usd,
        breakdown={
            "llm_cost_usd": cost.breakdown.llm_cost_usd,
            "ocr_cost_usd": cost.breakdown.ocr_cost_usd,
            "storage_cost_usd": cost.breakdown.storage_cost_usd,
        },
        model_name=cost.model_name,
        formatted_cost=format_cost(cost.estimated_cost_usd),
        formatted_storage={
            "uploaded": format_bytes(cost.storage_bytes_uploaded),
            "downloaded": format_bytes(cost.storage_bytes_downloaded),
        },
    )

    return ApiResponse(success=True, data=breakdown)


# =============================================================================
# Async Task Endpoints
# =============================================================================


def _get_task_queue():
    """Get the Celery task queue (lazy import to avoid circular deps)."""
    try:
        from app.infrastructure.celery import get_task_queue
        return get_task_queue()
    except ImportError:
        return None


@router.post(
    "/{job_id}/run/async",
    response_model=ApiResponse[RunAsyncResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_job_async(
    job_id: str,
    request: RunAsyncRequest,
) -> ApiResponse[RunAsyncResponse]:
    """Enqueue a job for asynchronous processing.

    This endpoint immediately returns with a task_id that can be used
    to track the job's progress via GET /jobs/{job_id}/task/{task_id}.

    Unlike POST /jobs/{job_id}/run, this endpoint does not wait for
    the job to complete.

    Args:
        job_id: ID of the job to run.
        request: Run configuration (run_mode, max_steps).

    Returns:
        Response with job_id and task_id for tracking.
    """
    service = get_job_service()

    # Verify job exists
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    # Check if job is already in terminal state
    if job.status in (JobStatus.DONE, JobStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is already {job.status.value}",
        )

    # Get task queue
    task_queue = _get_task_queue()
    if task_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async task processing is not available",
        )

    # Enqueue the task
    task_id = await task_queue.enqueue(
        "process_job",
        job_id,
        run_mode=request.run_mode,
        max_steps=request.max_steps,
    )

    return ApiResponse(
        success=True,
        data=RunAsyncResponse(
            job_id=job_id,
            task_id=task_id,
            status="running",
            message="Job processing enqueued",
        ),
    )


@router.get(
    "/{job_id}/task/{task_id}",
    response_model=ApiResponse[TaskStatusResponse],
)
async def get_task_status(
    job_id: str,
    task_id: str,
) -> ApiResponse[TaskStatusResponse]:
    """Get the status of an async task.

    Use this endpoint to poll for task completion after calling
    POST /jobs/{job_id}/run/async.

    Args:
        job_id: ID of the job.
        task_id: Celery task ID returned from run/async.

    Returns:
        Task status with progress information.
    """
    service = get_job_service()

    # Verify job exists
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    # Get task queue
    task_queue = _get_task_queue()
    if task_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async task processing is not available",
        )

    # Get task status
    status_info = await task_queue.get_status(task_id)

    # Map to response model
    task_status = TaskStatus(status_info.get("status", "pending"))
    meta = status_info.get("meta", {})

    return ApiResponse(
        success=True,
        data=TaskStatusResponse(
            task_id=task_id,
            status=task_status,
            progress=status_info.get("progress", 0),
            job_id=job_id,
            stage=meta.get("stage"),
            message=meta.get("message"),
            error=status_info.get("error"),
            result=status_info.get("result"),
        ),
    )


@router.delete(
    "/{job_id}/task/{task_id}",
    response_model=ApiResponse[dict[str, Any]],
)
async def cancel_task(
    job_id: str,
    task_id: str,
) -> ApiResponse[dict[str, Any]]:
    """Cancel an async task.

    Attempts to cancel a running or pending task.
    May not succeed if the task has already completed.

    Args:
        job_id: ID of the job.
        task_id: Celery task ID to cancel.

    Returns:
        Response indicating whether cancellation was successful.
    """
    service = get_job_service()

    # Verify job exists
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    # Get task queue
    task_queue = _get_task_queue()
    if task_queue is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Async task processing is not available",
        )

    # Cancel the task
    cancelled = await task_queue.cancel(task_id)

    return ApiResponse(
        success=True,
        data={
            "task_id": task_id,
            "job_id": job_id,
            "cancelled": cancelled,
            "message": "Task cancelled" if cancelled else "Task could not be cancelled",
        },
    )
