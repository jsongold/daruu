"""Vector Database Gateway interface (Port).

This defines the contract for vector similarity search operations.
Implementations can be in-memory, Pinecone, Qdrant, or any vector DB.
"""

from typing import Any, Protocol


class VectorDBGateway(Protocol):
    """Gateway interface for vector database operations.

    This protocol defines the contract for vector storage and search.
    Following Clean Architecture, the application layer depends on
    this interface, not on concrete implementations.

    Example:
        class PineconeVectorDB:
            async def store(self, id, embedding, metadata): ...
            async def search(self, embedding, limit, ...): ...
            async def delete(self, id): ...

        # Inject into service
        service = TemplateService(vector_db=PineconeVectorDB())
    """

    async def store(
        self,
        id: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store an embedding with metadata.

        Args:
            id: Unique identifier for the embedding.
            embedding: Vector embedding (list of floats).
            metadata: Optional metadata to store with the embedding.

        Returns:
            The ID of the stored embedding.
        """
        ...

    async def search(
        self,
        embedding: list[float],
        limit: int = 5,
        min_score: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings.

        Args:
            embedding: Query embedding vector.
            limit: Maximum number of results to return.
            min_score: Minimum similarity score (0-1) to include.
            filter: Optional metadata filter.

        Returns:
            List of matches, each containing:
                - id: Embedding ID
                - score: Similarity score (0-1)
                - metadata: Optional stored metadata
        """
        ...

    async def delete(self, id: str) -> bool:
        """Delete an embedding by ID.

        Args:
            id: Unique embedding identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...
