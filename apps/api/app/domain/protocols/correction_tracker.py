"""Protocol for CorrectionTracker.

CorrectionTracker records and retrieves user corrections to auto-filled
values, enabling the system to learn from mistakes.
"""

from typing import Protocol, runtime_checkable

from app.domain.models.correction_record import CorrectionRecord


@runtime_checkable
class CorrectionTrackerProtocol(Protocol):
    """Interface for tracking user corrections.

    Implementations store corrections and provide retrieval
    for learning and improvement.
    """

    async def record(
        self,
        correction: CorrectionRecord,
    ) -> None:
        """Record a user correction.

        Args:
            correction: The correction record to store.
        """
        ...

    async def list_corrections(
        self,
        document_id: str,
    ) -> list[CorrectionRecord]:
        """List corrections for a document.

        Args:
            document_id: Document ID to retrieve corrections for.

        Returns:
            List of correction records for the document.
        """
        ...
