"""Pytest configuration and fixtures."""

import os

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

# Set test mode BEFORE importing app modules
# This ensures memory repositories are used instead of Supabase
os.environ["DARU_REPOSITORY_MODE"] = "memory"

from app.config import get_settings
from app.main import app


@pytest.fixture(autouse=True)
def reset_repositories() -> None:
    """Reset all in-memory repositories before each test.

    Skipped silently when old repository modules are unavailable
    (e.g. on the simple-version branch).
    """
    try:
        import app.infrastructure.repositories.memory_repository as repo_module
        from app.infrastructure.repositories import factory
    except (ImportError, ModuleNotFoundError):
        return

    # Clear factory singletons
    factory.clear_repository_singletons()

    # Reset memory repository singleton instances
    repo_module._document_repository = None
    repo_module._job_repository = None
    repo_module._file_repository = None
    repo_module._event_publisher = None


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncClient:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def settings():
    """Get application settings."""
    return get_settings()


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Create sample PDF content for testing."""
    # Minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF"""


@pytest.fixture
def api_prefix(settings) -> str:
    """Get API prefix."""
    return settings.api_prefix


# =============================================================================
# Celery Fixtures (only when Celery is available)
# =============================================================================

try:
    from celery import Celery

    @pytest.fixture
    def celery_config():
        """Configure Celery for testing with eager execution."""
        return {
            "broker_url": "memory://",
            "result_backend": "cache+memory://",
            "task_always_eager": True,
            "task_eager_propagates": True,
        }

    @pytest.fixture
    def celery_app(celery_config):
        """Create a test Celery app with eager execution."""

        app = Celery("test")
        app.config_from_object(celery_config)

        # Auto-discover tasks
        app.autodiscover_tasks(["app.infrastructure.celery"])

        return app

    @pytest.fixture
    def mock_task_queue():
        """Create a mock task queue for testing without Celery."""
        from unittest.mock import AsyncMock

        mock = AsyncMock()
        mock.enqueue.return_value = "mock-task-id"
        mock.get_status.return_value = {
            "status": "completed",
            "progress": 100,
            "result": {"success": True},
        }
        mock.cancel.return_value = True
        return mock

except ImportError:
    # Celery not installed, skip Celery fixtures
    pass
