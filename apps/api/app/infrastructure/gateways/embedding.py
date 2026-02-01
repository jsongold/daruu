"""Embedding Gateway implementations.

Provides implementations for generating vector embeddings from content.
Includes mock implementation for testing and OpenAI implementation for production.
"""

import hashlib
import math
from typing import Any

from app.repositories.embedding_gateway import EmbeddingGateway


class MockEmbeddingGateway:
    """Mock implementation of EmbeddingGateway for testing.

    Generates deterministic embeddings based on content hash.
    Useful for testing and development without API costs.

    Example:
        gateway = MockEmbeddingGateway()
        embedding = await gateway.embed_text("Hello world")
    """

    def __init__(self, dimension: int = 1536) -> None:
        """Initialize the mock gateway.

        Args:
            dimension: Size of generated embeddings (default: 1536 for OpenAI).
        """
        self._dimension = dimension

    async def embed_image(self, image_bytes: bytes) -> list[float]:
        """Generate deterministic embedding from image bytes.

        Args:
            image_bytes: Raw image data.

        Returns:
            Normalized vector embedding.
        """
        # Generate hash-based embedding for determinism
        return self._generate_embedding(image_bytes)

    async def embed_text(self, text: str) -> list[float]:
        """Generate deterministic embedding from text.

        Args:
            text: Text to embed.

        Returns:
            Normalized vector embedding.
        """
        return self._generate_embedding(text.encode("utf-8"))

    async def embed_document_page(
        self,
        page_image: bytes | None = None,
        page_text: str | None = None,
        page_number: int = 1,
    ) -> list[float]:
        """Generate embedding for a document page.

        Args:
            page_image: Optional page image bytes.
            page_text: Optional extracted page text.
            page_number: Page number (for context).

        Returns:
            Normalized vector embedding.
        """
        # Combine available inputs
        content = b""
        if page_image:
            content += page_image
        if page_text:
            content += page_text.encode("utf-8")
        content += str(page_number).encode("utf-8")

        return self._generate_embedding(content)

    def _generate_embedding(self, content: bytes) -> list[float]:
        """Generate a deterministic, normalized embedding from content.

        Args:
            content: Raw bytes to embed.

        Returns:
            Normalized vector of specified dimension.
        """
        # Use SHA-256 hash to generate deterministic values
        hash_bytes = hashlib.sha256(content).digest()

        # Expand hash to fill the embedding dimension
        embedding = []
        for i in range(self._dimension):
            # Use different parts of the hash for each dimension
            idx = i % len(hash_bytes)
            # Convert to float in range [-1, 1]
            value = (hash_bytes[idx] - 128) / 128.0
            # Add some variation based on position
            value += (hash_bytes[(idx + 1) % len(hash_bytes)] - 128) / 256.0 * (i / self._dimension)
            embedding.append(value)

        # Normalize to unit vector
        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding


class OpenAIEmbeddingGateway:
    """OpenAI-based implementation of EmbeddingGateway.

    Uses OpenAI's text-embedding-3-small or similar models for production embeddings.
    Requires an OpenAI API key.

    Example:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key="sk-...")
        gateway = OpenAIEmbeddingGateway(client=client)
        embedding = await gateway.embed_text("Hello world")
    """

    def __init__(
        self,
        client: Any = None,
        model: str = "text-embedding-3-small",
    ) -> None:
        """Initialize the OpenAI gateway.

        Args:
            client: OpenAI async client instance.
            model: OpenAI embedding model to use.
        """
        self._client = client
        self._model = model

    async def embed_image(self, image_bytes: bytes) -> list[float]:
        """Generate embedding from image bytes.

        Note: OpenAI text embeddings don't directly support images.
        This implementation converts image to base64 and describes it.
        For true image embeddings, use a multimodal model.

        Args:
            image_bytes: Raw image data.

        Returns:
            Vector embedding.
        """
        # For now, use a text representation of the image
        # In production, you might use GPT-4V to describe the image first
        import base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        # Use a hash of the image as a placeholder
        return await self.embed_text(f"image:{image_b64[:100]}")

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding from text using OpenAI.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding.

        Raises:
            Exception: If API call fails.
        """
        if self._client is None:
            raise ValueError("OpenAI client not configured")

        response = await self._client.embeddings.create(
            model=self._model,
            input=text,
        )
        return response.data[0].embedding

    async def embed_document_page(
        self,
        page_image: bytes | None = None,
        page_text: str | None = None,
        page_number: int = 1,
    ) -> list[float]:
        """Generate embedding for a document page.

        Args:
            page_image: Optional page image bytes.
            page_text: Optional extracted page text.
            page_number: Page number (for context).

        Returns:
            Vector embedding.
        """
        # Prefer text if available, fall back to image
        if page_text:
            return await self.embed_text(page_text)
        elif page_image:
            return await self.embed_image(page_image)
        else:
            return await self.embed_text(f"Page {page_number}")


# Type assertion to verify protocol compliance
_assert_mock_gateway: EmbeddingGateway = MockEmbeddingGateway()
_assert_openai_gateway: EmbeddingGateway = OpenAIEmbeddingGateway()
