"""Repository interface for rule snippets.

Defines the contract for storing and retrieving rule snippets
extracted from rule documents, with support for vector-based
semantic search.
"""

from typing import Protocol, runtime_checkable

from app.domain.models.rule_snippet import RuleSnippet


@runtime_checkable
class RuleSnippetRepository(Protocol):
    """Interface for rule snippet persistence and search."""

    def create(self, snippet: RuleSnippet, embedding: list[float] | None = None) -> RuleSnippet:
        """Persist a rule snippet with optional embedding.

        Args:
            snippet: The rule snippet to store.
            embedding: Optional vector embedding for semantic search.

        Returns:
            The stored snippet (may include generated ID).
        """
        ...

    def list_by_document(self, document_id: str, limit: int = 100) -> list[RuleSnippet]:
        """List rule snippets for a document.

        Args:
            document_id: Document ID to filter by.
            limit: Maximum number of records to return.

        Returns:
            List of rule snippets ordered by created_at descending.
        """
        ...

    def search_similar(
        self,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[RuleSnippet]:
        """Search for semantically similar rule snippets.

        Args:
            query_embedding: Vector embedding of the search query.
            limit: Maximum number of results.
            threshold: Minimum cosine similarity score (0.0-1.0).

        Returns:
            List of matching snippets ordered by similarity descending.
        """
        ...

    def delete_by_document(self, document_id: str) -> int:
        """Delete all rule snippets for a document.

        Args:
            document_id: Document ID whose snippets to delete.

        Returns:
            Number of deleted records.
        """
        ...
