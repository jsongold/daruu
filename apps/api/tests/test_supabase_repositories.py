"""Tests for Supabase repository implementations.

These tests verify that the Supabase repository classes correctly implement
the repository protocols and properly convert data between models and database rows.
"""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from app.models import (
    DocumentMeta,
    DocumentType,
    FieldType,
    IssueSeverity,
    IssueType,
)


class TestSupabaseDocumentRepository:
    """Tests for SupabaseDocumentRepository."""

    def test_to_document_conversion(self) -> None:
        """Test that database rows are correctly converted to Document models."""
        from app.repositories.supabase.document_repository import (
            SupabaseDocumentRepository,
        )

        # Create a mock row
        row = {
            "id": str(uuid4()),
            "ref": "supabase://documents/test.pdf",
            "document_type": "source",
            "meta": {
                "page_count": 10,
                "file_size": 12345,
                "mime_type": "application/pdf",
                "filename": "test.pdf",
                "has_password": False,
                "has_acroform": True,
            },
            "created_at": "2024-01-15T10:30:00+00:00",
        }

        # Mock the client
        with patch("app.repositories.supabase.document_repository.get_supabase_client"):
            repo = SupabaseDocumentRepository()
            doc = repo._to_document(row)

        assert doc.id == row["id"]
        assert doc.ref == row["ref"]
        assert doc.document_type == DocumentType.SOURCE
        assert doc.meta.page_count == 10
        assert doc.meta.file_size == 12345
        assert doc.meta.has_acroform is True

    def test_to_row_conversion(self) -> None:
        """Test that document data is correctly converted to database rows."""
        from app.repositories.supabase.document_repository import (
            SupabaseDocumentRepository,
        )

        meta = DocumentMeta(
            page_count=5,
            file_size=5000,
            mime_type="application/pdf",
            filename="test.pdf",
            has_password=False,
            has_acroform=False,
        )

        with patch("app.repositories.supabase.document_repository.get_supabase_client"):
            repo = SupabaseDocumentRepository()
            row = repo._to_row(DocumentType.TARGET, meta, "supabase://docs/test.pdf", "doc-123")

        assert row["id"] == "doc-123"
        assert row["ref"] == "supabase://docs/test.pdf"
        assert row["document_type"] == "target"
        assert row["meta"]["page_count"] == 5


class TestSupabaseJobRepository:
    """Tests for SupabaseJobRepository."""

    def test_to_field_conversion(self) -> None:
        """Test that field rows are correctly converted to FieldModel."""
        from app.repositories.supabase.job_repository import SupabaseJobRepository

        row = {
            "id": str(uuid4()),
            "name": "First Name",
            "field_type": "text",
            "value": "John",
            "confidence": 0.95,
            "bbox": {"x": 100, "y": 200, "width": 150, "height": 20, "page": 1},
            "document_id": str(uuid4()),
            "page": 1,
            "is_required": True,
            "is_editable": True,
        }

        with patch("app.repositories.supabase.job_repository.get_supabase_client"):
            repo = SupabaseJobRepository()
            field = repo._to_field(row)

        assert field.id == row["id"]
        assert field.name == "First Name"
        assert field.field_type == FieldType.TEXT
        assert field.value == "John"
        assert field.confidence == 0.95
        assert field.bbox is not None
        assert field.bbox.x == 100

    def test_to_issue_conversion(self) -> None:
        """Test that issue rows are correctly converted to Issue models."""
        from app.repositories.supabase.job_repository import SupabaseJobRepository

        row = {
            "id": str(uuid4()),
            "field_id": str(uuid4()),
            "issue_type": "low_confidence",
            "message": "Low confidence value",
            "severity": "warning",
            "suggested_action": "Review the extracted value",
        }

        with patch("app.repositories.supabase.job_repository.get_supabase_client"):
            repo = SupabaseJobRepository()
            issue = repo._to_issue(row)

        assert issue.id == row["id"]
        assert issue.issue_type == IssueType.LOW_CONFIDENCE
        assert issue.severity == IssueSeverity.WARNING
        assert issue.suggested_action == "Review the extracted value"

    def test_to_cost_summary_conversion(self) -> None:
        """Test that cost data is correctly converted to CostSummaryModel."""
        from app.repositories.supabase.job_repository import SupabaseJobRepository

        cost_data = {
            "llm_tokens_input": 1000,
            "llm_tokens_output": 500,
            "llm_calls": 5,
            "ocr_pages_processed": 10,
            "estimated_cost_usd": 0.05,
            "breakdown": {
                "llm_cost_usd": 0.04,
                "ocr_cost_usd": 0.01,
                "storage_cost_usd": 0.0,
            },
            "model_name": "gpt-4o-mini",
        }

        with patch("app.repositories.supabase.job_repository.get_supabase_client"):
            repo = SupabaseJobRepository()
            cost = repo._to_cost_summary(cost_data)

        assert cost.llm_tokens_input == 1000
        assert cost.llm_tokens_output == 500
        assert cost.llm_calls == 5
        assert cost.estimated_cost_usd == 0.05
        assert cost.breakdown.llm_cost_usd == 0.04

    def test_empty_cost_summary(self) -> None:
        """Test that empty cost data returns empty CostSummaryModel."""
        from app.repositories.supabase.job_repository import SupabaseJobRepository

        with patch("app.repositories.supabase.job_repository.get_supabase_client"):
            repo = SupabaseJobRepository()
            cost = repo._to_cost_summary({})

        assert cost.llm_tokens_input == 0
        assert cost.estimated_cost_usd == 0.0


class TestSupabaseFileRepository:
    """Tests for SupabaseFileRepository."""

    def test_get_content_parses_supabase_url(self) -> None:
        """Test that supabase:// URLs are correctly parsed."""
        from app.repositories.supabase.file_repository import SupabaseFileRepository

        # The method should parse supabase://bucket/path correctly
        ref = "supabase://documents/doc-123/test.pdf"

        with (
            patch("app.repositories.supabase.file_repository.get_supabase_client") as mock_client,
            patch("app.repositories.supabase.file_repository.get_supabase_config") as mock_config,
        ):
            mock_config.return_value.bucket_documents = "documents"
            mock_bucket = MagicMock()
            mock_bucket.download.return_value = b"PDF content"
            mock_client.return_value.storage.from_.return_value = mock_bucket

            repo = SupabaseFileRepository()
            content = repo.get_content(ref)

            mock_client.return_value.storage.from_.assert_called_with("documents")
            mock_bucket.download.assert_called_with("doc-123/test.pdf")
            assert content == b"PDF content"

    def test_store_creates_correct_path(self) -> None:
        """Test that store creates the correct storage path."""
        from app.repositories.supabase.file_repository import SupabaseFileRepository

        with (
            patch("app.repositories.supabase.file_repository.get_supabase_client") as mock_client,
            patch("app.repositories.supabase.file_repository.get_supabase_config") as mock_config,
        ):
            mock_config.return_value.bucket_documents = "documents"
            mock_bucket = MagicMock()
            mock_client.return_value.storage.from_.return_value = mock_bucket

            repo = SupabaseFileRepository()
            path = repo.store("doc-123", b"PDF content", "test.pdf")

            assert "doc-123" in str(path)
            assert "test.pdf" in str(path)
            mock_bucket.upload.assert_called_once()


class TestRepositoryFactory:
    """Tests for the repository factory."""

    def test_memory_mode_returns_memory_repos(self) -> None:
        """Test that memory mode returns in-memory repositories."""
        from app.infrastructure.repositories.factory import (
            clear_repository_singletons,
            get_document_repository,
            get_file_repository,
            get_job_repository,
        )
        from app.infrastructure.repositories.memory_repository import (
            MemoryDocumentRepository,
            MemoryFileRepository,
            MemoryJobRepository,
        )

        clear_repository_singletons()

        doc_repo = get_document_repository(mode="memory")
        job_repo = get_job_repository(mode="memory")
        file_repo = get_file_repository(mode="memory")

        assert isinstance(doc_repo, MemoryDocumentRepository)
        assert isinstance(job_repo, MemoryJobRepository)
        assert isinstance(file_repo, MemoryFileRepository)

    def test_auto_mode_without_supabase_returns_memory(self) -> None:
        """Test that auto mode without Supabase config returns memory repos."""
        from app.infrastructure.repositories.factory import (
            clear_repository_singletons,
            get_document_repository,
        )
        from app.infrastructure.repositories.memory_repository import (
            MemoryDocumentRepository,
        )

        clear_repository_singletons()

        # Memory mode should work without Supabase configured
        with patch(
            "app.infrastructure.repositories.factory.is_supabase_configured",
            return_value=False,
        ):
            doc_repo = get_document_repository(mode="memory")
            assert isinstance(doc_repo, MemoryDocumentRepository)

    def test_default_mode_without_config_raises_error(self) -> None:
        """Test that default (supabase) mode without config raises RuntimeError."""
        from app.infrastructure.repositories.factory import (
            clear_repository_singletons,
            get_document_repository,
        )

        clear_repository_singletons()

        with (
            patch(
                "app.infrastructure.repositories.factory.is_supabase_configured",
                return_value=False,
            ),
            patch(
                "app.infrastructure.repositories.factory._is_test_mode",
                return_value=False,
            ),
        ):
            with pytest.raises(RuntimeError, match="Supabase is not configured"):
                get_document_repository()  # Default is supabase, should raise

    def test_get_active_mode(self) -> None:
        """Test get_active_mode returns supabase when configured."""
        from app.infrastructure.repositories.factory import get_active_mode

        with patch(
            "app.infrastructure.repositories.factory.is_supabase_configured",
            return_value=True,
        ):
            assert get_active_mode() == "supabase"

    def test_get_active_mode_raises_when_not_configured(self) -> None:
        """Test get_active_mode raises error when Supabase not configured."""
        from app.infrastructure.repositories.factory import get_active_mode

        with patch(
            "app.infrastructure.repositories.factory.is_supabase_configured",
            return_value=False,
        ):
            with pytest.raises(RuntimeError, match="Supabase is not configured"):
                get_active_mode()


class TestProtocolCompliance:
    """Tests to verify protocol compliance."""

    def test_document_repository_protocol(self) -> None:
        """Test SupabaseDocumentRepository implements DocumentRepository."""
        from app.repositories.supabase.document_repository import (
            SupabaseDocumentRepository,
        )

        with patch("app.repositories.supabase.document_repository.get_supabase_client"):
            repo = SupabaseDocumentRepository()

        # Check required methods exist
        assert hasattr(repo, "create")
        assert hasattr(repo, "get")
        assert hasattr(repo, "list_all")
        assert hasattr(repo, "delete")
        assert callable(repo.create)
        assert callable(repo.get)
        assert callable(repo.list_all)
        assert callable(repo.delete)

    def test_job_repository_protocol(self) -> None:
        """Test SupabaseJobRepository implements JobRepository."""
        from app.repositories.supabase.job_repository import SupabaseJobRepository

        with patch("app.repositories.supabase.job_repository.get_supabase_client"):
            repo = SupabaseJobRepository()

        # Check required methods exist
        assert hasattr(repo, "create")
        assert hasattr(repo, "get")
        assert hasattr(repo, "update")
        assert hasattr(repo, "add_activity")
        assert hasattr(repo, "add_field")
        assert hasattr(repo, "add_mapping")
        assert hasattr(repo, "add_issue")
        assert hasattr(repo, "clear_issues")
        assert hasattr(repo, "list_all")
        assert hasattr(repo, "delete")

    def test_file_repository_protocol(self) -> None:
        """Test SupabaseFileRepository implements FileRepository."""
        from app.repositories.supabase.file_repository import SupabaseFileRepository

        with (
            patch("app.repositories.supabase.file_repository.get_supabase_client"),
            patch("app.repositories.supabase.file_repository.get_supabase_config"),
        ):
            repo = SupabaseFileRepository()

        # Check required methods exist
        assert hasattr(repo, "store")
        assert hasattr(repo, "get")
        assert hasattr(repo, "get_path")
        assert hasattr(repo, "delete")
        assert hasattr(repo, "store_preview")
        assert hasattr(repo, "get_preview_path")
        assert hasattr(repo, "get_content")
