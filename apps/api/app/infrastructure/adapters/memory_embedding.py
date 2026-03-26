"""In-memory mock embedding implementation.

MVP implementation of EmbeddingGateway for development and testing.
Generates deterministic pseudo-embeddings based on input hashing.

For production, use OpenAI embeddings or CLIP for visual embeddings.
"""

import hashlib
import math
from typing import Final

from app.application.ports.embedding_gateway import (
    BatchEmbeddingResult,
    EmbeddingGateway,
    EmbeddingResult,
)

# Default embedding dimensions (matches text-embedding-3-small)
DEFAULT_DIMENSIONS: Final[int] = 1536

# Model name for mock embeddings
MOCK_MODEL: Final[str] = "mock-embedding-v1"


def _hash_to_vector(data: bytes, dimensions: int = DEFAULT_DIMENSIONS) -> list[float]:
    """Generate a deterministic pseudo-embedding from bytes.

    Uses SHA-256 hash to generate reproducible vector values.
    The same input will always produce the same embedding.

    Args:
        data: Input data to hash.
        dimensions: Number of dimensions in the output vector.

    Returns:
        Normalized vector of floats.
    """
    # Generate enough hash bytes for the dimensions
    hash_bytes = b""
    counter = 0
    while len(hash_bytes) < dimensions * 4:
        h = hashlib.sha256(data + counter.to_bytes(4, "big"))
        hash_bytes += h.digest()
        counter += 1

    # Convert to floats in range [-1, 1]
    values = []
    for i in range(dimensions):
        # Take 4 bytes and convert to float
        byte_slice = hash_bytes[i * 4 : (i + 1) * 4]
        int_val = int.from_bytes(byte_slice, "big", signed=False)
        # Map to [-1, 1]
        float_val = (int_val / (2**32 - 1)) * 2 - 1
        values.append(float_val)

    # Normalize the vector (L2 normalization)
    norm = math.sqrt(sum(v * v for v in values))
    if norm > 0:
        values = [v / norm for v in values]

    return values


class MemoryEmbedding:
    """In-memory mock implementation of EmbeddingGateway.

    Generates deterministic embeddings based on input hashing.
    Useful for testing and development without external API calls.

    The embeddings are:
    - Deterministic: Same input always produces same output
    - Normalized: L2 norm equals 1
    - Dimensionally consistent: All vectors have same dimensions

    Example:
        embedding = MemoryEmbedding()

        # Generate visual embedding from image
        result = await embedding.embed_image(image_bytes)
        print(result.vector)  # [0.1, -0.2, 0.3, ...]

        # Same image always produces same embedding
        result2 = await embedding.embed_image(image_bytes)
        assert result.vector == result2.vector
    """

    def __init__(self, dimensions: int = DEFAULT_DIMENSIONS) -> None:
        """Initialize the mock embedding generator.

        Args:
            dimensions: Number of dimensions in generated vectors.
        """
        self._dimensions = dimensions

    async def embed_image(
        self,
        image_bytes: bytes,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Generate visual embedding from an image.

        Creates a deterministic pseudo-embedding from image content.

        Args:
            image_bytes: Image content as bytes (PNG, JPEG).
            model: Optional model override (ignored in mock).

        Returns:
            Embedding result with vector.
        """
        vector = _hash_to_vector(image_bytes, self._dimensions)
        return EmbeddingResult(
            vector=vector,
            model=model or MOCK_MODEL,
            dimensions=self._dimensions,
            usage_tokens=0,
        )

    async def embed_text(
        self,
        text: str,
        model: str | None = None,
    ) -> EmbeddingResult:
        """Generate text embedding.

        Creates a deterministic pseudo-embedding from text content.

        Args:
            text: Text to embed.
            model: Optional model override (ignored in mock).

        Returns:
            Embedding result with vector.
        """
        vector = _hash_to_vector(text.encode("utf-8"), self._dimensions)
        return EmbeddingResult(
            vector=vector,
            model=model or MOCK_MODEL,
            dimensions=self._dimensions,
            usage_tokens=len(text.split()),  # Approximate token count
        )

    async def embed_texts_batch(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> BatchEmbeddingResult:
        """Generate text embeddings in batch.

        Args:
            texts: List of texts to embed.
            model: Optional model override (ignored in mock).

        Returns:
            Batch embedding result with vectors.
        """
        embeddings = []
        total_tokens = 0

        for text in texts:
            vector = _hash_to_vector(text.encode("utf-8"), self._dimensions)
            embeddings.append(vector)
            total_tokens += len(text.split())

        return BatchEmbeddingResult(
            embeddings=embeddings,
            model=model or MOCK_MODEL,
            dimensions=self._dimensions,
            total_tokens=total_tokens,
        )

    async def embed_document_page(
        self,
        page_image: bytes,
        page_text: str | None = None,
    ) -> EmbeddingResult:
        """Generate embedding for a document page.

        Combines visual and textual features. In this mock implementation,
        we concatenate image bytes and text, then hash.

        Args:
            page_image: Page rendered as image (PNG).
            page_text: Optional extracted text for hybrid embedding.

        Returns:
            Embedding result with combined visual+text features.
        """
        # Combine image and text data
        combined_data = page_image
        if page_text:
            combined_data = page_image + b"|||" + page_text.encode("utf-8")

        vector = _hash_to_vector(combined_data, self._dimensions)

        return EmbeddingResult(
            vector=vector,
            model=MOCK_MODEL,
            dimensions=self._dimensions,
            usage_tokens=len(page_text.split()) if page_text else 0,
        )

    def get_dimensions(self, model: str | None = None) -> int:
        """Get the embedding dimensions for a model.

        Args:
            model: Model name (ignored in mock, always returns configured dimensions).

        Returns:
            Number of dimensions in the embedding vector.
        """
        return self._dimensions


# Type assertion to verify protocol compliance
_assert_embedding: EmbeddingGateway = MemoryEmbedding()
