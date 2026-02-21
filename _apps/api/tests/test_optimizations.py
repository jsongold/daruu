"""Tests for LLM performance optimization features."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache import (
    clear_render_cache,
    compute_pdf_hash,
    get_cache_stats,
    get_cached_render,
    set_cached_render,
)
from app.services.http_client import (
    get_general_client,
    get_llm_client,
    initialize_clients,
    shutdown_clients,
)
from app.services.pdf_render import RenderedPage


class TestHTTPClientManagement:
    """Test global HTTP client lifecycle management."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test that clients are initialized properly."""
        await initialize_clients()

        llm_client = get_llm_client()
        general_client = get_general_client()

        assert llm_client is not None
        assert general_client is not None
        assert not llm_client.is_closed
        assert not general_client.is_closed

        await shutdown_clients()

        assert llm_client.is_closed
        assert general_client.is_closed

    @pytest.mark.asyncio
    async def test_get_client_before_init(self):
        """Test that getting client before init raises error."""
        # Clear global state
        await shutdown_clients()

        with pytest.raises(RuntimeError, match="not initialized"):
            get_llm_client()

        # Re-initialize for other tests
        await initialize_clients()

    @pytest.mark.asyncio
    async def test_client_connection_limits(self):
        """Test that clients have connection limits configured."""
        await initialize_clients()

        llm_client = get_llm_client()
        general_client = get_general_client()

        # Check LLM client limits
        assert llm_client._limits.max_connections == 10
        assert llm_client._limits.max_keepalive_connections == 5

        # Check general client limits
        assert general_client._limits.max_connections == 20
        assert general_client._limits.max_keepalive_connections == 10

        await shutdown_clients()


class TestRenderCache:
    """Test request-scoped PDF render cache."""

    def test_pdf_hash_computation(self):
        """Test that PDF hashing is consistent."""
        pdf_bytes_1 = b"PDF content here"
        pdf_bytes_2 = b"PDF content here"
        pdf_bytes_3 = b"Different content"

        hash_1 = compute_pdf_hash(pdf_bytes_1)
        hash_2 = compute_pdf_hash(pdf_bytes_2)
        hash_3 = compute_pdf_hash(pdf_bytes_3)

        assert hash_1 == hash_2
        assert hash_1 != hash_3
        assert len(hash_1) == 64  # SHA-256 hex string

    def test_cache_hit_miss(self):
        """Test basic cache hit and miss."""
        clear_render_cache()

        pdf_bytes = b"test pdf"
        page = RenderedPage(
            index=0,
            width=612.0,
            height=792.0,
            png_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA",
            text_blocks=None,
            visual_anchors=[],
        )
        pages = [page]

        # Cache miss
        assert get_cached_render(pdf_bytes, None, 150, True) is None

        # Store in cache
        set_cached_render(pdf_bytes, None, 150, True, pages)

        # Cache hit
        cached = get_cached_render(pdf_bytes, None, 150, True)
        assert cached == pages

        # Different parameters = miss
        assert get_cached_render(pdf_bytes, None, 200, True) is None
        assert get_cached_render(pdf_bytes, None, 150, False) is None

        clear_render_cache()

    def test_cache_with_page_indices(self):
        """Test cache with specific page indices."""
        clear_render_cache()

        pdf_bytes = b"test pdf"
        page = RenderedPage(
            index=0,
            width=612.0,
            height=792.0,
            png_base64="base64...",
            text_blocks=None,
        )

        # Cache with page subset
        set_cached_render(pdf_bytes, [0, 1], 150, False, [page])

        # Miss with different page indices
        assert get_cached_render(pdf_bytes, [0, 1, 2], 150, False) is None

        # Hit with same page indices
        assert get_cached_render(pdf_bytes, [0, 1], 150, False) is not None

        clear_render_cache()

    def test_cache_statistics(self):
        """Test cache statistics tracking."""
        clear_render_cache()

        pdf_bytes = b"test pdf"
        page = RenderedPage(
            index=0,
            width=612.0,
            height=792.0,
            png_base64="base64...",
            text_blocks=None,
        )

        # Cache is empty
        stats = get_cache_stats()
        assert stats["cache_entries"] == 0
        assert stats["total_pages_cached"] == 0

        # Add entries
        set_cached_render(pdf_bytes, None, 150, True, [page])
        set_cached_render(pdf_bytes, None, 150, False, [page])

        # Check stats
        stats = get_cache_stats()
        assert stats["cache_entries"] == 2
        assert stats["total_pages_cached"] == 2
        assert stats["estimated_memory_mb"] > 0

        clear_render_cache()

    def test_cache_clear(self):
        """Test that cache can be cleared."""
        clear_render_cache()

        pdf_bytes = b"test pdf"
        page = RenderedPage(
            index=0,
            width=612.0,
            height=792.0,
            png_base64="base64...",
            text_blocks=None,
        )

        set_cached_render(pdf_bytes, None, 150, True, [page])

        # Verify cached
        assert get_cached_render(pdf_bytes, None, 150, True) is not None

        # Clear
        clear_render_cache()

        # Verify cleared
        assert get_cached_render(pdf_bytes, None, 150, True) is None


class TestAsyncConverting:
    """Test that async methods work correctly."""

    @pytest.mark.asyncio
    async def test_concurrent_request_limit(self):
        """Test that OPENAI_MAX_CONCURRENT_REQUESTS is respected."""
        from app.services.analysis.strategies import (
            OPENAI_MAX_CONCURRENT_REQUESTS,
        )

        # Default should be 5
        assert OPENAI_MAX_CONCURRENT_REQUESTS >= 1
        assert OPENAI_MAX_CONCURRENT_REQUESTS <= 20

    @pytest.mark.asyncio
    async def test_semaphore_concurrency(self):
        """Test semaphore-based concurrency limiting."""
        max_concurrent = 3
        semaphore = asyncio.Semaphore(max_concurrent)

        concurrent_count = 0
        max_seen = 0

        async def task():
            nonlocal concurrent_count, max_seen

            async with semaphore:
                concurrent_count += 1
                max_seen = max(max_seen, concurrent_count)
                await asyncio.sleep(0.01)
                concurrent_count -= 1

        # Create 10 tasks but limit to 3 concurrent
        tasks = [task() for _ in range(10)]
        await asyncio.gather(*tasks)

        assert max_seen <= max_concurrent


class TestConfigurationIntegration:
    """Test configuration environment variables."""

    def test_openai_max_concurrent_requests_env(self):
        """Test OPENAI_MAX_CONCURRENT_REQUESTS env variable."""
        from app.services.analysis.strategies import (
            OPENAI_MAX_CONCURRENT_REQUESTS,
        )

        # Should have a default value
        assert isinstance(OPENAI_MAX_CONCURRENT_REQUESTS, int)
        assert 1 <= OPENAI_MAX_CONCURRENT_REQUESTS <= 20

    def test_openai_timeout_env(self):
        """Test OPENAI_TIMEOUT_SECONDS env variable."""
        timeout_str = os.getenv("OPENAI_TIMEOUT_SECONDS", "120.0")
        timeout = float(timeout_str)
        assert timeout > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
