"""In-memory vector database implementation.

MVP implementation of VectorDBGateway for development and testing.
Uses simple cosine similarity for vector search.

For production, use Supabase with pgvector or a dedicated
vector database (Pinecone, Weaviate, etc.).
"""

import math
from uuid import uuid4

from app.application.ports.vector_db_gateway import (
    EmbeddingVector,
    SimilarityResult,
    TemplateMatch,
    VectorDBGateway,
)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec_a: First vector.
        vec_b: Second vector.

    Returns:
        Cosine similarity score between 0 and 1.

    Raises:
        ValueError: If vectors have different dimensions.
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector dimensions must match: {len(vec_a)} vs {len(vec_b)}"
        )

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    similarity = dot_product / (norm_a * norm_b)
    # Clamp to [0, 1] to handle floating point errors
    return max(0.0, min(1.0, similarity))


class MemoryVectorDB:
    """In-memory implementation of VectorDBGateway.

    Stores embedding vectors in memory and performs brute-force
    cosine similarity search. Suitable for development and testing
    with small datasets.

    Collections are stored as separate dictionaries, allowing
    isolation between different embedding types (templates, documents, etc.).

    Example:
        db = MemoryVectorDB()

        # Store template embedding
        embedding_id = await db.store_template_embedding(
            template_id="tmpl-1",
            template_name="W-9",
            page_embedding=[0.1, 0.2, 0.3, ...],
            page_number=1,
        )

        # Find similar templates
        matches = await db.find_matching_templates(
            page_embedding=[0.1, 0.2, 0.3, ...],
            limit=5,
            threshold=0.8,
        )
    """

    # Default collection for template embeddings
    TEMPLATES_COLLECTION = "template_embeddings"

    def __init__(self) -> None:
        """Initialize the in-memory vector database."""
        # Collections store embeddings: {collection_name: {id: EmbeddingVector}}
        self._collections: dict[str, dict[str, EmbeddingVector]] = {}

    def _get_collection(self, collection: str) -> dict[str, EmbeddingVector]:
        """Get or create a collection."""
        if collection not in self._collections:
            self._collections[collection] = {}
        return self._collections[collection]

    async def store_embedding(
        self,
        collection: str,
        embedding: EmbeddingVector,
    ) -> str:
        """Store an embedding vector.

        Args:
            collection: Collection/table name.
            embedding: Embedding vector with metadata.

        Returns:
            ID of the stored embedding.
        """
        coll = self._get_collection(collection)
        coll[embedding.id] = embedding
        return embedding.id

    async def search_similar(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        threshold: float = 0.7,
        tenant_id: str | None = None,
    ) -> list[SimilarityResult]:
        """Search for similar vectors using cosine similarity.

        Args:
            collection: Collection/table name.
            query_vector: Query embedding vector.
            limit: Maximum number of results.
            threshold: Minimum similarity score.
            tenant_id: Filter by tenant (for multi-tenancy).

        Returns:
            List of similarity results sorted by score descending.
        """
        coll = self._get_collection(collection)

        results: list[tuple[str, float, dict]] = []

        for emb_id, embedding in coll.items():
            # Filter by tenant if specified
            if tenant_id is not None and embedding.tenant_id != tenant_id:
                continue

            try:
                score = _cosine_similarity(query_vector, embedding.vector)
                if score >= threshold:
                    results.append((emb_id, score, dict(embedding.metadata)))
            except ValueError:
                # Skip embeddings with incompatible dimensions
                continue

        # Sort by score descending and limit
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:limit]

        return [
            SimilarityResult(id=r[0], score=r[1], metadata=r[2]) for r in results
        ]

    async def delete_embedding(
        self,
        collection: str,
        embedding_id: str,
    ) -> None:
        """Delete an embedding vector.

        Args:
            collection: Collection/table name.
            embedding_id: ID of embedding to delete.
        """
        coll = self._get_collection(collection)
        if embedding_id in coll:
            del coll[embedding_id]

    async def find_matching_templates(
        self,
        page_embedding: list[float],
        tenant_id: str | None = None,
        limit: int = 3,
        threshold: float = 0.8,
    ) -> list[TemplateMatch]:
        """Find templates matching a page's visual embedding.

        Searches the template embeddings collection for similar templates.
        Returns matches with template metadata.

        Args:
            page_embedding: Visual embedding of the uploaded page.
            tenant_id: Filter by tenant (for multi-tenancy).
            limit: Maximum number of matches to return.
            threshold: Minimum similarity score.

        Returns:
            List of matching templates sorted by similarity.
        """
        similar = await self.search_similar(
            collection=self.TEMPLATES_COLLECTION,
            query_vector=page_embedding,
            limit=limit,
            threshold=threshold,
            tenant_id=tenant_id,
        )

        matches = []
        for result in similar:
            matches.append(
                TemplateMatch(
                    template_id=str(result.metadata.get("template_id", result.id)),
                    template_name=str(result.metadata.get("template_name", "Unknown")),
                    similarity_score=result.score,
                    preview_url=result.metadata.get("preview_url"),
                    field_count=int(result.metadata.get("field_count", 0)),
                )
            )

        return matches

    async def store_template_embedding(
        self,
        template_id: str,
        template_name: str,
        page_embedding: list[float],
        page_number: int,
        tenant_id: str | None = None,
        metadata: dict[str, str | int | float | bool] | None = None,
    ) -> str:
        """Store a template's visual embedding.

        Args:
            template_id: Template ID.
            template_name: Template display name.
            page_embedding: Visual embedding of the template page.
            page_number: Page number within the template.
            tenant_id: Tenant ID (for multi-tenancy).
            metadata: Additional metadata (field_count, preview_url, etc.).

        Returns:
            ID of the stored embedding.
        """
        embedding_id = f"emb-{uuid4().hex[:12]}"

        # Build metadata combining explicit fields and additional metadata
        emb_metadata: dict[str, str | int | float | bool] = {
            "template_id": template_id,
            "template_name": template_name,
            "page_number": page_number,
        }
        if metadata:
            emb_metadata.update(metadata)

        embedding = EmbeddingVector(
            id=embedding_id,
            vector=page_embedding,
            metadata=emb_metadata,
            tenant_id=tenant_id,
        )

        return await self.store_embedding(
            collection=self.TEMPLATES_COLLECTION,
            embedding=embedding,
        )

    def clear_collection(self, collection: str) -> None:
        """Clear all embeddings from a collection.

        Useful for testing.

        Args:
            collection: Collection name to clear.
        """
        if collection in self._collections:
            self._collections[collection].clear()

    def clear_all(self) -> None:
        """Clear all collections.

        Useful for testing.
        """
        self._collections.clear()


# Type assertion to verify protocol compliance
_assert_vector_db: VectorDBGateway = MemoryVectorDB()
