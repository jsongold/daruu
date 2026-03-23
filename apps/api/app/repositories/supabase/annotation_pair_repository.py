"""Supabase implementation of AnnotationPairRepository."""

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.resilience import with_retry
from app.models.annotation import AnnotationBBox, AnnotationPairCreate, AnnotationPairModel
from app.repositories.annotation_pair_repository import AnnotationPairRepository

logger = logging.getLogger(__name__)


class SupabaseAnnotationPairRepository:
    """Supabase implementation of AnnotationPairRepository."""

    TABLE_NAME = "annotation_pairs"

    def __init__(self) -> None:
        self._client = get_supabase_client()

    def _parse_bbox(self, raw: Any) -> AnnotationBBox:
        if isinstance(raw, str):
            raw = json.loads(raw)
        return AnnotationBBox(
            x=raw["x"],
            y=raw["y"],
            width=raw["width"],
            height=raw["height"],
        )

    def _to_model(self, row: dict[str, Any]) -> AnnotationPairModel:
        created_at_str = row.get("created_at")
        created_at = None
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        elif created_at_str is not None:
            created_at = created_at_str

        return AnnotationPairModel(
            id=str(row["id"]),
            document_id=str(row["document_id"]),
            label_id=row["label_id"],
            label_text=row["label_text"],
            label_bbox=self._parse_bbox(row["label_bbox"]),
            label_page=row["label_page"],
            field_id=row["field_id"],
            field_name=row["field_name"],
            field_bbox=self._parse_bbox(row["field_bbox"]),
            field_page=row["field_page"],
            confidence=row["confidence"],
            status=row["status"],
            is_manual=row["is_manual"],
            created_at=created_at,
        )

    def _to_row(self, document_id: str, data: AnnotationPairCreate, pair_id: str) -> dict[str, Any]:
        return {
            "id": pair_id,
            "document_id": document_id,
            "label_id": data.label_id,
            "label_text": data.label_text,
            "label_bbox": data.label_bbox.model_dump(),
            "label_page": data.label_page,
            "field_id": data.field_id,
            "field_name": data.field_name,
            "field_bbox": data.field_bbox.model_dump(),
            "field_page": data.field_page,
            "confidence": data.confidence,
            "status": data.status,
            "is_manual": data.is_manual,
        }

    def create(self, document_id: str, data: AnnotationPairCreate) -> AnnotationPairModel:
        pair_id = str(uuid4())
        row = self._to_row(document_id, data, pair_id)
        try:
            return self._create_with_retry(row, pair_id, document_id, data)
        except Exception as e:
            logger.error(f"Failed to create annotation pair: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _create_with_retry(
        self,
        row: dict[str, Any],
        pair_id: str,
        document_id: str,
        data: AnnotationPairCreate,
    ) -> AnnotationPairModel:
        result = self._client.table(self.TABLE_NAME).insert(row).execute()
        if result.data and len(result.data) > 0:
            return self._to_model(result.data[0])
        return AnnotationPairModel(
            id=pair_id,
            document_id=document_id,
            label_id=data.label_id,
            label_text=data.label_text,
            label_bbox=data.label_bbox,
            label_page=data.label_page,
            field_id=data.field_id,
            field_name=data.field_name,
            field_bbox=data.field_bbox,
            field_page=data.field_page,
            confidence=data.confidence,
            status=data.status,
            is_manual=data.is_manual,
            created_at=datetime.now(timezone.utc),
        )

    def list_by_document(self, document_id: str) -> list[AnnotationPairModel]:
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .select("*")
                .eq("document_id", document_id)
                .order("created_at")
                .execute()
            )
            return [self._to_model(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to list annotation pairs for {document_id}: {e}")
            return []

    def delete(self, pair_id: str) -> bool:
        try:
            self._client.table(self.TABLE_NAME).delete().eq("id", pair_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete annotation pair {pair_id}: {e}")
            return False

    def delete_by_document(self, document_id: str) -> int:
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .delete()
                .eq("document_id", document_id)
                .execute()
            )
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"Failed to clear annotation pairs for {document_id}: {e}")
            return 0


# Verify protocol compliance
_assert_protocol: AnnotationPairRepository = SupabaseAnnotationPairRepository()  # type: ignore[assignment]
