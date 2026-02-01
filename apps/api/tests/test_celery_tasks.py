"""Tests for Celery task processing.

These tests verify:
- Task configuration is correct
- Tasks execute properly
- Error handling and retries work
- Task queue implementation follows the protocol
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Check if Celery is available
try:
    import celery
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False

celery_required = pytest.mark.skipif(
    not CELERY_AVAILABLE,
    reason="Celery not installed",
)


@celery_required
class TestCeleryConfig:
    """Tests for Celery configuration."""

    def test_celery_config_defaults(self):
        """Test CeleryConfig has correct defaults."""
        from app.infrastructure.celery.config import CeleryConfig

        config = CeleryConfig()

        assert config.broker_url == "redis://localhost:6379/0"
        assert config.result_backend == "redis://localhost:6379/1"
        assert config.task_soft_time_limit == 300
        assert config.task_time_limit == 600
        assert config.worker_concurrency == 4

    def test_celery_config_to_celery_config(self):
        """Test conversion to Celery configuration dictionary."""
        from app.infrastructure.celery.config import CeleryConfig

        config = CeleryConfig()
        celery_config = config.to_celery_config()

        assert "broker_url" in celery_config
        assert "result_backend" in celery_config
        assert "task_routes" in celery_config
        assert celery_config["timezone"] == "UTC"
        assert celery_config["task_track_started"] is True

    def test_celery_config_from_env(self, monkeypatch):
        """Test CeleryConfig loads from environment."""
        from app.infrastructure.celery.config import (
            CeleryConfig,
            clear_celery_config_cache,
        )

        clear_celery_config_cache()
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://custom:6379/0")
        monkeypatch.setenv("CELERY_WORKER_CONCURRENCY", "8")

        config = CeleryConfig()

        assert config.broker_url == "redis://custom:6379/0"
        assert config.worker_concurrency == 8

    def test_task_progress_config(self):
        """Test TaskProgressConfig has correct defaults."""
        from app.infrastructure.celery.config import TaskProgressConfig

        config = TaskProgressConfig()

        assert config.ingest_start == 0.0
        assert config.ingest_complete == 0.10
        assert config.review_complete == 1.0


@celery_required
class TestCeleryTaskQueue:
    """Tests for CeleryTaskQueue implementation."""

    @pytest.fixture
    def mock_celery_app(self):
        """Create a mock Celery app."""
        mock_app = MagicMock()
        mock_app.tasks = {}
        mock_app.control = MagicMock()
        return mock_app

    @pytest.fixture
    def task_queue(self, mock_celery_app):
        """Create a CeleryTaskQueue with mocked app."""
        from app.infrastructure.celery.task_queue import CeleryTaskQueue

        with patch(
            "app.infrastructure.celery.task_queue.get_celery_app",
            return_value=mock_celery_app,
        ):
            queue = CeleryTaskQueue()
            return queue

    @pytest.mark.asyncio
    async def test_enqueue_process_job(self, task_queue, mock_celery_app):
        """Test enqueueing a process_job task."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_celery_app.send_task.return_value = mock_result

        # Enqueue task
        task_id = await task_queue.enqueue(
            "process_job",
            "job-456",
            run_mode="until_done",
        )

        assert task_id == "task-123"
        mock_celery_app.send_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_unknown_task_raises(self, task_queue):
        """Test that enqueueing unknown task raises ValueError."""
        with pytest.raises(ValueError, match="Unknown task name"):
            await task_queue.enqueue("unknown_task", "job-123")

    @pytest.mark.asyncio
    async def test_get_status_pending(self, task_queue, mock_celery_app):
        """Test getting status of pending task."""
        from celery.result import AsyncResult

        with patch.object(AsyncResult, "__init__", return_value=None):
            with patch.object(AsyncResult, "state", "PENDING", create=True):
                status = await task_queue.get_status("task-123")

        assert status["status"] == "pending"
        assert status["task_id"] == "task-123"

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_queue, mock_celery_app):
        """Test cancelling a task."""
        from celery.result import AsyncResult

        with patch.object(AsyncResult, "__init__", return_value=None):
            with patch.object(AsyncResult, "state", "PENDING", create=True):
                result = await task_queue.cancel("task-123")

        assert result is True
        mock_celery_app.control.revoke.assert_called_with("task-123", terminate=True)


@celery_required
class TestProcessJobTask:
    """Tests for process_job_task."""

    @pytest.fixture
    def mock_job_repository(self):
        """Create mock job repository."""
        mock_repo = MagicMock()
        return mock_repo

    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        mock_pub = MagicMock()
        return mock_pub

    def test_task_is_registered(self):
        """Test that process_job_task is properly defined."""
        from app.infrastructure.celery.tasks import process_job_task

        assert process_job_task.name == "app.infrastructure.celery.tasks.process_job_task"
        assert process_job_task.max_retries == 3

    def test_task_has_retry_config(self):
        """Test that task has retry configuration."""
        from app.infrastructure.celery.tasks import process_job_task

        # Check that retry is configured
        assert hasattr(process_job_task, "autoretry_for")

    @patch("app.infrastructure.celery.tasks.get_job_repository")
    @patch("app.infrastructure.celery.tasks.get_event_publisher")
    def test_task_handles_missing_job(
        self,
        mock_get_publisher,
        mock_get_repo,
        mock_job_repository,
    ):
        """Test task handles missing job gracefully."""
        from app.infrastructure.celery.tasks import process_job_task

        mock_job_repository.get.return_value = None
        mock_get_repo.return_value = mock_job_repository

        # Create mock task self
        mock_self = MagicMock()
        mock_self.update_state = MagicMock()

        # Run task with bound=True workaround
        result = process_job_task.__wrapped__(mock_self, "nonexistent-job")

        assert result["success"] is False
        assert "not found" in result["error"]


@celery_required
class TestIngestDocumentTask:
    """Tests for ingest_document_task."""

    def test_task_is_registered(self):
        """Test that ingest_document_task is properly defined."""
        from app.infrastructure.celery.tasks import ingest_document_task

        assert (
            ingest_document_task.name
            == "app.infrastructure.celery.tasks.ingest_document_task"
        )
        assert ingest_document_task.max_retries == 3


@celery_required
class TestTaskHelpers:
    """Tests for task helper functions."""

    def test_run_async_creates_loop_when_needed(self):
        """Test _run_async creates event loop when none exists."""
        from app.infrastructure.celery.tasks import _run_async

        async def sample_coro():
            return "result"

        result = _run_async(sample_coro())
        assert result == "result"

    def test_update_task_progress(self):
        """Test update_task_progress helper."""
        from app.infrastructure.celery.tasks import update_task_progress

        mock_task = MagicMock()

        with patch("app.infrastructure.celery.tasks.get_event_publisher"):
            update_task_progress(
                mock_task,
                "job-123",
                0.5,
                "extraction",
                "Extracting fields...",
            )

        mock_task.update_state.assert_called_once()
        call_kwargs = mock_task.update_state.call_args[1]
        assert call_kwargs["state"] == "PROGRESS"
        assert call_kwargs["meta"]["progress"] == 0.5
        assert call_kwargs["meta"]["stage"] == "extraction"


class TestAsyncJobEndpoints:
    """Tests for async job API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from app.main import app

        return TestClient(app)

    @pytest.fixture
    def sample_job(self, client, api_prefix, sample_pdf_content):
        """Create a sample job for testing."""
        from app.infrastructure.repositories import (
            get_document_repository,
            get_job_repository,
        )
        from app.models import Document, DocumentMeta, DocumentType, JobMode
        from uuid import uuid4

        doc_repo = get_document_repository()
        job_repo = get_job_repository()

        # Create document with proper metadata
        meta = DocumentMeta(
            page_count=1,
            file_size=len(sample_pdf_content),
            mime_type="application/pdf",
            filename="test.pdf",
        )
        doc = doc_repo.create(
            document_type=DocumentType.TARGET,
            meta=meta,
            ref="/tmp/test.pdf",
        )

        # Create job
        job = job_repo.create(
            mode=JobMode.SCRATCH,
            target_document=doc,
            source_document=None,
        )

        return job

    @pytest.fixture
    def api_prefix(self):
        """Get API prefix."""
        from app.config import get_settings

        return get_settings().api_prefix

    def test_run_async_returns_202(self, client, sample_job, api_prefix):
        """Test that POST /jobs/{id}/run/async returns 202 Accepted."""
        with patch(
            "app.routes.jobs._get_task_queue"
        ) as mock_get_queue:
            mock_queue = AsyncMock()
            mock_queue.enqueue.return_value = "task-123"
            mock_get_queue.return_value = mock_queue

            response = client.post(
                f"{api_prefix}/jobs/{sample_job.id}/run/async",
                json={"run_mode": "until_done"},
            )

        assert response.status_code == 202
        data = response.json()
        assert data["success"] is True
        assert data["data"]["job_id"] == sample_job.id
        assert data["data"]["task_id"] == "task-123"

    def test_run_async_not_available(self, client, sample_job, api_prefix):
        """Test that endpoint returns 503 when Celery not available."""
        with patch(
            "app.routes.jobs._get_task_queue",
            return_value=None,
        ):
            response = client.post(
                f"{api_prefix}/jobs/{sample_job.id}/run/async",
                json={"run_mode": "until_done"},
            )

        assert response.status_code == 503

    def test_get_task_status(self, client, sample_job, api_prefix):
        """Test GET /jobs/{id}/task/{task_id} returns status."""
        with patch(
            "app.routes.jobs._get_task_queue"
        ) as mock_get_queue:
            mock_queue = AsyncMock()
            mock_queue.get_status.return_value = {
                "status": "running",
                "progress": 50,
                "meta": {"stage": "extraction"},
            }
            mock_get_queue.return_value = mock_queue

            response = client.get(
                f"{api_prefix}/jobs/{sample_job.id}/task/task-123",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"
        assert data["data"]["progress"] == 50

    def test_cancel_task(self, client, sample_job, api_prefix):
        """Test DELETE /jobs/{id}/task/{task_id} cancels task."""
        with patch(
            "app.routes.jobs._get_task_queue"
        ) as mock_get_queue:
            mock_queue = AsyncMock()
            mock_queue.cancel.return_value = True
            mock_get_queue.return_value = mock_queue

            response = client.delete(
                f"{api_prefix}/jobs/{sample_job.id}/task/task-123",
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["cancelled"] is True

    def test_run_async_job_not_found(self, client, api_prefix):
        """Test that POST /jobs/{id}/run/async returns 404 for non-existent job."""
        response = client.post(
            f"{api_prefix}/jobs/nonexistent-job/run/async",
            json={"run_mode": "until_done"},
        )

        assert response.status_code == 404

    def test_run_async_job_already_done(self, client, sample_job, api_prefix):
        """Test that POST /jobs/{id}/run/async returns 409 for done job."""
        from app.infrastructure.repositories import get_job_repository
        from app.models import JobStatus

        # Mark job as done
        job_repo = get_job_repository()
        job_repo.update(sample_job.id, status=JobStatus.DONE)

        response = client.post(
            f"{api_prefix}/jobs/{sample_job.id}/run/async",
            json={"run_mode": "until_done"},
        )

        assert response.status_code == 409
