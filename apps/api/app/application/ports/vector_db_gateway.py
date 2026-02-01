"""Vector Database Gateway interface.

Defines the contract for vector database operations used in template matching.
The primary implementation will use Supabase with pgvector.

Key responsibilities:
- Store and search visual embeddings for template matching
- Support similarity search for finding matching templates
- Handle tenant isolation for multi-tenancy
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class EmbeddingVector(BaseModel):
    """An embedding vector with metadata."""

    id: str = Field(..., description="Unique identifier")
    vector: list[float] = Field(..., description="Embedding vector")
    metadata: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Associated metadata"
    )
    tenant_id: str | None = Field(None, description="Tenant ID for multi-tenancy")

    model_config = {"frozen": True}


class SimilarityResult(BaseModel):
    """Result of a similarity search."""

    id: str = Field(..., description="Matching item ID")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    metadata: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Associated metadata"
    )

    model_config = {"frozen": True}


class TemplateMatch(BaseModel):
    """A matched template from similarity search."""

    template_id: str = Field(..., description="Template ID")
    template_name: str = Field(..., description="Template display name")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Match score")
    preview_url: str | None = Field(None, description="Template preview image URL")
    field_count: int = Field(default=0, description="Number of fields in template")

    model_config = {"frozen": True}


@runtime_checkable
class VectorDBGateway(Protocol):
    """Interface for vector database operations (implemented by Supabase pgvector).

    This gateway abstracts vector similarity search, allowing different
    vector database backends to be used (pgvector, Pinecone, Weaviate, etc.).

    Used for:
    - Template matching via visual embedding similarity
    - Finding similar forms based on structure
    - Document deduplication
    """

    async def store_embedding(
        self,
        collection: str,
        embedding: EmbeddingVector,
    ) -> str:
        """Store an embedding vector.

        Args:
            collection: Collection/table name
            embedding: Embedding vector with metadata

        Returns:
            ID of the stored embedding
        """
        ...

    async def search_similar(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        threshold: float = 0.7,
        tenant_id: str | None = None,
    ) -> list[SimilarityResult]:
        """Search for similar vectors.

        Args:
            collection: Collection/table name
            query_vector: Query embedding vector
            limit: Maximum number of results
            threshold: Minimum similarity score
            tenant_id: Filter by tenant (for multi-tenancy)

        Returns:
            List of similarity results sorted by score descending
        """
        ...

    async def delete_embedding(
        self,
        collection: str,
        embedding_id: str,
    ) -> None:
        """Delete an embedding vector.

        Args:
            collection: Collection/table name
            embedding_id: ID of embedding to delete
        """
        ...

    async def find_matching_templates(
        self,
        page_embedding: list[float],
        tenant_id: str | None = None,
        limit: int = 3,
        threshold: float = 0.8,
    ) -> list[TemplateMatch]:
        """Find templates matching a page's visual embedding.

        Convenience method for template matching workflow.

        Args:
            page_embedding: Visual embedding of the uploaded page
            tenant_id: Filter by tenant (for multi-tenancy)
            limit: Maximum number of matches to return
            threshold: Minimum similarity score

        Returns:
            List of matching templates sorted by similarity
        """
        ...

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

        Convenience method for template registration workflow.

        Args:
            template_id: Template ID
            template_name: Template display name
            page_embedding: Visual embedding of the template page
            page_number: Page number within the template
            tenant_id: Tenant ID (for multi-tenancy)
            metadata: Additional metadata (field_count, preview_url, etc.)

        Returns:
            ID of the stored embedding
        """
        ...
