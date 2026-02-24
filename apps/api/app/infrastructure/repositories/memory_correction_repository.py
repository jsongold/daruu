"""In-memory implementation of CorrectionRepository.

For unit testing only. Not suitable for production use.
"""

from app.domain.models.correction_record import CorrectionRecord


class MemoryCorrectionRepository:
    """In-memory correction storage using a list."""

    def __init__(self) -> None:
        self._store: list[CorrectionRecord] = []

    def create(self, correction: CorrectionRecord) -> CorrectionRecord:
        self._store.append(correction)
        return correction

    def list_by_document(
        self, document_id: str, limit: int = 100
    ) -> list[CorrectionRecord]:
        matches = [
            c for c in self._store if c.document_id == document_id
        ]
        # Sort by timestamp descending
        matches.sort(key=lambda c: c.timestamp, reverse=True)
        return matches[:limit]
