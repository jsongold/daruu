"""Retry utilities for LLM calls with exponential backoff.

This module provides decorators and utilities for handling transient errors
in LLM API calls with configurable retry logic and exponential backoff.

Retryable errors include:
- Rate limits (429)
- Server errors (5xx)
- Network timeouts
- Transient API failures

Usage:
    @with_retry(max_retries=3, base_delay=1.0)
    async def call_llm(prompt: str) -> str:
        return await llm.ainvoke(prompt)
"""

import asyncio
import logging
import re
from functools import wraps
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class LLMRetryError(Exception):
    """Raised when all LLM retry attempts have been exhausted.

    Attributes:
        attempts: Number of attempts made
        last_error: The final error that caused failure
    """

    def __init__(
        self,
        message: str,
        attempts: int = 0,
        last_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


class RateLimitError(Exception):
    """Raised when rate limit is exceeded.

    Attributes:
        retry_after: Suggested retry delay in seconds, if available
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after


# Default retryable exceptions for LLM calls
DEFAULT_RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    OSError,
    RateLimitError,
)


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is retryable.

    Examines the error to determine if it represents a transient failure
    that should be retried.

    Args:
        error: The exception to check

    Returns:
        True if the error is retryable
    """
    # Check for standard retryable exceptions
    if isinstance(error, DEFAULT_RETRYABLE_EXCEPTIONS):
        return True

    # Check for HTTP status codes in error message
    error_str = str(error).lower()

    # Rate limit errors (429)
    if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
        return True

    # Server errors (5xx)
    for code in ["500", "502", "503", "504"]:
        if code in error_str:
            return True

    # Timeout-related errors
    if "timeout" in error_str or "timed out" in error_str:
        return True

    # Connection errors
    if "connection" in error_str and ("refused" in error_str or "reset" in error_str):
        return True

    # OpenAI specific retryable errors
    if "openai" in error_str:
        if "overloaded" in error_str or "capacity" in error_str:
            return True

    return False


def extract_retry_after(error: Exception) -> float | None:
    """Extract retry-after hint from error if available.

    Args:
        error: The exception to examine

    Returns:
        Retry delay in seconds, or None if not available
    """
    # Check for RateLimitError with retry_after
    if isinstance(error, RateLimitError) and error.retry_after:
        return error.retry_after

    # Check error message for retry-after hints
    error_str = str(error)

    patterns = [
        r"retry.after[:\s]+(\d+(?:\.\d+)?)",
        r"wait[:\s]+(\d+(?:\.\d+)?)\s*s",
        r"(\d+(?:\.\d+)?)\s*second",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_str.lower())
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return None


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    on_retry: Callable[[Exception, int], None] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator for LLM calls with exponential backoff retry logic.

    Wraps an async function to automatically retry on transient failures
    with exponential backoff between attempts.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        retryable_exceptions: Tuple of exception types to retry on.
            If None, uses is_retryable_error() for determination.
        on_retry: Optional callback called on each retry with (error, attempt)

    Returns:
        Decorated async function with retry logic

    Raises:
        LLMRetryError: When all retry attempts are exhausted

    Example:
        @with_retry(max_retries=3, base_delay=1.0)
        async def call_openai(prompt: str) -> str:
            return await openai_client.chat.completions.create(...)
    """

    def decorator(
        func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Determine if we should retry
                    should_retry = False
                    if retryable_exceptions is not None:
                        should_retry = isinstance(e, retryable_exceptions)
                    else:
                        should_retry = is_retryable_error(e)

                    # If not retryable or last attempt, raise
                    if not should_retry or attempt >= max_retries:
                        if attempt > 0:
                            logger.warning(
                                "LLM call failed after %d attempts: %s",
                                attempt + 1,
                                str(e),
                            )
                        raise

                    # Calculate delay with exponential backoff
                    retry_after = extract_retry_after(e)
                    if retry_after and retry_after > 0:
                        delay = min(retry_after, max_delay)
                    else:
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay,
                        )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt + 1)

                    logger.debug(
                        "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        str(e),
                    )

                    await asyncio.sleep(delay)

            # Should not reach here, but just in case
            raise LLMRetryError(
                f"Failed after {max_retries + 1} attempts",
                attempts=max_retries + 1,
                last_error=last_exception,
            )

        return wrapper

    return decorator


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    **kwargs: Any,
) -> T:
    """Execute an async function with retry logic.

    Functional alternative to the decorator for one-off retry needs.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Exponential backoff base
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        LLMRetryError: When all attempts are exhausted
    """
    wrapped = with_retry(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
    )(func)

    return await wrapped(*args, **kwargs)
