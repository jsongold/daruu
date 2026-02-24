"""CorrectionTracker — persistent correction tracking.

Records user corrections to auto-filled values and retrieves them
for learning and improvement. Wraps a CorrectionRepository with
defensive error handling (non-fatal on failures).
"""

import logging

from app.domain.models.correction_record import CorrectionRecord
from app.repositories.correction_repository import CorrectionRepository

logger = logging.getLogger(__name__)


class CorrectionTrackerStub:
    """Stub implementation of CorrectionTrackerProtocol.

    No-op: does not persist corrections. Kept for backward compatibility
    and as a fallback when repository is unavailable.
    """

    async def record(self, correction: CorrectionRecord) -> None:
        pass

    async def list_corrections(self, document_id: str) -> list[CorrectionRecord]:
        return []


class CorrectionTracker:
    """Persistent correction tracker backed by a repository.

    record() is fire-and-forget: exceptions are logged but not raised.
    list_corrections() returns [] on error.
    """

    def __init__(self, repository: CorrectionRepository) -> None:
        self._repo = repository

    async def record(self, correction: CorrectionRecord) -> None:
        """Record a correction. Non-fatal on repository errors."""
        try:
            self._repo.create(correction)
            logger.info(
                f"Recorded correction: doc={correction.document_id}, "
                f"field={correction.field_id}"
            )
        except Exception as e:
            logger.error(f"Failed to record correction: {e}")

    async def list_corrections(self, document_id: str) -> list[CorrectionRecord]:
        """List corrections for a document. Returns [] on error."""
        try:
            return self._repo.list_by_document(document_id)
        except Exception as e:
            logger.error(f"Failed to list corrections for {document_id}: {e}")
            return []
