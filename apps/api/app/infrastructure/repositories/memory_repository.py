"""In-memory repository implementations (Adapters) for MVP.

These classes implement the repository interfaces defined in
`app.repositories`. They provide in-memory storage suitable
for development and testing. In production, swap for database-backed
implementations (e.g., SupabaseRepository).

Implements:
    - MemoryDocumentRepository -> DocumentRepository
    - MemoryJobRepository -> JobRepository
    - MemoryFileRepository -> FileRepository
    - MemoryEventPublisher -> EventPublisher
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import (
    Activity,
    ActivityAction,
    Document,
    DocumentMeta,
    DocumentType,
    Evidence,
    Extraction,
    FieldModel,
    Issue,
    JobContext,
    JobMode,
    JobStatus,
    Mapping,
)
from app.repositories import (
    DocumentRepository,
    EventPublisher,
    FileRepository,
    JobRepository,
)


class MemoryDocumentRepository:
    """In-memory implementation of DocumentRepository."""

    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def create(
        self,
        document_type: DocumentType,
        meta: DocumentMeta,
        ref: str,
    ) -> Document:
        """Create a new document record."""
        doc_id = str(uuid4())
        now = datetime.now(timezone.utc)
        document = Document(
            id=doc_id,
            ref=ref,
            document_type=document_type,
            meta=meta,
            created_at=now,
        )
        self._documents[doc_id] = document
        return document

    def get(self, document_id: str) -> Document | None:
        """Get a document by ID."""
        return self._documents.get(document_id)

    def list_all(self) -> list[Document]:
        """List all documents."""
        return list(self._documents.values())

    def delete(self, document_id: str) -> bool:
        """Delete a document by ID."""
        if document_id in self._documents:
            del self._documents[document_id]
            return True
        return False


# Ensure it satisfies the protocol
_assert_doc_repo: DocumentRepository = MemoryDocumentRepository()


class MemoryJobRepository:
    """In-memory implementation of JobRepository."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobContext] = {}

    def create(
        self,
        mode: JobMode,
        target_document: Document,
        source_document: Document | None = None,
    ) -> JobContext:
        """Create a new job."""
        job_id = str(uuid4())
        now = datetime.now(timezone.utc)

        initial_activity = Activity(
            id=str(uuid4()),
            timestamp=now,
            action=ActivityAction.JOB_CREATED,
            details={"mode": mode.value},
        )

        job = JobContext(
            id=job_id,
            mode=mode,
            status=JobStatus.CREATED,
            source_document=source_document,
            target_document=target_document,
            fields=[],
            mappings=[],
            extractions=[],
            evidence=[],
            issues=[],
            activities=[initial_activity],
            created_at=now,
            updated_at=now,
            progress=0.0,
            current_step="initialized",
            next_actions=["run"],
        )
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> JobContext | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def update(self, job_id: str, **updates: Any) -> JobContext | None:
        """Update a job with new values (immutable pattern)."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        # Create new job with updates (immutable)
        updated_data = job.model_dump()
        updated_data.update(updates)
        updated_data["updated_at"] = datetime.now(timezone.utc)

        new_job = JobContext(**updated_data)
        self._jobs[job_id] = new_job
        return new_job

    def add_activity(self, job_id: str, activity: Activity) -> JobContext | None:
        """Add an activity to a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_activities = [*job.activities, activity]
        return self.update(job_id, activities=new_activities)

    def add_field(self, job_id: str, field: FieldModel) -> JobContext | None:
        """Add a field to a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_fields = [*job.fields, field]
        return self.update(job_id, fields=new_fields)

    def update_field(self, job_id: str, field_id: str, **updates: Any) -> JobContext | None:
        """Update a field in a job (immutable)."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_fields = []
        found = False
        for f in job.fields:
            if f.id == field_id:
                field_data = f.model_dump()
                field_data.update(updates)
                new_fields.append(FieldModel(**field_data))
                found = True
            else:
                new_fields.append(f)

        if not found:
            return None

        return self.update(job_id, fields=new_fields)

    def add_mapping(self, job_id: str, mapping: Mapping) -> JobContext | None:
        """Add a mapping to a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_mappings = [*job.mappings, mapping]
        return self.update(job_id, mappings=new_mappings)

    def add_extraction(self, job_id: str, extraction: Extraction) -> JobContext | None:
        """Add an extraction to a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_extractions = [*job.extractions, extraction]
        return self.update(job_id, extractions=new_extractions)

    def add_evidence(self, job_id: str, evidence: Evidence) -> JobContext | None:
        """Add evidence to a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_evidence = [*job.evidence, evidence]
        return self.update(job_id, evidence=new_evidence)

    def add_issue(self, job_id: str, issue: Issue) -> JobContext | None:
        """Add an issue to a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_issues = [*job.issues, issue]
        return self.update(job_id, issues=new_issues)

    def clear_issues(self, job_id: str) -> JobContext | None:
        """Clear all issues from a job."""
        return self.update(job_id, issues=[])

    def remove_issue(self, job_id: str, issue_id: str) -> JobContext | None:
        """Remove a specific issue from a job."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        new_issues = [i for i in job.issues if i.id != issue_id]
        return self.update(job_id, issues=new_issues)

    def list_all(self) -> list[JobContext]:
        """List all jobs."""
        return list(self._jobs.values())

    def delete(self, job_id: str) -> bool:
        """Delete a job by ID."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False


# Ensure it satisfies the protocol
_assert_job_repo: JobRepository = MemoryJobRepository()


class MemoryFileRepository:
    """In-memory implementation of FileRepository."""

    def __init__(self, base_path: Path | None = None) -> None:
        self._base_path = base_path or Path("/tmp/daru-pdf-uploads")
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, bytes] = {}  # For small files, keep in memory
        self._file_paths: dict[str, Path] = {}  # For larger files, store on disk

    def store(self, file_id: str, content: bytes, filename: str) -> str:
        """Store file content and return the path."""
        file_path = self._base_path / file_id / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        self._file_paths[file_id] = file_path
        return str(file_path)

    def get(self, file_id: str) -> bytes | None:
        """Get file content by ID."""
        if file_id in self._files:
            return self._files[file_id]
        if file_id in self._file_paths:
            return self._file_paths[file_id].read_bytes()
        return None

    def get_path(self, file_id: str) -> str | None:
        """Get file path by ID."""
        path = self._file_paths.get(file_id)
        return str(path) if path else None

    def delete(self, file_id: str) -> bool:
        """Delete a file by ID."""
        if file_id in self._files:
            del self._files[file_id]
            return True
        if file_id in self._file_paths:
            path = self._file_paths[file_id]
            if path.exists():
                path.unlink()
            del self._file_paths[file_id]
            return True
        return False

    def store_preview(self, document_id: str, page: int, content: bytes) -> str:
        """Store a page preview image."""
        preview_path = self._base_path / document_id / "previews" / f"page_{page}.png"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_bytes(content)
        return str(preview_path)

    def get_preview_path(self, document_id: str, page: int) -> str | None:
        """Get the path to a page preview."""
        preview_path = self._base_path / document_id / "previews" / f"page_{page}.png"
        if preview_path.exists():
            return str(preview_path)
        return None

    def get_content(self, ref: str) -> bytes | None:
        """Get file content by file path reference."""
        path = Path(ref)
        if path.exists():
            return path.read_bytes()
        return None

    def get_preview_content(self, document_id: str, page: int) -> bytes | None:
        """Get preview image content."""
        preview_path = self._base_path / document_id / "previews" / f"page_{page}.png"
        if preview_path.exists():
            return preview_path.read_bytes()
        return None


# Ensure it satisfies the protocol
_assert_file_repo: FileRepository = MemoryFileRepository()


class MemoryEventPublisher:
    """In-memory implementation of EventPublisher."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Subscribe to events for a job."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Unsubscribe from events for a job."""
        if job_id in self._subscribers:
            try:
                self._subscribers[job_id].remove(queue)
            except ValueError:
                pass

    async def publish(self, job_id: str, event: dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        if job_id in self._subscribers:
            for queue in self._subscribers[job_id]:
                await queue.put(event)

    def publish_sync(self, job_id: str, event: dict[str, Any]) -> None:
        """Synchronously publish an event (creates task)."""
        if job_id in self._subscribers:
            for queue in self._subscribers[job_id]:
                queue.put_nowait(event)


# Ensure it satisfies the protocol
_assert_event_pub: EventPublisher = MemoryEventPublisher()


# Singleton instances
_document_repository: MemoryDocumentRepository | None = None
_job_repository: MemoryJobRepository | None = None
_file_repository: MemoryFileRepository | None = None
_event_publisher: MemoryEventPublisher | None = None


def get_document_repository() -> DocumentRepository:
    """Get the singleton document repository."""
    global _document_repository
    if _document_repository is None:
        _document_repository = MemoryDocumentRepository()
    return _document_repository


def get_job_repository() -> JobRepository:
    """Get the singleton job repository."""
    global _job_repository
    if _job_repository is None:
        _job_repository = MemoryJobRepository()
    return _job_repository


def get_file_repository() -> FileRepository:
    """Get the singleton file repository."""
    global _file_repository
    if _file_repository is None:
        _file_repository = MemoryFileRepository()
    return _file_repository


def get_event_publisher() -> EventPublisher:
    """Get the singleton event publisher."""
    global _event_publisher
    if _event_publisher is None:
        _event_publisher = MemoryEventPublisher()
    return _event_publisher
