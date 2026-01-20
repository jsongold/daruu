"""Global HTTP Client Manager with connection pooling.

Provides singleton async HTTP clients for:
1. LLM API calls (OpenAI) - long timeout, limited concurrency
2. General HTTP calls (PDF downloads) - short timeout, higher concurrency
"""

from __future__ import annotations

import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Global client instances (initialized by lifespan)
_llm_client: httpx.AsyncClient | None = None
_general_client: httpx.AsyncClient | None = None


def get_llm_client() -> httpx.AsyncClient:
    """Get the global LLM API client."""
    if _llm_client is None:
        raise RuntimeError("LLM HTTP client not initialized. Call initialize_clients() first.")
    return _llm_client


def get_general_client() -> httpx.AsyncClient:
    """Get the general purpose HTTP client."""
    if _general_client is None:
        raise RuntimeError("General HTTP client not initialized. Call initialize_clients() first.")
    return _general_client


async def initialize_clients() -> None:
    """Initialize global HTTP clients with connection pooling."""
    global _llm_client, _general_client

    # LLM Client Configuration
    # - Long timeout for LLM processing
    # - Limited concurrency to respect rate limits
    # - Connection pooling to reuse connections
    llm_timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "120.0"))
    llm_limits = httpx.Limits(
        max_keepalive_connections=5,  # Keep 5 connections alive
        max_connections=10,  # Max 10 concurrent connections
        keepalive_expiry=30.0  # Keep connections alive for 30s
    )

    _llm_client = httpx.AsyncClient(
        timeout=httpx.Timeout(llm_timeout_seconds),
        limits=llm_limits,
        http2=True,  # Enable HTTP/2 for better multiplexing
    )

    # General Client Configuration
    # - Shorter timeout for quick operations
    # - Higher concurrency for parallel downloads
    general_limits = httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20,
        keepalive_expiry=30.0
    )

    _general_client = httpx.AsyncClient(
        timeout=httpx.Timeout(20.0),
        limits=general_limits,
        http2=True,
    )

    logger.info(
        "HTTP clients initialized: LLM (timeout=%.1fs, max_conn=%d), General (timeout=%.1fs, max_conn=%d)",
        llm_timeout_seconds,
        llm_limits.max_connections,
        20.0,
        general_limits.max_connections,
    )


async def shutdown_clients() -> None:
    """Cleanup HTTP clients on shutdown."""
    global _llm_client, _general_client

    if _llm_client is not None:
        await _llm_client.aclose()
        _llm_client = None
        logger.info("LLM HTTP client closed")

    if _general_client is not None:
        await _general_client.aclose()
        _general_client = None
        logger.info("General HTTP client closed")
