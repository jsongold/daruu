"""Embedding Gateway interface.

Defines the contract for generating embeddings.
The primary implementation will use OpenAI embeddings or CLIP for visual embeddings.

Key responsibilities:
- Generate visual embeddings from document pages (for template matching)
- Generate text embeddings (for semantic search if needed)
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class EmbeddingResult(BaseModel):
    """Result of an embedding operation."""

    vector: list[float] = Field(..., description="Embedding vector")
    model: str = Field(..., description="Model used for embedding")
    dimensions: int = Field(..., description="Vector dimensions")
    usage_tokens: int = Field(default=0, description="Tokens used (for text embeddings)")

    model_config = {"frozen": True}


class BatchEmbeddingResult(BaseModel):
    """Result of a batch embedding operation."""

    embeddings: list[list[float]] = Field(..., description="List of embedding vectors")
    model: str = Field(..., description="Model used for embedding")
    dimensions: int = Field(..., description="Vector dimensions")
    total_tokens: int = Field(default=0, description="Total tokens used")

    model_config = {"frozen": True}


@runtime_checkable
class EmbeddingGateway(Protocol):
    """Interface for embedding generation (implemented by OpenAI/CLIP).

    This gateway abstracts embedding generation, allowing different
    embedding providers to be used (OpenAI, CLIP, Cohere, etc.).

    Used for:
    - Visual embeddings for template matching
    - Text embeddings for semantic search
    """

    async def embed_image(
        self,
        image_bytes: bytes,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Generate visual embedding from an image.

        Uses CLIP or similar vision model for visual understanding.

        Args:
            image_bytes: Image content as bytes (PNG, JPEG)
            model: Optional model override

        Returns:
            Embedding result with vector
        """
        ...

    async def embed_text(
        self,
        text: str,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Generate text embedding.

        Args:
            text: Text to embed
            model: Optional model override

        Returns:
            Embedding result with vector
        """
        ...

    async def embed_texts_batch(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> BatchEmbeddingResult:
        """Generate text embeddings in batch.

        Args:
            texts: List of texts to embed
            model: Optional model override

        Returns:
            Batch embedding result with vectors
        """
        ...

    async def embed_document_page(
        self,
        page_image: bytes,
        page_text: str | None = None,
    ) -> EmbeddingResult:
        """Generate embedding for a document page.

        Combines visual and textual features for better matching.
        This is the primary method for template matching.

        Args:
            page_image: Page rendered as image (PNG)
            page_text: Optional extracted text for hybrid embedding

        Returns:
            Embedding result with combined visual+text features
        """
        ...

    def get_dimensions(self, model: str | None = None) -> int:
        """Get the embedding dimensions for a model.

        Args:
            model: Model name (uses default if None)

        Returns:
            Number of dimensions in the embedding vector
        """
        ...
