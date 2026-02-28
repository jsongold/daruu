"""Repository interface for rule snippets.

Defines the contract for storing and retrieving rule snippets
extracted from rule documents, with support for vector-based
semantic search.
"""

from typing import Protocol, runtime_checkable

from app.schemas.rule_schemas import RuleSnippet


@runtime_checkable
class RuleSnippetRepository(Protocol):
    """Interface for rule snippet persistence and search."""

    def create(
        self, snippet: RuleSnippet, embedding: list[float] | None = None
    ) -> RuleSnippet:
        """Persist a rule snippet with optional embedding."""
        ...

    def list_by_document(
        self, document_id: str, limit: int = 100
    ) -> list[RuleSnippet]:
        """List rule snippets for a document."""
        ...

    def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[RuleSnippet]:
        """Search for semantically similar rule snippets."""
        ...

    def delete_by_document(self, document_id: str) -> int:
        """Delete all rule snippets for a document."""
        ...
