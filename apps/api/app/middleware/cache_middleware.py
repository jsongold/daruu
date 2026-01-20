"""Middleware to manage request-scoped render cache lifecycle.

Ensures cache is cleared after each request to prevent memory leaks
and request isolation.
"""

import logging
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.cache import clear_render_cache, get_cache_stats

logger = logging.getLogger(__name__)
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


class RenderCacheMiddleware(BaseHTTPMiddleware):
    """
    Manages lifecycle of request-scoped PDF render cache.

    - Cache is automatically created per request (via ContextVar)
    - Cleared after response is sent (in finally block)
    - Logs cache stats in DEBUG mode
    """

    async def dispatch(self, request: Request, call_next):
        # ContextVar creates isolated cache per async context automatically
        # No explicit initialization needed

        try:
            response = await call_next(request)

            # Log cache statistics before clearing (DEBUG mode)
            if DEBUG:
                stats = get_cache_stats()
                logger.info(
                    "Render cache stats: %d entries, %d pages, ~%d MB",
                    stats["cache_entries"],
                    stats["total_pages_cached"],
                    stats["estimated_memory_mb"],
                )

            return response

        finally:
            # Always clear cache after request
            clear_render_cache()
