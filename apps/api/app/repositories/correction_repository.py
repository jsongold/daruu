"""Repository interface for correction records.

Defines the contract for storing and retrieving user corrections
to auto-filled field values.
"""

from typing import Protocol, runtime_checkable

from app.domain.models.correction_record import CorrectionRecord


@runtime_checkable
class CorrectionRepository(Protocol):
    """Interface for correction persistence."""

    def create(self, correction: CorrectionRecord) -> CorrectionRecord:
        """Persist a correction record.

        Args:
            correction: The correction record to store.

        Returns:
            The stored correction record (may include generated ID).
        """
        ...

    def list_by_document(self, document_id: str, limit: int = 100) -> list[CorrectionRecord]:
        """List corrections for a document.

        Args:
            document_id: Document ID to filter by.
            limit: Maximum number of records to return.

        Returns:
            List of correction records, ordered by timestamp descending.
        """
        ...
