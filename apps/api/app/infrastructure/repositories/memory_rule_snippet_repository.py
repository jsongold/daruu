"""In-memory implementation of RuleSnippetRepository.

For unit testing only. Uses cosine similarity for vector search
(same approach as InMemoryVectorDB).
"""

import math
from uuid import uuid4

from app.domain.models.rule_snippet import RuleSnippet


class MemoryRuleSnippetRepository:
    """In-memory rule snippet storage with vector search."""

    def __init__(self) -> None:
        self._store: list[tuple[RuleSnippet, list[float] | None]] = []

    def create(
        self, snippet: RuleSnippet, embedding: list[float] | None = None
    ) -> RuleSnippet:
        stored = RuleSnippet(
            id=snippet.id or str(uuid4()),
            document_id=snippet.document_id,
            rule_text=snippet.rule_text,
            applicable_fields=snippet.applicable_fields,
            source_document=snippet.source_document,
            confidence=snippet.confidence,
            created_at=snippet.created_at,
        )
        self._store.append((stored, embedding))
        return stored

    def list_by_document(
        self, document_id: str, limit: int = 100
    ) -> list[RuleSnippet]:
        matches = [
            s for s, _ in self._store if s.document_id == document_id
        ]
        matches.sort(key=lambda s: s.created_at, reverse=True)
        return matches[:limit]

    def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[RuleSnippet]:
        scored: list[tuple[float, RuleSnippet]] = []
        for snippet, emb in self._store:
            if emb is None:
                continue
            score = _cosine_similarity(query_embedding, emb)
            if score >= threshold:
                scored.append((score, snippet))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def delete_by_document(self, document_id: str) -> int:
        before = len(self._store)
        self._store = [
            (s, e) for s, e in self._store if s.document_id != document_id
        ]
        return before - len(self._store)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    if len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)
