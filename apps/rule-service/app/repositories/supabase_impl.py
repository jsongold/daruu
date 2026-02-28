"""Supabase implementation of RuleSnippetRepository.

Provides rule snippet persistence using Supabase PostgreSQL with
pgvector for semantic similarity search.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.resilience import with_retry
from app.infrastructure.supabase_client import get_supabase_client
from app.schemas.rule_schemas import RuleSnippet

logger = logging.getLogger(__name__)


class SupabaseRuleSnippetRepository:
    """Supabase implementation of RuleSnippetRepository."""

    TABLE_NAME = "rule_snippets"

    def __init__(self) -> None:
        self._client = get_supabase_client()

    def _to_model(self, row: dict[str, Any]) -> RuleSnippet:
        """Convert a database row to a RuleSnippet model."""
        created_at_str = row.get("created_at")
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
        else:
            created_at = created_at_str or datetime.now(timezone.utc)

        applicable_fields = row.get("applicable_fields") or []

        return RuleSnippet(
            id=row["id"],
            document_id=row["document_id"],
            rule_text=row["rule_text"],
            applicable_fields=tuple(applicable_fields),
            source_document=row.get("source_document"),
            confidence=row.get("confidence", 1.0),
            created_at=created_at,
        )

    def _to_row(
        self, snippet: RuleSnippet, embedding: list[float] | None = None
    ) -> dict[str, Any]:
        """Convert a RuleSnippet model to a database row."""
        row: dict[str, Any] = {
            "id": snippet.id or str(uuid4()),
            "document_id": snippet.document_id,
            "rule_text": snippet.rule_text,
            "applicable_fields": list(snippet.applicable_fields),
            "source_document": snippet.source_document,
            "confidence": snippet.confidence,
            "created_at": snippet.created_at.isoformat(),
        }
        if embedding is not None:
            row["embedding"] = embedding
        return row

    def create(
        self, snippet: RuleSnippet, embedding: list[float] | None = None
    ) -> RuleSnippet:
        """Persist a rule snippet with retry on transient errors."""
        try:
            return self._create_with_retry(snippet, embedding)
        except Exception as e:
            logger.error(f"Failed to create rule snippet: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _create_with_retry(
        self, snippet: RuleSnippet, embedding: list[float] | None
    ) -> RuleSnippet:
        row = self._to_row(snippet, embedding)
        result = self._client.table(self.TABLE_NAME).insert(row).execute()
        if result.data and len(result.data) > 0:
            return self._to_model(result.data[0])
        return snippet

    def list_by_document(
        self, document_id: str, limit: int = 100
    ) -> list[RuleSnippet]:
        """List rule snippets for a document with retry."""
        try:
            return self._list_by_document_with_retry(document_id, limit)
        except Exception as e:
            logger.error(
                f"Failed to list rule snippets for document {document_id}: {e}"
            )
            return []

    @with_retry(max_retries=3, base_delay=1.0)
    def _list_by_document_with_retry(
        self, document_id: str, limit: int
    ) -> list[RuleSnippet]:
        result = (
            self._client.table(self.TABLE_NAME)
            .select("*")
            .eq("document_id", document_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [self._to_model(row) for row in result.data]

    def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[RuleSnippet]:
        """Semantic search using pgvector cosine distance."""
        try:
            return self._search_similar_with_retry(
                query_embedding, limit, threshold
            )
        except Exception as e:
            logger.error(f"Failed to search similar rule snippets: {e}")
            return []

    @with_retry(max_retries=3, base_delay=1.0)
    def _search_similar_with_retry(
        self,
        query_embedding: list[float],
        limit: int,
        threshold: float,
    ) -> list[RuleSnippet]:
        max_distance = 1.0 - threshold
        result = self._client.rpc(
            "match_rule_snippets",
            {
                "query_embedding": query_embedding,
                "match_threshold": max_distance,
                "match_count": limit,
            },
        ).execute()
        return [self._to_model(row) for row in (result.data or [])]

    def delete_by_document(self, document_id: str) -> int:
        """Delete all rule snippets for a document with retry."""
        try:
            return self._delete_by_document_with_retry(document_id)
        except Exception as e:
            logger.error(
                f"Failed to delete rule snippets for document {document_id}: {e}"
            )
            return 0

    @with_retry(max_retries=3, base_delay=1.0)
    def _delete_by_document_with_retry(self, document_id: str) -> int:
        result = (
            self._client.table(self.TABLE_NAME)
            .delete()
            .eq("document_id", document_id)
            .execute()
        )
        return len(result.data) if result.data else 0
