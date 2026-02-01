"""In-memory job storage for MVP.

This module provides a simple in-memory storage for job contexts.
In production, this would be replaced with Redis or another persistent store.
"""

from datetime import datetime
from typing import Protocol
from uuid import uuid4

from app.models.job_context import (
    JobContext,
    JobCreate,
    JobMode,
    JobStatus,
    JobSummary,
    JobThresholds,
)


class JobStoreProtocol(Protocol):
    """Protocol defining the job store interface.

    This allows for easy swapping of storage implementations.
    """

    async def create(self, job_create: JobCreate) -> JobContext:
        """Create a new job.

        Args:
            job_create: Job creation request

        Returns:
            Created job context
        """
        ...

    async def get(self, job_id: str) -> JobContext | None:
        """Get a job by ID.

        Args:
            job_id: Unique job identifier

        Returns:
            Job context if found, None otherwise
        """
        ...

    async def update(self, job_context: JobContext) -> JobContext:
        """Update a job.

        Args:
            job_context: Updated job context

        Returns:
            Updated job context
        """
        ...

    async def delete(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Unique job identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobSummary]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of job summaries
        """
        ...


class InMemoryJobStore:
    """In-memory job storage implementation.

    Thread-safe for basic operations but not suitable for production.
    Use Redis or another distributed store for production deployments.
    """

    def __init__(self) -> None:
        """Initialize empty job store."""
        self._jobs: dict[str, JobContext] = {}

    async def create(self, job_create: JobCreate) -> JobContext:
        """Create a new job from the creation request.

        Args:
            job_create: Job creation request with mode, documents, etc.

        Returns:
            Newly created job context with generated ID

        Raises:
            ValueError: If source document required but not provided
        """
        if job_create.mode == JobMode.TRANSFER and not job_create.source_document_id:
            raise ValueError("Source document ID required for transfer mode")

        job_id = str(uuid4())
        now = datetime.utcnow()

        # Build thresholds from request or defaults
        thresholds = job_create.thresholds or JobThresholds()

        job_context = JobContext(
            id=job_id,
            mode=job_create.mode,
            status=JobStatus.CREATED,
            source_document=None,  # Will be populated by ingest stage
            target_document=None,  # Will be populated by ingest stage
            source_fields=[],
            target_fields=[],
            mappings=[],
            extractions=[],
            evidence=[],
            issues=[],
            activities=[],
            current_stage=None,
            completed_stages=[],
            stage_results=[],
            iteration_count=0,
            max_iterations=job_create.max_iterations,
            previous_confidence=None,
            thresholds=thresholds,
            rules=job_create.rules or {},
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            progress=0.0,
        )

        self._jobs[job_id] = job_context
        return job_context

    async def get(self, job_id: str) -> JobContext | None:
        """Get a job by ID.

        Args:
            job_id: Unique job identifier

        Returns:
            Job context if found, None otherwise
        """
        return self._jobs.get(job_id)

    async def update(self, job_context: JobContext) -> JobContext:
        """Update a job.

        Since JobContext is immutable (frozen=True), this replaces
        the entire context in storage.

        Args:
            job_context: Updated job context

        Returns:
            Updated job context

        Raises:
            KeyError: If job not found
        """
        if job_context.id not in self._jobs:
            raise KeyError(f"Job {job_context.id} not found")

        # Create new context with updated timestamp
        updated_context = JobContext(
            **{
                **job_context.model_dump(),
                "updated_at": datetime.utcnow(),
            }
        )

        self._jobs[job_context.id] = updated_context
        return updated_context

    async def delete(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Unique job identifier

        Returns:
            True if deleted, False if not found
        """
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[JobSummary]:
        """List jobs with optional filtering.

        Args:
            status: Filter by status
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of job summaries sorted by created_at descending
        """
        jobs = list(self._jobs.values())

        # Filter by status if specified
        if status is not None:
            jobs = [j for j in jobs if j.status == status]

        # Sort by created_at descending (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        # Apply pagination
        paginated = jobs[offset : offset + limit]

        # Convert to summaries
        return [
            JobSummary(
                id=j.id,
                mode=j.mode,
                status=j.status,
                progress=j.progress,
                current_stage=j.current_stage,
                issue_count=len(j.issues),
                created_at=j.created_at,
                updated_at=j.updated_at,
            )
            for j in paginated
        ]

    async def clear(self) -> None:
        """Clear all jobs from storage.

        Primarily used for testing.
        """
        self._jobs.clear()

    @property
    def count(self) -> int:
        """Get the number of jobs in storage.

        Returns:
            Number of jobs
        """
        return len(self._jobs)


# Global store instance for dependency injection
_job_store: InMemoryJobStore | None = None


def get_job_store() -> InMemoryJobStore:
    """Get the global job store instance.

    Returns:
        Job store instance
    """
    global _job_store
    if _job_store is None:
        _job_store = InMemoryJobStore()
    return _job_store


def reset_job_store() -> None:
    """Reset the global job store.

    Primarily used for testing.
    """
    global _job_store
    _job_store = None
