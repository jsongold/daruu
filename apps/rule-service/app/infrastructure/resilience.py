"""Retry logic for Supabase operations.

Provides retry decorators for handling transient Supabase errors
such as 500, 502, 503, 504 errors from Cloudflare or database overload.
"""

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0


def is_retryable_error(error: Exception) -> bool:
    """Check if error is transient and worth retrying."""
    error_str = str(error).lower()

    for code in RETRYABLE_STATUS_CODES:
        if str(code) in error_str:
            return True

    transient_patterns = [
        "timeout",
        "connection",
        "temporarily unavailable",
        "service unavailable",
        "internal server error",
        "cloudflare",
        "rate limit",
        "too many requests",
        "connection reset",
        "connection refused",
        "network",
        "socket",
        "broken pipe",
        "no address",
        "hostname",
        "name resolution",
        "dns",
        "getaddrinfo",
    ]
    return any(pattern in error_str for pattern in transient_patterns)


def with_retry(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to add retry logic with exponential backoff to sync functions."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if not is_retryable_error(e) or attempt >= max_retries:
                        raise

                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        f"Retryable error in {func.__name__}, "
                        f"attempt {attempt + 1}/{max_retries + 1}, "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)

            if last_error:
                raise last_error
            raise RuntimeError("Unexpected retry loop exit")

        return wrapper

    return decorator
