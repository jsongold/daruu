"""Task Queue interface for async task processing.

This protocol defines the contract for async task queue operations.
Implementations can use Celery, RQ, or other task queue systems.

This is a stub interface for future implementation.
"""

from typing import Any, Protocol


class TaskQueue(Protocol):
    """Interface for async task queue (Celery/RQ).

    This interface supports:
    - Enqueueing tasks for background processing
    - Checking task status
    - Cancelling tasks

    Implementations should handle:
    - Task serialization/deserialization
    - Retry logic
    - Dead letter queue
    """

    async def enqueue(
        self,
        task_name: str,
        job_id: str,
        **kwargs: Any,
    ) -> str:
        """Enqueue a task for async processing.

        Args:
            task_name: Name of the task to execute.
            job_id: ID of the job this task belongs to.
            **kwargs: Additional arguments for the task.

        Returns:
            Task ID for tracking.
        """
        ...

    async def get_status(self, task_id: str) -> dict[str, Any]:
        """Get task status.

        Args:
            task_id: ID of the task to check.

        Returns:
            Dictionary with status information:
            - status: "pending", "running", "completed", "failed"
            - result: Task result if completed
            - error: Error message if failed
            - progress: Progress percentage (0-100)
        """
        ...

    async def cancel(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: ID of the task to cancel.

        Returns:
            True if cancelled, False if not found or already completed.
        """
        ...

    async def get_result(self, task_id: str, timeout: float | None = None) -> Any:
        """Wait for and get task result.

        Args:
            task_id: ID of the task.
            timeout: Maximum time to wait in seconds. None means wait forever.

        Returns:
            Task result.

        Raises:
            TimeoutError: If timeout is exceeded.
            TaskError: If task failed.
        """
        ...
