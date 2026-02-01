"""Retry logic for Supabase operations.

This module provides retry decorators for handling transient Supabase errors
such as 500, 502, 503, 504 errors from Cloudflare or database overload.
"""

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# HTTP status codes that indicate transient errors worth retrying
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 30.0


def is_retryable_error(error: Exception) -> bool:
    """Check if error is transient and worth retrying.

    Args:
        error: The exception to check.

    Returns:
        True if the error is likely transient and should be retried.
    """
    error_str = str(error).lower()

    # Check for HTTP status codes
    for code in RETRYABLE_STATUS_CODES:
        if str(code) in error_str:
            return True

    # Check for common transient error patterns
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
        # DNS resolution errors
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
    """Decorator to add retry logic with exponential backoff to sync functions.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.

    Returns:
        Decorated function with retry logic.

    Example:
        @with_retry(max_retries=3, base_delay=1.0)
        def get_data():
            return client.table("users").select("*").execute()
    """

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


def with_retry_result(
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> Callable[[Callable[..., T | None]], Callable[..., T | None]]:
    """Decorator that retries on retryable errors but returns None for non-retryable errors.

    This is useful for get() methods that should return None on 404 but retry on 500.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.

    Returns:
        Decorated function with retry logic that returns None on non-retryable errors.
    """

    def decorator(func: Callable[..., T | None]) -> Callable[..., T | None]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T | None:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if not is_retryable_error(e):
                        # Non-retryable error (e.g., 404) - log and return None
                        logger.debug(
                            f"Non-retryable error in {func.__name__}: {e}"
                        )
                        return None

                    if attempt >= max_retries:
                        # Exhausted retries - log and return None
                        logger.error(
                            f"Exhausted retries in {func.__name__} after "
                            f"{max_retries + 1} attempts: {e}"
                        )
                        return None

                    delay = min(base_delay * (2**attempt), max_delay)
                    logger.warning(
                        f"Retryable error in {func.__name__}, "
                        f"attempt {attempt + 1}/{max_retries + 1}, "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    time.sleep(delay)

            return None

        return wrapper

    return decorator
