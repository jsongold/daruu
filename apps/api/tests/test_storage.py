"""Tests for in-memory storage layer."""

from datetime import datetime

import pytest
from app.infrastructure.repositories.memory_repository import (
    MemoryDocumentRepository,
    MemoryEventPublisher,
    MemoryFileRepository,
    MemoryJobRepository,
)
from app.models import (
    Activity,
    ActivityAction,
    DocumentMeta,
    DocumentType,
    Evidence,
    Extraction,
    FieldModel,
    FieldType,
    Issue,
    IssueSeverity,
    IssueType,
    JobMode,
    JobStatus,
    Mapping,
)


class TestMemoryDocumentRepository:
    """Tests for MemoryDocumentRepository."""

    def test_create_document(self) -> None:
        """Test creating a document."""
        repo = MemoryDocumentRepository()
        meta = DocumentMeta(
            page_count=5,
            file_size=1024,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        doc = repo.create(
            document_type=DocumentType.SOURCE,
            meta=meta,
            ref="/path/to/file.pdf",
        )
        assert doc.id is not None
        assert doc.document_type == DocumentType.SOURCE
        assert doc.meta == meta
        assert doc.ref == "/path/to/file.pdf"

    def test_get_document(self) -> None:
        """Test getting a document by ID."""
        repo = MemoryDocumentRepository()
        meta = DocumentMeta(
            page_count=1,
            file_size=100,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        created = repo.create(DocumentType.TARGET, meta, "/path")
        retrieved = repo.get(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_get_nonexistent_document(self) -> None:
        """Test getting a document that doesn't exist."""
        repo = MemoryDocumentRepository()
        result = repo.get("nonexistent")
        assert result is None

    def test_list_all_documents(self) -> None:
        """Test listing all documents."""
        repo = MemoryDocumentRepository()
        meta = DocumentMeta(
            page_count=1,
            file_size=100,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        repo.create(DocumentType.SOURCE, meta, "/path1")
        repo.create(DocumentType.TARGET, meta, "/path2")
        docs = repo.list_all()
        assert len(docs) == 2

    def test_delete_document(self) -> None:
        """Test deleting a document."""
        repo = MemoryDocumentRepository()
        meta = DocumentMeta(
            page_count=1,
            file_size=100,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        doc = repo.create(DocumentType.SOURCE, meta, "/path")
        assert repo.delete(doc.id) is True
        assert repo.get(doc.id) is None
        assert repo.delete(doc.id) is False  # Already deleted


class TestMemoryJobRepository:
    """Tests for MemoryJobRepository."""

    @pytest.fixture
    def document_repository(self) -> MemoryDocumentRepository:
        """Create a document store with sample documents."""
        repo = MemoryDocumentRepository()
        meta = DocumentMeta(
            page_count=1,
            file_size=100,
            mime_type="application/pdf",
            filename="test.pdf",
        )
        repo.create(DocumentType.SOURCE, meta, "/source")
        repo.create(DocumentType.TARGET, meta, "/target")
        return repo

    def test_create_job(self, document_repository: MemoryDocumentRepository) -> None:
        """Test creating a job."""
        job_repository = MemoryJobRepository()
        docs = document_repository.list_all()
        target = docs[0]

        job = job_repository.create(
            mode=JobMode.SCRATCH,
            target_document=target,
        )
        assert job.id is not None
        assert job.mode == JobMode.SCRATCH
        assert job.status == JobStatus.CREATED
        assert job.target_document == target
        assert job.source_document is None

    def test_create_transfer_job(self, document_repository: MemoryDocumentRepository) -> None:
        """Test creating a transfer job."""
        job_repository = MemoryJobRepository()
        docs = document_repository.list_all()
        source = docs[0]
        target = docs[1]

        job = job_repository.create(
            mode=JobMode.TRANSFER,
            target_document=target,
            source_document=source,
        )
        assert job.source_document == source
        assert job.target_document == target

    def test_get_job(self, document_repository: MemoryDocumentRepository) -> None:
        """Test getting a job by ID."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        created = job_repository.create(JobMode.SCRATCH, target)

        retrieved = job_repository.get(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_update_job(self, document_repository: MemoryDocumentRepository) -> None:
        """Test updating a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        updated = job_repository.update(job.id, status=JobStatus.RUNNING, progress=0.5)
        assert updated is not None
        assert updated.status == JobStatus.RUNNING
        assert updated.progress == 0.5
        # Verify immutability (original job unchanged in memory reference)
        assert job.status == JobStatus.CREATED

    def test_add_field(self, document_repository: MemoryDocumentRepository) -> None:
        """Test adding a field to a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        field = FieldModel(
            id="field-1",
            name="Test Field",
            field_type=FieldType.TEXT,
            document_id=target.id,
            page=1,
        )
        updated = job_repository.add_field(job.id, field)
        assert updated is not None
        assert len(updated.fields) == 1
        assert updated.fields[0].id == "field-1"

    def test_update_field(self, document_repository: MemoryDocumentRepository) -> None:
        """Test updating a field in a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        field = FieldModel(
            id="field-1",
            name="Test Field",
            field_type=FieldType.TEXT,
            document_id=target.id,
            page=1,
        )
        job_repository.add_field(job.id, field)
        updated = job_repository.update_field(job.id, "field-1", value="New Value")

        assert updated is not None
        assert updated.fields[0].value == "New Value"

    def test_add_mapping(self, document_repository: MemoryDocumentRepository) -> None:
        """Test adding a mapping to a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        mapping = Mapping(
            id="map-1",
            source_field_id="src-1",
            target_field_id="tgt-1",
            confidence=0.9,
        )
        updated = job_repository.add_mapping(job.id, mapping)
        assert updated is not None
        assert len(updated.mappings) == 1

    def test_add_extraction(self, document_repository: MemoryDocumentRepository) -> None:
        """Test adding an extraction to a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        extraction = Extraction(
            id="ext-1",
            field_id="field-1",
            value="Extracted",
            confidence=0.85,
        )
        updated = job_repository.add_extraction(job.id, extraction)
        assert updated is not None
        assert len(updated.extractions) == 1

    def test_add_evidence(self, document_repository: MemoryDocumentRepository) -> None:
        """Test adding evidence to a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        evidence = Evidence(
            id="ev-1",
            field_id="field-1",
            source="ocr",
            confidence=0.9,
            document_id=target.id,
        )
        updated = job_repository.add_evidence(job.id, evidence)
        assert updated is not None
        assert len(updated.evidence) == 1

    def test_add_issue(self, document_repository: MemoryDocumentRepository) -> None:
        """Test adding an issue to a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        issue = Issue(
            id="issue-1",
            field_id="field-1",
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Low confidence",
            severity=IssueSeverity.WARNING,
        )
        updated = job_repository.add_issue(job.id, issue)
        assert updated is not None
        assert len(updated.issues) == 1

    def test_clear_issues(self, document_repository: MemoryDocumentRepository) -> None:
        """Test clearing issues from a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        issue = Issue(
            id="issue-1",
            field_id="field-1",
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Low confidence",
            severity=IssueSeverity.WARNING,
        )
        job_repository.add_issue(job.id, issue)
        updated = job_repository.clear_issues(job.id)
        assert updated is not None
        assert len(updated.issues) == 0

    def test_add_activity(self, document_repository: MemoryDocumentRepository) -> None:
        """Test adding an activity to a job."""
        job_repository = MemoryJobRepository()
        target = document_repository.list_all()[0]
        job = job_repository.create(JobMode.SCRATCH, target)

        activity = Activity(
            id="act-1",
            timestamp=datetime.utcnow(),
            action=ActivityAction.EXTRACTION_STARTED,
            details={"phase": "test"},
        )
        updated = job_repository.add_activity(job.id, activity)
        assert updated is not None
        # Should have 2 activities (job_created + new one)
        assert len(updated.activities) == 2


class TestMemoryFileRepository:
    """Tests for MemoryFileRepository."""

    def test_store_and_get_file(self, tmp_path) -> None:
        """Test storing and retrieving a file."""
        repo = MemoryFileRepository(base_path=tmp_path)
        content = b"test content"
        path = repo.store("file-1", content, "test.pdf")

        assert path.exists()
        retrieved = repo.get("file-1")
        assert retrieved == content

    def test_get_nonexistent_file(self, tmp_path) -> None:
        """Test getting a file that doesn't exist."""
        repo = MemoryFileRepository(base_path=tmp_path)
        result = repo.get("nonexistent")
        assert result is None

    def test_delete_file(self, tmp_path) -> None:
        """Test deleting a file."""
        repo = MemoryFileRepository(base_path=tmp_path)
        content = b"test content"
        repo.store("file-1", content, "test.pdf")

        assert repo.delete("file-1") is True
        assert repo.get("file-1") is None
        assert repo.delete("file-1") is False

    def test_store_preview(self, tmp_path) -> None:
        """Test storing a page preview."""
        repo = MemoryFileRepository(base_path=tmp_path)
        content = b"preview content"
        path = repo.store_preview("doc-1", 1, content)

        assert path.exists()
        preview_path = repo.get_preview_path("doc-1", 1)
        assert preview_path is not None
        assert preview_path.read_bytes() == content

    def test_get_preview_nonexistent(self, tmp_path) -> None:
        """Test getting a preview that doesn't exist."""
        repo = MemoryFileRepository(base_path=tmp_path)
        result = repo.get_preview_path("doc-1", 1)
        assert result is None


class TestMemoryEventPublisher:
    """Tests for MemoryEventPublisher."""

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self) -> None:
        """Test subscribing and receiving events."""
        publisher = MemoryEventPublisher()
        queue = publisher.subscribe("job-1")

        await publisher.publish("job-1", {"event": "test", "data": "value"})

        event = await queue.get()
        assert event["event"] == "test"
        assert event["data"] == "value"

    def test_publish_sync(self) -> None:
        """Test synchronous publish."""
        publisher = MemoryEventPublisher()
        queue = publisher.subscribe("job-1")

        publisher.publish_sync("job-1", {"event": "sync_test"})

        event = queue.get_nowait()
        assert event["event"] == "sync_test"

    def test_unsubscribe(self) -> None:
        """Test unsubscribing from events."""
        publisher = MemoryEventPublisher()
        queue = publisher.subscribe("job-1")
        publisher.unsubscribe("job-1", queue)

        # Should not raise even if queue is removed
        publisher.publish_sync("job-1", {"event": "test"})
        assert queue.empty()

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        """Test multiple subscribers receive events."""
        publisher = MemoryEventPublisher()
        queue1 = publisher.subscribe("job-1")
        queue2 = publisher.subscribe("job-1")

        await publisher.publish("job-1", {"event": "broadcast"})

        event1 = await queue1.get()
        event2 = await queue2.get()
        assert event1["event"] == "broadcast"
        assert event2["event"] == "broadcast"
