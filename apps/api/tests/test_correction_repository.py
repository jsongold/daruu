"""Tests for MemoryCorrectionRepository."""

from datetime import datetime, timedelta

import pytest
from app.domain.models.correction_record import CorrectionCategory, CorrectionRecord
from app.infrastructure.repositories.memory_correction_repository import (
    MemoryCorrectionRepository,
)


@pytest.fixture
def repo():
    return MemoryCorrectionRepository()


def _make_correction(
    document_id: str = "doc-1",
    field_id: str = "name",
    timestamp: datetime | None = None,
) -> CorrectionRecord:
    return CorrectionRecord(
        document_id=document_id,
        field_id=field_id,
        original_value="old",
        corrected_value="new",
        category=CorrectionCategory.WRONG_VALUE,
        timestamp=timestamp or datetime.utcnow(),
    )


class TestMemoryCorrectionRepository:
    def test_create_returns_correction(self, repo):
        correction = _make_correction()
        result = repo.create(correction)
        assert result.document_id == "doc-1"
        assert result.field_id == "name"

    def test_list_by_document_filters(self, repo):
        repo.create(_make_correction(document_id="doc-1", field_id="name"))
        repo.create(_make_correction(document_id="doc-2", field_id="date"))
        repo.create(_make_correction(document_id="doc-1", field_id="address"))

        result = repo.list_by_document("doc-1")
        assert len(result) == 2
        assert all(r.document_id == "doc-1" for r in result)

    def test_list_by_document_empty(self, repo):
        result = repo.list_by_document("nonexistent")
        assert result == []

    def test_list_by_document_ordering(self, repo):
        now = datetime.utcnow()
        old = _make_correction(
            document_id="doc-1", field_id="old", timestamp=now - timedelta(hours=1)
        )
        new = _make_correction(document_id="doc-1", field_id="new", timestamp=now)

        repo.create(old)
        repo.create(new)

        result = repo.list_by_document("doc-1")
        assert len(result) == 2
        # Newest first
        assert result[0].field_id == "new"
        assert result[1].field_id == "old"

    def test_list_by_document_limit(self, repo):
        for i in range(10):
            repo.create(_make_correction(document_id="doc-1", field_id=f"field_{i}"))

        result = repo.list_by_document("doc-1", limit=3)
        assert len(result) == 3
