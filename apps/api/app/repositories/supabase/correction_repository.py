"""Supabase implementation of CorrectionRepository.

Provides correction record persistence using Supabase PostgreSQL database.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.models.correction_record import CorrectionCategory, CorrectionRecord
from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.resilience import with_retry

logger = logging.getLogger(__name__)


class SupabaseCorrectionRepository:
    """Supabase implementation of CorrectionRepository."""

    TABLE_NAME = "corrections"

    def __init__(self) -> None:
        self._client = get_supabase_client()

    def _to_model(self, row: dict[str, Any]) -> CorrectionRecord:
        """Convert a database row to a CorrectionRecord model."""
        created_at_str = row.get("created_at")
        if isinstance(created_at_str, str):
            timestamp = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            timestamp = created_at_str or datetime.now(timezone.utc)

        return CorrectionRecord(
            document_id=row["document_id"],
            field_id=row["field_id"],
            original_value=row.get("original_value"),
            corrected_value=row["corrected_value"],
            category=CorrectionCategory(row.get("category", "other")),
            timestamp=timestamp,
            conversation_id=row.get("conversation_id"),
        )

    def _to_row(self, correction: CorrectionRecord) -> dict[str, Any]:
        """Convert a CorrectionRecord model to a database row."""
        return {
            "id": str(uuid4()),
            "document_id": correction.document_id,
            "field_id": correction.field_id,
            "original_value": correction.original_value,
            "corrected_value": correction.corrected_value,
            "category": str(correction.category),
            "conversation_id": correction.conversation_id,
            "created_at": correction.timestamp.isoformat(),
        }

    def create(self, correction: CorrectionRecord) -> CorrectionRecord:
        """Persist a correction record with retry on transient errors."""
        try:
            return self._create_with_retry(correction)
        except Exception as e:
            logger.error(f"Failed to create correction: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _create_with_retry(self, correction: CorrectionRecord) -> CorrectionRecord:
        """Internal create with retry logic."""
        row = self._to_row(correction)
        result = self._client.table(self.TABLE_NAME).insert(row).execute()

        if result.data and len(result.data) > 0:
            return self._to_model(result.data[0])
        return correction

    def list_by_document(self, document_id: str, limit: int = 100) -> list[CorrectionRecord]:
        """List corrections for a document with retry on transient errors."""
        try:
            return self._list_by_document_with_retry(document_id, limit)
        except Exception as e:
            logger.error(f"Failed to list corrections for document {document_id}: {e}")
            return []

    @with_retry(max_retries=3, base_delay=1.0)
    def _list_by_document_with_retry(self, document_id: str, limit: int) -> list[CorrectionRecord]:
        """Internal list with retry logic."""
        result = (
            self._client.table(self.TABLE_NAME)
            .select("*")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._to_model(row) for row in result.data]
