"""Cache Gateway interface.

Defines the contract for caching operations.
The primary implementation will use Redis.

Key responsibilities:
- Session state caching for conversations
- Temporary data storage during processing
- Rate limiting counters
- Job progress tracking
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    """A cached entry with metadata."""

    key: str = Field(..., description="Cache key")
    value: str = Field(..., description="Cached value (JSON string)")
    ttl_seconds: int | None = Field(None, description="Time to live in seconds")
    created_at: str = Field(..., description="ISO-8601 creation timestamp")

    model_config = {"frozen": True}


@runtime_checkable
class CacheGateway(Protocol):
    """Interface for caching operations (implemented by Redis).

    This gateway abstracts caching functionality, allowing different
    cache backends to be used (Redis, Memcached, in-memory, etc.).

    Used for:
    - Conversation session state
    - Processing progress tracking
    - Rate limiting
    - Temporary extraction results
    """

    async def get(self, key: str) -> str | None:
        """Get a cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        ...

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set a cached value.

        Args:
            key: Cache key
            value: Value to cache (should be JSON string)
            ttl_seconds: Optional TTL in seconds
        """
        ...

    async def delete(self, key: str) -> None:
        """Delete a cached value.

        Args:
            key: Cache key
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: Cache key

        Returns:
            True if key exists and not expired
        """
        ...

    async def increment(
        self,
        key: str,
        amount: int = 1,
        ttl_seconds: int | None = None,
    ) -> int:
        """Increment a counter.

        Args:
            key: Cache key
            amount: Amount to increment by
            ttl_seconds: Optional TTL (set on first increment)

        Returns:
            New counter value
        """
        ...

    async def get_json(self, key: str) -> dict | list | None:
        """Get a cached JSON value.

        Convenience method that deserializes JSON.

        Args:
            key: Cache key

        Returns:
            Deserialized JSON or None if not found
        """
        ...

    async def set_json(
        self,
        key: str,
        value: dict | list,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set a JSON value.

        Convenience method that serializes to JSON.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Optional TTL in seconds
        """
        ...

    # Session-specific convenience methods

    async def get_session(self, session_id: str) -> dict | None:
        """Get conversation session state.

        Args:
            session_id: Session/conversation ID

        Returns:
            Session state dict or None
        """
        ...

    async def set_session(
        self,
        session_id: str,
        state: dict,
        ttl_seconds: int = 3600,
    ) -> None:
        """Save conversation session state.

        Args:
            session_id: Session/conversation ID
            state: Session state dict
            ttl_seconds: TTL (default 1 hour)
        """
        ...

    async def delete_session(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session/conversation ID
        """
        ...

    # Rate limiting convenience methods

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """Check and increment rate limit counter.

        Args:
            key: Rate limit key (e.g., f"rate:{user_id}:{endpoint}")
            limit: Maximum requests allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        ...
