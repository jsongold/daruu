"""CeleryTaskQueue implementation of TaskQueue port.

Provides an implementation of the TaskQueue protocol using Celery
for asynchronous task processing.
"""

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from celery.result import AsyncResult

from app.infrastructure.celery.app import get_celery_app
from app.infrastructure.celery.config import get_celery_config
from app.services.orchestrator.application.ports.task_queue import TaskQueue


class TaskNotFoundError(Exception):
    """Raised when a task is not found."""

    pass


class TaskError(Exception):
    """Raised when a task execution fails."""

    pass


class CeleryTaskQueue:
    """Celery implementation of the TaskQueue port.

    This class provides async task queue operations using Celery:
    - Enqueue tasks for background processing
    - Check task status
    - Cancel tasks
    - Wait for task results

    The implementation follows the TaskQueue protocol interface.
    """

    # Map Celery states to our standardized states
    STATE_MAP = {
        "PENDING": "pending",
        "RECEIVED": "pending",
        "STARTED": "running",
        "PROGRESS": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "RETRY": "pending",
        "REVOKED": "cancelled",
    }

    # Task name mapping
    TASK_MAP = {
        "process_job": "app.infrastructure.celery.tasks.process_job_task",
        "ingest_document": "app.infrastructure.celery.tasks.ingest_document_task",
    }

    def __init__(self) -> None:
        """Initialize the task queue with Celery app."""
        self._app = get_celery_app()
        self._config = get_celery_config()

    async def enqueue(
        self,
        task_name: str,
        job_id: str,
        **kwargs: Any,
    ) -> str:
        """Enqueue a task for async processing.

        Args:
            task_name: Name of the task to execute.
                Supported: "process_job", "ingest_document"
            job_id: ID of the job this task belongs to.
            **kwargs: Additional arguments for the task.

        Returns:
            Task ID for tracking.

        Raises:
            ValueError: If task_name is not supported.
        """
        # Resolve task name
        full_task_name = self.TASK_MAP.get(task_name)
        if full_task_name is None:
            raise ValueError(f"Unknown task name: {task_name}")

        # Get the task
        task = self._app.tasks.get(full_task_name)
        if task is None:
            # Task not registered, send by name
            result = self._app.send_task(
                full_task_name,
                args=(job_id,),
                kwargs=kwargs,
            )
        else:
            # Task registered, use delay
            result = task.apply_async(
                args=(job_id,),
                kwargs=kwargs,
            )

        return result.id

    async def get_status(self, task_id: str) -> dict[str, Any]:
        """Get task status.

        Args:
            task_id: ID of the task to check.

        Returns:
            Dictionary with status information:
            - status: "pending", "running", "completed", "failed", "cancelled"
            - result: Task result if completed
            - error: Error message if failed
            - progress: Progress percentage (0-100)
            - meta: Additional metadata
        """
        result = AsyncResult(task_id, app=self._app)

        # Map Celery state to our standardized state
        status = self.STATE_MAP.get(result.state, "unknown")

        response: dict[str, Any] = {
            "task_id": task_id,
            "status": status,
            "celery_state": result.state,
        }

        # Add result or error based on state
        if result.state == "SUCCESS":
            response["result"] = result.result
            response["progress"] = 100
        elif result.state == "FAILURE":
            response["error"] = str(result.result) if result.result else "Unknown error"
            response["progress"] = 0
        elif result.state == "PROGRESS":
            # Get progress from task meta
            meta = result.info or {}
            response["progress"] = int(meta.get("progress", 0) * 100)
            response["meta"] = meta
        else:
            response["progress"] = 0

        return response

    async def cancel(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: ID of the task to cancel.

        Returns:
            True if cancelled, False if not found or already completed.
        """
        result = AsyncResult(task_id, app=self._app)

        # Check if task is already done
        if result.state in ("SUCCESS", "FAILURE", "REVOKED"):
            return False

        # Revoke the task
        self._app.control.revoke(task_id, terminate=True)

        return True

    async def get_result(
        self,
        task_id: str,
        timeout: float | None = None,
    ) -> Any:
        """Wait for and get task result.

        Args:
            task_id: ID of the task.
            timeout: Maximum time to wait in seconds. None means wait forever.

        Returns:
            Task result.

        Raises:
            TimeoutError: If timeout is exceeded.
            TaskError: If task failed.
            TaskNotFoundError: If task not found.
        """
        result = AsyncResult(task_id, app=self._app)

        try:
            # Wait for result with timeout
            return result.get(timeout=timeout, propagate=False)
        except TimeoutError:
            raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")
        except Exception as e:
            if result.state == "FAILURE":
                raise TaskError(f"Task {task_id} failed: {result.result}")
            raise TaskError(f"Error getting result for task {task_id}: {e}")

    def get_task_info(self, task_id: str) -> dict[str, Any]:
        """Get detailed task information.

        Args:
            task_id: ID of the task.

        Returns:
            Dictionary with detailed task information.
        """
        result = AsyncResult(task_id, app=self._app)

        return {
            "task_id": task_id,
            "state": result.state,
            "status": self.STATE_MAP.get(result.state, "unknown"),
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
            "result": result.result if result.ready() else None,
            "info": result.info,
            "traceback": result.traceback if result.failed() else None,
        }

    def purge_queue(self, queue_name: str | None = None) -> int:
        """Purge all pending tasks from a queue.

        Args:
            queue_name: Name of queue to purge. None purges default queue.

        Returns:
            Number of tasks purged.
        """
        queue = queue_name or self._config.task_default_queue
        return self._app.control.purge() or 0


@lru_cache
def get_task_queue() -> CeleryTaskQueue:
    """Get the cached CeleryTaskQueue instance.

    Returns:
        Singleton CeleryTaskQueue.
    """
    return CeleryTaskQueue()


def clear_task_queue_cache() -> None:
    """Clear the cached task queue instance.

    Useful for testing.
    """
    get_task_queue.cache_clear()
