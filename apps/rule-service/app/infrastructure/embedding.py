"""Embedding Gateway implementations.

Provides mock (testing) and OpenAI (production) embedding gateways.
Only embed_text() is needed for the rule service.
"""

import hashlib
import math
from typing import Any


class MockEmbeddingGateway:
    """Mock implementation for testing.

    Generates deterministic embeddings based on content hash.
    """

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    async def embed_text(self, text: str) -> list[float]:
        """Generate deterministic embedding from text."""
        return self._generate_embedding(text.encode("utf-8"))

    def _generate_embedding(self, content: bytes) -> list[float]:
        """Generate a deterministic, normalized embedding from content."""
        hash_bytes = hashlib.sha256(content).digest()

        embedding = []
        for i in range(self._dimension):
            idx = i % len(hash_bytes)
            value = (hash_bytes[idx] - 128) / 128.0
            value += (hash_bytes[(idx + 1) % len(hash_bytes)] - 128) / 256.0 * (i / self._dimension)
            embedding.append(value)

        magnitude = math.sqrt(sum(x * x for x in embedding))
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding


class OpenAIEmbeddingGateway:
    """LiteLLM-based embedding gateway for production use."""

    def __init__(
        self,
        client: Any = None,
        model: str = "text-embedding-3-small",
    ) -> None:
        self._client = client
        self._model = model

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding from text using LiteLLM or direct OpenAI client."""
        if self._client is None:
            raise ValueError("LLM client not configured")

        try:
            import litellm

            api_key = getattr(self._client, "_api_key", None)
            kwargs: dict[str, Any] = {
                "model": self._model,
                "input": [text],
            }
            if api_key:
                kwargs["api_key"] = api_key

            response = await litellm.aembedding(**kwargs)
            return response.data[0]["embedding"]

        except ImportError:
            if hasattr(self._client, "embeddings"):
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=text,
                )
                return response.data[0].embedding
            raise RuntimeError("Neither litellm nor a direct embedding client is available")
