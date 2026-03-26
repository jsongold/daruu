"""In-memory Vector Database implementation.

MVP implementation for testing and development.
For production, use a proper vector database like Pinecone, Qdrant, or Weaviate.
"""

import math
from typing import Any

from app.repositories.vector_db_gateway import VectorDBGateway


class InMemoryVectorDB:
    """In-memory implementation of VectorDBGateway.

    Stores embeddings in a dictionary and performs brute-force
    cosine similarity search. Suitable for small datasets and testing.

    Example:
        db = InMemoryVectorDB()
        await db.store("emb-1", [0.1, 0.2, 0.3], {"tenant_id": "t1"})
        results = await db.search([0.1, 0.2, 0.3], limit=5)
    """

    def __init__(self) -> None:
        """Initialize the vector database with empty storage."""
        self._embeddings: dict[str, dict[str, Any]] = {}

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

        Raises:
            ValueError: If embedding is empty.
        """
        if not embedding:
            raise ValueError("Embedding cannot be empty")

        # Check for NaN or infinity
        for val in embedding:
            if math.isnan(val) or math.isinf(val):
                raise ValueError("Embedding contains NaN or infinity values")

        self._embeddings[id] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }
        return id

    async def search(
        self,
        embedding: list[float],
        limit: int = 5,
        min_score: float | None = None,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar embeddings using cosine similarity.

        Args:
            embedding: Query embedding vector.
            limit: Maximum number of results to return.
            min_score: Minimum similarity score (0-1) to include.
            filter: Optional metadata filter.

        Returns:
            List of matches sorted by similarity score (descending).
        """
        if limit <= 0:
            return []

        results = []

        for id, data in self._embeddings.items():
            stored_embedding = data["embedding"]
            stored_metadata = data["metadata"]

            # Apply metadata filter
            if filter:
                match = True
                for key, value in filter.items():
                    if stored_metadata.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            # Calculate cosine similarity
            score = self._cosine_similarity(embedding, stored_embedding)

            # Apply minimum score filter
            if min_score is not None and score < min_score:
                continue

            results.append(
                {
                    "id": id,
                    "score": score,
                    "metadata": stored_metadata,
                }
            )

        # Sort by score descending and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    async def delete(self, id: str) -> bool:
        """Delete an embedding by ID.

        Args:
            id: Unique embedding identifier.

        Returns:
            True if deleted, False if not found.
        """
        if id in self._embeddings:
            del self._embeddings[id]
            return True
        return False

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector.
            vec2: Second vector.

        Returns:
            Cosine similarity score between -1 and 1.
        """
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def clear(self) -> None:
        """Clear all embeddings from storage.

        Useful for testing.
        """
        self._embeddings.clear()


# Type assertion to verify protocol compliance
_assert_vector_db: VectorDBGateway = InMemoryVectorDB()
