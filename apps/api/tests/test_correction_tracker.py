"""Tests for CorrectionTracker — persistent correction tracking."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from app.domain.models.correction_record import CorrectionCategory, CorrectionRecord
from app.domain.protocols.correction_tracker import CorrectionTrackerProtocol
from app.infrastructure.repositories.memory_correction_repository import (
    MemoryCorrectionRepository,
)
from app.services.correction_tracker.tracker import (
    CorrectionTracker,
    CorrectionTrackerStub,
)

# ============================================================================
# Helpers
# ============================================================================


def _make_correction(
    document_id: str = "doc-1",
    field_id: str = "name",
    original: str = "John",
    corrected: str = "Jane",
    category: CorrectionCategory = CorrectionCategory.WRONG_VALUE,
) -> CorrectionRecord:
    return CorrectionRecord(
        document_id=document_id,
        field_id=field_id,
        original_value=original,
        corrected_value=corrected,
        category=category,
        timestamp=datetime.utcnow(),
    )


# ============================================================================
# Protocol Compliance
# ============================================================================


class TestProtocolCompliance:
    def test_stub_satisfies_protocol(self):
        stub = CorrectionTrackerStub()
        assert isinstance(stub, CorrectionTrackerProtocol)

    def test_tracker_satisfies_protocol(self):
        tracker = CorrectionTracker(repository=MemoryCorrectionRepository())
        assert isinstance(tracker, CorrectionTrackerProtocol)


# ============================================================================
# CorrectionTrackerStub
# ============================================================================


class TestCorrectionTrackerStub:
    @pytest.mark.asyncio
    async def test_record_is_noop(self):
        stub = CorrectionTrackerStub()
        await stub.record(_make_correction())
        # No error raised

    @pytest.mark.asyncio
    async def test_list_returns_empty(self):
        stub = CorrectionTrackerStub()
        result = await stub.list_corrections("any-doc")
        assert result == []


# ============================================================================
# CorrectionTracker
# ============================================================================


class TestCorrectionTrackerRecord:
    @pytest.mark.asyncio
    async def test_record_persists_via_repo(self):
        repo = MemoryCorrectionRepository()
        tracker = CorrectionTracker(repository=repo)

        correction = _make_correction(document_id="doc-1", field_id="name")
        await tracker.record(correction)

        stored = repo.list_by_document("doc-1")
        assert len(stored) == 1
        assert stored[0].field_id == "name"

    @pytest.mark.asyncio
    async def test_record_non_fatal_on_error(self):
        repo = MagicMock()
        repo.create = MagicMock(side_effect=Exception("DB down"))
        tracker = CorrectionTracker(repository=repo)

        # Should not raise
        await tracker.record(_make_correction())


class TestCorrectionTrackerList:
    @pytest.mark.asyncio
    async def test_list_retrieves_by_document(self):
        repo = MemoryCorrectionRepository()
        tracker = CorrectionTracker(repository=repo)

        await tracker.record(_make_correction(document_id="doc-1"))
        await tracker.record(_make_correction(document_id="doc-2"))
        await tracker.record(_make_correction(document_id="doc-1", field_id="date"))

        result = await tracker.list_corrections("doc-1")
        assert len(result) == 2
        assert all(r.document_id == "doc-1" for r in result)

    @pytest.mark.asyncio
    async def test_list_returns_empty_for_unknown(self):
        repo = MemoryCorrectionRepository()
        tracker = CorrectionTracker(repository=repo)

        result = await tracker.list_corrections("nonexistent")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_returns_empty_on_error(self):
        repo = MagicMock()
        repo.list_by_document = MagicMock(side_effect=Exception("DB down"))
        tracker = CorrectionTracker(repository=repo)

        result = await tracker.list_corrections("doc-1")
        assert result == []
