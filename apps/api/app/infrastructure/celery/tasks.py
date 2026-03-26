"""Celery task definitions for async processing.

This module defines the main Celery tasks for the daru-pdf system:

- process_job_task: Main pipeline execution task
- ingest_document_task: Document ingestion task

Tasks are designed to be:
- Idempotent where possible
- Self-retrying on transient failures
- Progress-reporting for real-time updates
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from celery import Task, shared_task
from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded

from app.infrastructure.celery.config import get_celery_config
from app.models import JobStatus, RunMode


class BaseTask(Task):
    """Base task class with common error handling and retry logic.

    Provides:
    - Automatic retry on transient failures
    - Progress reporting
    - Dead letter queue handling
    """

    # Retry configuration
    autoretry_for = (ConnectionError, TimeoutError)
    retry_backoff = True
    retry_backoff_max = 300  # 5 minutes max backoff
    retry_jitter = True

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Handle task failure.

        Logs the failure and optionally sends to dead letter queue.

        Args:
            exc: The exception that caused the failure.
            task_id: Unique task identifier.
            args: Positional arguments passed to the task.
            kwargs: Keyword arguments passed to the task.
            einfo: Exception info object.
        """
        # Log failure (would use proper logging in production)
        job_id = args[0] if args else kwargs.get("job_id", "unknown")

        # Update job status to failed
        try:
            from app.infrastructure.repositories import get_job_repository

            job_repository = get_job_repository()
            job_repository.update(
                job_id,
                status=JobStatus.FAILED,
                current_step=f"task_failed: {str(exc)[:100]}",
            )
        except Exception:
            pass  # Best effort status update

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Handle task retry.

        Updates job status to indicate retry in progress.

        Args:
            exc: The exception that caused the retry.
            task_id: Unique task identifier.
            args: Positional arguments passed to the task.
            kwargs: Keyword arguments passed to the task.
            einfo: Exception info object.
        """
        job_id = args[0] if args else kwargs.get("job_id", "unknown")

        # Update job with retry info
        try:
            from app.infrastructure.repositories import get_job_repository

            job_repository = get_job_repository()
            job_repository.update(
                job_id,
                current_step=f"retrying: {str(exc)[:50]}",
            )
        except Exception:
            pass  # Best effort status update


def _run_async(coro: Any) -> Any:
    """Run an async coroutine in a sync context.

    Creates a new event loop if needed.

    Args:
        coro: Coroutine to run.

    Returns:
        Result of the coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        # If there's already a running loop, use run_coroutine_threadsafe

        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=600)
    else:
        # No running loop, create one
        return asyncio.run(coro)


@shared_task(
    bind=True,
    base=BaseTask,
    name="app.infrastructure.celery.tasks.process_job_task",
    max_retries=3,
    default_retry_delay=30,
)
def process_job_task(
    self: Task,
    job_id: str,
    run_mode: str = "until_done",
    max_steps: int | None = None,
) -> dict[str, Any]:
    """Process a job through the pipeline.

    This is the main task for executing the document processing pipeline.
    It delegates to the Orchestrator.run() method with the specified run_mode.

    Args:
        self: Task instance (bound).
        job_id: ID of the job to process.
        run_mode: How to run the job ("step", "until_blocked", "until_done").
        max_steps: Optional maximum steps to execute.

    Returns:
        Dictionary with job status and result information.

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit.
        MaxRetriesExceededError: If max retries exceeded.
    """
    config = get_celery_config()

    try:
        # Update task state to started
        self.update_state(
            state="PROGRESS",
            meta={
                "job_id": job_id,
                "progress": 0.0,
                "stage": "starting",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Import here to avoid circular imports
        from app.infrastructure.repositories import (
            get_event_publisher,
            get_job_repository,
        )
        from app.orchestrator import Orchestrator

        job_repository = get_job_repository()
        event_publisher = get_event_publisher()

        # Verify job exists
        job = job_repository.get(job_id)
        if job is None:
            return {
                "success": False,
                "error": f"Job not found: {job_id}",
                "job_id": job_id,
            }

        # Check if job is already in terminal state
        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            return {
                "success": True,
                "job_id": job_id,
                "status": job.status.value,
                "message": "Job already in terminal state",
            }

        # Create orchestrator
        orchestrator = Orchestrator(
            job_repository=job_repository,
            event_publisher=event_publisher,
        )

        # Parse run mode
        try:
            run_mode_enum = RunMode(run_mode)
        except ValueError:
            run_mode_enum = RunMode.UNTIL_DONE

        # Run the pipeline asynchronously
        async def run_pipeline() -> Any:
            return await orchestrator.run(job_id, run_mode_enum, max_steps)

        result_job = _run_async(run_pipeline())

        # Update final state
        self.update_state(
            state="SUCCESS",
            meta={
                "job_id": job_id,
                "progress": result_job.progress,
                "status": result_job.status.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": result_job.status.value,
            "progress": result_job.progress,
            "current_stage": result_job.current_stage,
            "next_actions": list(result_job.next_actions),
        }

    except SoftTimeLimitExceeded:
        # Update job status before re-raising
        try:
            from app.infrastructure.repositories import get_job_repository

            job_repository = get_job_repository()
            job_repository.update(
                job_id,
                status=JobStatus.BLOCKED,
                current_step="timeout: task exceeded time limit",
            )
        except Exception:
            pass

        raise

    except MaxRetriesExceededError:
        # Final failure after all retries
        return {
            "success": False,
            "error": "Max retries exceeded",
            "job_id": job_id,
            "status": "failed",
        }

    except Exception as e:
        # Attempt retry for transient errors
        try:
            raise self.retry(
                exc=e,
                countdown=config.task_default_retry_delay,
                max_retries=config.task_max_retries,
            )
        except MaxRetriesExceededError:
            return {
                "success": False,
                "error": str(e),
                "job_id": job_id,
                "status": "failed",
            }


@shared_task(
    bind=True,
    base=BaseTask,
    name="app.infrastructure.celery.tasks.ingest_document_task",
    max_retries=3,
    default_retry_delay=15,
)
def ingest_document_task(
    self: Task,
    document_id: str,
    job_id: str | None = None,
    document_ref: str | None = None,
    render_dpi: int = 150,
) -> dict[str, Any]:
    """Ingest a document for processing.

    This task handles document ingestion which includes:
    - Validating the document
    - Extracting metadata
    - Generating page previews
    - Running OCR if needed

    Args:
        self: Task instance (bound).
        document_id: ID of the document to ingest.
        job_id: Optional job ID if part of a job workflow.
        document_ref: Path or reference to the document file.
        render_dpi: DPI for rendering page previews.

    Returns:
        Dictionary with ingestion result information.
    """
    config = get_celery_config()

    try:
        # Update task state
        self.update_state(
            state="PROGRESS",
            meta={
                "document_id": document_id,
                "job_id": job_id,
                "progress": 0.0,
                "stage": "ingesting",
            },
        )

        # Import services and adapters
        from app.config import get_settings
        from app.infrastructure.repositories import (
            get_document_repository,
            get_file_repository,
        )
        from app.services.ingest import (
            IngestRequest,
            IngestService,
            LocalStorageAdapter,
            PyMuPdfAdapter,
        )

        document_repository = get_document_repository()
        file_repository = get_file_repository()
        settings = get_settings()

        # Verify document exists
        document = document_repository.get(document_id)
        if document is None:
            return {
                "success": False,
                "error": f"Document not found: {document_id}",
                "document_id": document_id,
            }

        # Get document file path
        if document_ref is None:
            file_path = file_repository.get_path(document_id)
            if file_path is None:
                return {
                    "success": False,
                    "error": f"Document file not found: {document_id}",
                    "document_id": document_id,
                }
            document_ref = str(file_path)

        # Create adapters
        pdf_reader = PyMuPdfAdapter()
        storage = LocalStorageAdapter(base_path=str(settings.upload_dir))

        # Create service
        ingest_service = IngestService(
            pdf_reader=pdf_reader,
            storage=storage,
        )

        # Create request
        ingest_request = IngestRequest(
            document_id=document_id,
            document_ref=document_ref,
            render_dpi=render_dpi,
        )

        # Run ingestion
        async def run_ingest() -> Any:
            return await ingest_service.ingest(ingest_request)

        result = _run_async(run_ingest())

        # Update final state
        self.update_state(
            state="SUCCESS",
            meta={
                "document_id": document_id,
                "job_id": job_id,
                "progress": 1.0,
                "stage": "complete",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Handle result - check for errors
        if result.error is not None:
            return {
                "success": False,
                "error": result.error.message,
                "error_code": result.error.code.value,
                "document_id": document_id,
                "job_id": job_id,
            }

        return {
            "success": True,
            "document_id": document_id,
            "job_id": job_id,
            "page_count": result.document_meta.page_count if result.document_meta else None,
            "has_text": result.document_meta.has_native_text if result.document_meta else None,
            "pages_rendered": len(result.rendered_pages) if result.rendered_pages else 0,
        }

    except Exception as e:
        # Attempt retry
        try:
            raise self.retry(
                exc=e,
                countdown=config.task_default_retry_delay,
                max_retries=config.task_max_retries,
            )
        except MaxRetriesExceededError:
            return {
                "success": False,
                "error": str(e),
                "document_id": document_id,
                "job_id": job_id,
            }


def update_task_progress(
    task: Task,
    job_id: str,
    progress: float,
    stage: str,
    message: str | None = None,
) -> None:
    """Update task progress state.

    Helper function to update task progress and publish events.

    Args:
        task: The Celery task instance.
        job_id: ID of the job being processed.
        progress: Progress percentage (0.0 to 1.0).
        stage: Current processing stage name.
        message: Optional status message.
    """
    task.update_state(
        state="PROGRESS",
        meta={
            "job_id": job_id,
            "progress": progress,
            "stage": stage,
            "message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    # Publish progress event
    try:
        from app.infrastructure.repositories import get_event_publisher

        event_publisher = get_event_publisher()
        event_publisher.publish_sync(
            job_id,
            {
                "event": "task_progress",
                "job_id": job_id,
                "progress": progress,
                "stage": stage,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception:
        pass  # Best effort event publishing
