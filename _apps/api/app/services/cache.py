"""Request-scoped cache for rendered PDF pages.

Eliminates redundant rendering within a single request using
ContextVar for request isolation and automatic cleanup.
"""

from __future__ import annotations

import hashlib
import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.pdf_render import RenderedPage

logger = logging.getLogger(__name__)

# Cache key: (pdf_hash, page_indices_tuple, dpi, include_text_blocks)
CacheKey = tuple[str, tuple[int, ...], int, bool]
CacheValue = list[Any]  # list[RenderedPage], but using Any to avoid circular import

# Request-scoped cache storage (auto-isolated per async context)
_render_cache: ContextVar[dict[CacheKey, CacheValue]] = ContextVar(
    "render_cache", default={}
)


def compute_pdf_hash(pdf_bytes: bytes) -> str:
    """
    Compute fast hash of PDF bytes using first/last chunks + size.

    Strategy:
    - Hash first 64KB (header, metadata)
    - Hash last 64KB (may contain xref table)
    - Include total size

    This is much faster than hashing entire multi-MB files.
    Collision risk is negligible for same-request scenarios.
    """
    size = len(pdf_bytes)
    hasher = hashlib.sha256()

    # First chunk (up to 64KB)
    chunk_size = min(65536, size)
    hasher.update(pdf_bytes[:chunk_size])

    # Last chunk (if file > 64KB)
    if size > 65536:
        hasher.update(pdf_bytes[-65536:])

    # Include size to differentiate files with same header/footer
    hasher.update(str(size).encode("utf-8"))

    return hasher.hexdigest()


def get_cached_render(
    pdf_bytes: bytes,
    page_indices: list[int] | None,
    dpi: int,
    include_text_blocks: bool,
) -> list[Any] | None:
    """
    Retrieve cached rendered pages if available.

    Returns None if cache miss.
    """
    cache = _render_cache.get()
    pdf_hash = compute_pdf_hash(pdf_bytes)

    # Normalize page_indices to tuple for hashing
    # None means "all pages" - we use empty tuple as sentinel
    indices_tuple = tuple(page_indices) if page_indices else ()

    cache_key = (pdf_hash, indices_tuple, dpi, include_text_blocks)
    return cache.get(cache_key)


def set_cached_render(
    pdf_bytes: bytes,
    page_indices: list[int] | None,
    dpi: int,
    include_text_blocks: bool,
    rendered_pages: list[Any],
) -> None:
    """Store rendered pages in cache."""
    cache = _render_cache.get()
    pdf_hash = compute_pdf_hash(pdf_bytes)
    indices_tuple = tuple(page_indices) if page_indices else ()
    cache_key = (pdf_hash, indices_tuple, dpi, include_text_blocks)
    cache[cache_key] = rendered_pages


def clear_render_cache() -> None:
    """
    Clear the request-scoped cache.

    Called at end of request lifecycle by middleware.
    """
    cache = _render_cache.get()
    cache.clear()


def get_cache_stats() -> dict[str, int]:
    """
    Get cache statistics for debugging.

    Returns entry count and estimated memory usage.
    """
    cache = _render_cache.get()
    entry_count = len(cache)

    # Estimate memory (very rough)
    # Each RenderedPage ~1MB base64 PNG
    total_pages = sum(len(pages) for pages in cache.values())
    estimated_mb = total_pages * 1  # 1MB per page average

    return {
        "cache_entries": entry_count,
        "total_pages_cached": total_pages,
        "estimated_memory_mb": int(estimated_mb),
    }
