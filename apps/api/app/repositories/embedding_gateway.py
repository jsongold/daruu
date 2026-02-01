"""Embedding Gateway interface (Port).

This defines the contract for generating vector embeddings from content.
Implementations can use OpenAI, local models, or any embedding service.
"""

from typing import Protocol


class EmbeddingGateway(Protocol):
    """Gateway interface for embedding generation.

    This protocol defines the contract for converting content
    (images, text) into vector embeddings for similarity search.

    Example:
        class OpenAIEmbeddingGateway:
            async def embed_image(self, image_bytes): ...
            async def embed_text(self, text): ...

        # Inject into service
        service = TemplateService(embedding_gateway=OpenAIEmbeddingGateway())
    """

    async def embed_image(self, image_bytes: bytes) -> list[float]:
        """Generate embedding from image bytes.

        Args:
            image_bytes: Raw image data (PNG, JPEG, etc.).

        Returns:
            Vector embedding (list of floats).
        """
        ...

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding from text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding (list of floats).
        """
        ...

    async def embed_document_page(
        self,
        page_image: bytes | None = None,
        page_text: str | None = None,
        page_number: int = 1,
    ) -> list[float]:
        """Generate embedding for a document page.

        Combines image and text information for a more robust embedding.
        At least one of page_image or page_text must be provided.

        Args:
            page_image: Optional page image bytes.
            page_text: Optional extracted page text.
            page_number: Page number (for context).

        Returns:
            Vector embedding (list of floats).
        """
        ...
