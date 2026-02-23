"""CorrectionTracker stub — no-op for Phase 2.

Will be replaced with persistent storage in a future phase.
"""

from app.domain.models.correction_record import CorrectionRecord


class CorrectionTrackerStub:
    """Stub implementation of CorrectionTrackerProtocol.

    No-op: does not persist corrections. Placeholder for
    future database-backed implementation.
    """

    async def record(
        self,
        correction: CorrectionRecord,
    ) -> None:
        """No-op (stub).

        Args:
            correction: Correction record (ignored).
        """

    async def list_corrections(
        self,
        document_id: str,
    ) -> list[CorrectionRecord]:
        """Return empty list (stub).

        Args:
            document_id: Document ID (ignored).

        Returns:
            Empty list.
        """
        return []
