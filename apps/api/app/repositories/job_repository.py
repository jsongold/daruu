"""Job repository interface (Port).

This defines the contract for job persistence operations.
Implementations can be in-memory, database, or any other storage.
"""

from typing import Any, Protocol

from app.models import (
    Activity,
    Document,
    Evidence,
    Extraction,
    FieldModel,
    Issue,
    JobContext,
    JobMode,
    Mapping,
)


class JobRepository(Protocol):
    """Repository interface for Job entities.

    This protocol defines the contract that any job storage
    implementation must satisfy. All update operations follow
    immutable patterns - they return new objects rather than
    mutating existing ones.

    Example:
        class PostgresJobRepository:
            def create(self, ...) -> JobContext: ...
            def get(self, job_id: str) -> JobContext | None: ...
            # etc.

        # Inject into service
        orchestrator = Orchestrator(job_repo=PostgresJobRepository())
    """

    def create(
        self,
        mode: JobMode,
        target_document: Document,
        source_document: Document | None = None,
    ) -> JobContext:
        """Create a new job.

        Args:
            mode: Job mode (transfer/scratch).
            target_document: Target document to fill.
            source_document: Optional source document for transfer mode.

        Returns:
            Created JobContext with generated ID.
        """
        ...

    def get(self, job_id: str) -> JobContext | None:
        """Get a job by ID.

        Args:
            job_id: Unique job identifier.

        Returns:
            JobContext if found, None otherwise.
        """
        ...

    def update(self, job_id: str, **updates: Any) -> JobContext | None:
        """Update a job with new values (immutable pattern).

        Creates a new JobContext with the updates applied.
        The original is not mutated.

        Args:
            job_id: Unique job identifier.
            **updates: Fields to update.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def add_activity(self, job_id: str, activity: Activity) -> JobContext | None:
        """Add an activity to a job.

        Args:
            job_id: Unique job identifier.
            activity: Activity to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def add_field(self, job_id: str, field: FieldModel) -> JobContext | None:
        """Add a field to a job.

        Args:
            job_id: Unique job identifier.
            field: Field to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def update_field(self, job_id: str, field_id: str, **updates: Any) -> JobContext | None:
        """Update a field in a job (immutable).

        Args:
            job_id: Unique job identifier.
            field_id: Field identifier to update.
            **updates: Fields to update.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def add_mapping(self, job_id: str, mapping: Mapping) -> JobContext | None:
        """Add a mapping to a job.

        Args:
            job_id: Unique job identifier.
            mapping: Mapping to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def add_extraction(self, job_id: str, extraction: Extraction) -> JobContext | None:
        """Add an extraction to a job.

        Args:
            job_id: Unique job identifier.
            extraction: Extraction to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def add_evidence(self, job_id: str, evidence: Evidence) -> JobContext | None:
        """Add evidence to a job.

        Args:
            job_id: Unique job identifier.
            evidence: Evidence to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def add_issue(self, job_id: str, issue: Issue) -> JobContext | None:
        """Add an issue to a job.

        Args:
            job_id: Unique job identifier.
            issue: Issue to add.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def clear_issues(self, job_id: str) -> JobContext | None:
        """Clear all issues from a job.

        Args:
            job_id: Unique job identifier.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def remove_issue(self, job_id: str, issue_id: str) -> JobContext | None:
        """Remove a specific issue from a job.

        Args:
            job_id: Unique job identifier.
            issue_id: Issue identifier to remove.

        Returns:
            Updated JobContext if found, None otherwise.
        """
        ...

    def list_all(self) -> list[JobContext]:
        """List all jobs.

        Returns:
            List of all jobs.
        """
        ...

    def delete(self, job_id: str) -> bool:
        """Delete a job by ID.

        Args:
            job_id: Unique job identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...
