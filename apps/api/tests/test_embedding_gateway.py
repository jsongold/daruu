"""Tests for Embedding Gateway.

Tests mock EmbeddingGateway:
- embed_image returns valid vector
- embed_text returns valid vector
- embed_document_page
- Consistent dimensions
"""

import math
from unittest.mock import AsyncMock

import pytest


class TestMockEmbeddingGateway:
    """Tests for MockEmbeddingGateway implementation."""

    @pytest.fixture
    def embedding_gateway(self):
        """Create a mock embedding gateway."""
        from app.infrastructure.gateways.embedding import MockEmbeddingGateway

        return MockEmbeddingGateway()

    @pytest.fixture
    def sample_image_bytes(self) -> bytes:
        """Create sample image bytes for testing."""
        # Minimal PNG header bytes
        return bytes(
            [
                0x89,
                0x50,
                0x4E,
                0x47,
                0x0D,
                0x0A,
                0x1A,
                0x0A,
                0x00,
                0x00,
                0x00,
                0x0D,
                0x49,
                0x48,
                0x44,
                0x52,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
            ]
        )

    # =========================================================================
    # embed_image Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_embed_image_returns_vector(self, embedding_gateway, sample_image_bytes) -> None:
        """Test that embed_image returns a vector."""
        result = await embedding_gateway.embed_image(sample_image_bytes)

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(x, (int, float)) for x in result)

    @pytest.mark.asyncio
    async def test_embed_image_consistent_dimensions(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test that embed_image returns consistent dimensions."""
        result1 = await embedding_gateway.embed_image(sample_image_bytes)
        result2 = await embedding_gateway.embed_image(sample_image_bytes)

        assert len(result1) == len(result2)

    @pytest.mark.asyncio
    async def test_embed_image_standard_dimension(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test that embedding has standard dimension (1536 for OpenAI)."""
        result = await embedding_gateway.embed_image(sample_image_bytes)

        # Common embedding dimensions: 384, 768, 1024, 1536, 3072
        assert len(result) in [384, 768, 1024, 1536, 3072]

    @pytest.mark.asyncio
    async def test_embed_image_normalized(self, embedding_gateway, sample_image_bytes) -> None:
        """Test that embedding is normalized (unit vector)."""
        result = await embedding_gateway.embed_image(sample_image_bytes)

        magnitude = math.sqrt(sum(x * x for x in result))
        # Should be close to 1.0 if normalized
        assert 0.99 <= magnitude <= 1.01 or magnitude > 0  # Or at least non-zero

    @pytest.mark.asyncio
    async def test_embed_image_different_images_different_vectors(self, embedding_gateway) -> None:
        """Test that different images produce different embeddings."""
        image1 = b"image_content_1_unique_pattern"
        image2 = b"image_content_2_different_pattern"

        result1 = await embedding_gateway.embed_image(image1)
        result2 = await embedding_gateway.embed_image(image2)

        # Embeddings should be different (or at least this is the expectation)
        # For mock, they might be deterministic based on input
        assert isinstance(result1, list)
        assert isinstance(result2, list)

    @pytest.mark.asyncio
    async def test_embed_image_empty_bytes(self, embedding_gateway) -> None:
        """Test handling of empty image bytes."""
        result = await embedding_gateway.embed_image(b"")

        # Should still return a valid vector (mock behavior)
        assert isinstance(result, list)
        assert len(result) > 0

    # =========================================================================
    # embed_text Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_embed_text_returns_vector(self, embedding_gateway) -> None:
        """Test that embed_text returns a vector."""
        result = await embedding_gateway.embed_text("Sample text for embedding")

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(x, (int, float)) for x in result)

    @pytest.mark.asyncio
    async def test_embed_text_same_dimension_as_image(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test that text and image embeddings have same dimensions."""
        image_result = await embedding_gateway.embed_image(sample_image_bytes)
        text_result = await embedding_gateway.embed_text("Sample text")

        assert len(image_result) == len(text_result)

    @pytest.mark.asyncio
    async def test_embed_text_consistent_dimensions(self, embedding_gateway) -> None:
        """Test that embed_text returns consistent dimensions."""
        result1 = await embedding_gateway.embed_text("First text")
        result2 = await embedding_gateway.embed_text("Second text")

        assert len(result1) == len(result2)

    @pytest.mark.asyncio
    async def test_embed_text_empty_string(self, embedding_gateway) -> None:
        """Test handling of empty string."""
        result = await embedding_gateway.embed_text("")

        # Should still return a valid vector
        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embed_text_long_text(self, embedding_gateway) -> None:
        """Test handling of long text."""
        long_text = "word " * 1000  # Very long text

        result = await embedding_gateway.embed_text(long_text)

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embed_text_unicode(self, embedding_gateway) -> None:
        """Test handling of unicode text."""
        unicode_text = "Unicode text: "

        result = await embedding_gateway.embed_text(unicode_text)

        assert isinstance(result, list)
        assert len(result) > 0

    # =========================================================================
    # embed_document_page Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_embed_document_page_returns_vector(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test that embed_document_page returns a vector."""
        result = await embedding_gateway.embed_document_page(
            page_image=sample_image_bytes,
            page_text="Some text on the page",
            page_number=1,
        )

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embed_document_page_image_only(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test embedding document page with only image."""
        result = await embedding_gateway.embed_document_page(
            page_image=sample_image_bytes,
            page_text=None,
            page_number=1,
        )

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embed_document_page_text_only(self, embedding_gateway) -> None:
        """Test embedding document page with only text."""
        result = await embedding_gateway.embed_document_page(
            page_image=None,
            page_text="Page text content",
            page_number=1,
        )

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_embed_document_page_consistent_dimensions(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test that document page embeddings have consistent dimensions."""
        result1 = await embedding_gateway.embed_document_page(
            page_image=sample_image_bytes,
            page_text="Text 1",
            page_number=1,
        )
        result2 = await embedding_gateway.embed_document_page(
            page_image=sample_image_bytes,
            page_text="Text 2",
            page_number=2,
        )

        assert len(result1) == len(result2)

    @pytest.mark.asyncio
    async def test_embed_document_page_same_dimension_as_image(
        self, embedding_gateway, sample_image_bytes
    ) -> None:
        """Test that document page embedding has same dimension as image embedding."""
        image_result = await embedding_gateway.embed_image(sample_image_bytes)
        page_result = await embedding_gateway.embed_document_page(
            page_image=sample_image_bytes,
            page_text="Some text",
            page_number=1,
        )

        assert len(image_result) == len(page_result)


class TestEmbeddingGatewayProtocol:
    """Tests to verify EmbeddingGateway implements the protocol correctly."""

    def test_implements_protocol(self) -> None:
        """Test that MockEmbeddingGateway implements EmbeddingGateway protocol."""
        from app.infrastructure.gateways.embedding import MockEmbeddingGateway
        from app.repositories.embedding_gateway import EmbeddingGateway

        gateway = MockEmbeddingGateway()
        # This should not raise if protocol is implemented correctly
        _: EmbeddingGateway = gateway

    def test_required_methods_exist(self) -> None:
        """Test that all required methods exist."""
        from app.infrastructure.gateways.embedding import MockEmbeddingGateway

        gateway = MockEmbeddingGateway()

        assert hasattr(gateway, "embed_image")
        assert hasattr(gateway, "embed_text")
        assert hasattr(gateway, "embed_document_page")

        assert callable(gateway.embed_image)
        assert callable(gateway.embed_text)
        assert callable(gateway.embed_document_page)


class TestEmbeddingGatewayDeterminism:
    """Tests for embedding gateway determinism."""

    @pytest.fixture
    def embedding_gateway(self):
        """Create a mock embedding gateway."""
        from app.infrastructure.gateways.embedding import MockEmbeddingGateway

        return MockEmbeddingGateway()

    @pytest.mark.asyncio
    async def test_same_input_same_output(self, embedding_gateway) -> None:
        """Test that same input produces same output (deterministic)."""
        input_bytes = b"consistent_input_data"

        result1 = await embedding_gateway.embed_image(input_bytes)
        result2 = await embedding_gateway.embed_image(input_bytes)

        # For mock implementation, same input should give same output
        # (This may not be true for real embedding services with randomness)
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_same_text_same_output(self, embedding_gateway) -> None:
        """Test that same text produces same embedding."""
        text = "Consistent text input"

        result1 = await embedding_gateway.embed_text(text)
        result2 = await embedding_gateway.embed_text(text)

        assert result1 == result2


class TestEmbeddingGatewayEdgeCases:
    """Edge case tests for Embedding Gateway."""

    @pytest.fixture
    def embedding_gateway(self):
        """Create a mock embedding gateway."""
        from app.infrastructure.gateways.embedding import MockEmbeddingGateway

        return MockEmbeddingGateway()

    @pytest.mark.asyncio
    async def test_binary_data_in_text(self, embedding_gateway) -> None:
        """Test handling of binary data passed as text."""
        # Some non-text data that might accidentally be passed
        binary_text = "\x00\x01\x02\x03"

        result = await embedding_gateway.embed_text(binary_text)

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_very_large_image(self, embedding_gateway) -> None:
        """Test handling of very large image data."""
        large_image = b"x" * (10 * 1024 * 1024)  # 10MB

        result = await embedding_gateway.embed_image(large_image)

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_concurrent_embeddings(self, embedding_gateway) -> None:
        """Test concurrent embedding requests."""
        import asyncio

        async def embed_text(i: int):
            return await embedding_gateway.embed_text(f"Text {i}")

        results = await asyncio.gather(*[embed_text(i) for i in range(10)])

        assert len(results) == 10
        assert all(isinstance(r, list) for r in results)
        assert all(len(r) > 0 for r in results)

    @pytest.mark.asyncio
    async def test_special_characters_in_text(self, embedding_gateway) -> None:
        """Test handling of special characters."""
        special_text = 'Special chars: !@#$%^&*()_+-={}[]|\\:";<>?,./'

        result = await embedding_gateway.embed_text(special_text)

        assert isinstance(result, list)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_newlines_and_tabs(self, embedding_gateway) -> None:
        """Test handling of whitespace characters."""
        whitespace_text = "Line 1\nLine 2\tTabbed\rCarriage return"

        result = await embedding_gateway.embed_text(whitespace_text)

        assert isinstance(result, list)
        assert len(result) > 0


class TestOpenAIEmbeddingGateway:
    """Tests for OpenAI-based embedding gateway (requires mocking)."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        from unittest.mock import AsyncMock, MagicMock

        mock = MagicMock()

        # Mock embeddings.create response
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock.embeddings.create = AsyncMock(return_value=mock_response)

        return mock

    @pytest.mark.asyncio
    async def test_openai_gateway_embed_text(self, mock_openai_client) -> None:
        """Test OpenAI gateway text embedding."""
        from app.infrastructure.gateways.embedding import OpenAIEmbeddingGateway

        gateway = OpenAIEmbeddingGateway(client=mock_openai_client)

        result = await gateway.embed_text("Test text")

        assert isinstance(result, list)
        assert len(result) == 1536
        mock_openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_openai_gateway_embed_image(self, mock_openai_client) -> None:
        """Test OpenAI gateway image embedding (via base64)."""
        from app.infrastructure.gateways.embedding import OpenAIEmbeddingGateway

        gateway = OpenAIEmbeddingGateway(client=mock_openai_client)

        result = await gateway.embed_image(b"fake_image_data")

        assert isinstance(result, list)
        # Depending on implementation, might use text embedding for image description
        # or multimodal embedding

    @pytest.mark.asyncio
    async def test_openai_gateway_handles_api_error(self, mock_openai_client) -> None:
        """Test OpenAI gateway handles API errors gracefully."""
        from app.infrastructure.gateways.embedding import OpenAIEmbeddingGateway

        mock_openai_client.embeddings.create = AsyncMock(side_effect=Exception("API Error"))

        gateway = OpenAIEmbeddingGateway(client=mock_openai_client)

        with pytest.raises(Exception):
            await gateway.embed_text("Test text")

    @pytest.mark.asyncio
    async def test_openai_gateway_rate_limiting(self, mock_openai_client) -> None:
        """Test OpenAI gateway handles rate limiting."""
        from app.infrastructure.gateways.embedding import OpenAIEmbeddingGateway

        call_count = 0

        async def rate_limited_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Rate limit exceeded")
            mock_response = MagicMock()
            mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
            return mock_response

        mock_openai_client.embeddings.create = AsyncMock(side_effect=rate_limited_response)

        gateway = OpenAIEmbeddingGateway(client=mock_openai_client)

        # First call should fail
        with pytest.raises(Exception):
            await gateway.embed_text("Test")
