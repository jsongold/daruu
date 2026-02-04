"""
MCP Session Management.

Manages MCP sessions and links them to SaaS users.
Implements the Y Pattern for authentication.

Session flow:
1. Claude starts conversation → session_token generated
2. link_session called → check for existing auth
3. If logged in → auto-link user_id to session
4. If not logged in → return login URL
5. After login → session linked, entitlements checked

Storage:
- Redis: Used in dev/prod for persistent session storage
- In-memory: Used only for tests (when Redis unavailable)
"""

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from contextvars import ContextVar

from app.config import get_settings

# Context variable to store current session ID for tool handlers
_current_session_id: ContextVar[str | None] = ContextVar(
    "current_session_id", default=None
)

# Redis client singleton
_redis_client: Any = None
_use_memory_fallback: bool = False
_memory_sessions: dict[str, dict[str, Any]] = {}

SESSION_PREFIX = "mcp:session:"
SESSION_TTL = 3600  # 1 hour


def _get_redis_client() -> Any:
    """Get or create Redis client."""
    global _redis_client, _use_memory_fallback

    if _use_memory_fallback:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/2")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        # Test connection
        _redis_client.ping()
        return _redis_client
    except Exception:
        # Fallback to in-memory for tests
        _use_memory_fallback = True
        return None


async def get_current_session() -> dict[str, Any] | None:
    """Get the current MCP session from storage."""
    session_id = _current_session_id.get()
    if not session_id:
        return None

    client = _get_redis_client()
    if client:
        data = client.get(f"{SESSION_PREFIX}{session_id}")
        if data:
            return json.loads(data)
        return None
    else:
        return _memory_sessions.get(session_id)


async def save_session(session: dict[str, Any]) -> None:
    """Save session to storage."""
    session_id = session.get("id")
    if not session_id:
        return

    client = _get_redis_client()
    if client:
        client.setex(
            f"{SESSION_PREFIX}{session_id}",
            SESSION_TTL,
            json.dumps(session),
        )
    else:
        _memory_sessions[session_id] = session


def set_current_session(session: dict[str, Any] | None) -> None:
    """Set the current MCP session ID in context and save to storage."""
    if session:
        _current_session_id.set(session.get("id"))
        # Save synchronously for initialization
        client = _get_redis_client()
        if client:
            client.setex(
                f"{SESSION_PREFIX}{session['id']}",
                SESSION_TTL,
                json.dumps(session),
            )
        else:
            _memory_sessions[session["id"]] = session
    else:
        _current_session_id.set(None)


class MCPSessionManager:
    """
    Manages MCP sessions with Supabase persistence.

    Sessions are:
    - Short-lived (default: 1 hour)
    - One-time linkable (to prevent token replay)
    - Hashed for storage (security)
    """

    def __init__(self) -> None:
        """Initialize session manager."""
        self._settings = get_settings()
        self._session_ttl = timedelta(hours=1)

    async def create_session(self) -> dict[str, Any]:
        """
        Create a new MCP session.

        Returns:
            Dict with:
                - id: Session ID (internal)
                - token: Session token (for client)
                - expires_at: Expiration timestamp
        """
        session_id = secrets.token_urlsafe(32)
        session_token = secrets.token_urlsafe(48)
        token_hash = self._hash_token(session_token)

        expires_at = datetime.now(timezone.utc) + self._session_ttl

        session = {
            "id": session_id,
            "token_hash": token_hash,
            "user_id": None,
            "linked": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
            "form_ids": [],
            "source_doc_ids": [],
        }

        # Store session
        await self._store_session(session)

        return {
            "id": session_id,
            "token": session_token,
            "expires_at": expires_at.isoformat(),
        }

    async def get_session(self, session_token: str) -> dict[str, Any] | None:
        """
        Get a session by token.

        Args:
            session_token: The session token from client

        Returns:
            Session dict or None if invalid/expired
        """
        token_hash = self._hash_token(session_token)

        session = await self._get_session_by_hash(token_hash)

        if not session:
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            await self._delete_session(session["id"])
            return None

        return session

    async def link_session(
        self,
        session_token: str,
        user_id: str,
    ) -> bool:
        """
        Link a session to a user.

        Args:
            session_token: Session token
            user_id: User ID from Supabase Auth

        Returns:
            True if linked successfully
        """
        session = await self.get_session(session_token)

        if not session:
            return False

        if session.get("linked"):
            # Already linked - check if same user
            return session.get("user_id") == user_id

        session["user_id"] = user_id
        session["linked"] = True
        session["linked_at"] = datetime.now(timezone.utc).isoformat()

        await self._update_session(session)

        return True

    async def get_login_url(self, session_token: str) -> str:
        """
        Generate a login URL with session callback.

        Args:
            session_token: Session token to include in callback

        Returns:
            Login URL with session parameter
        """
        base_url = self._settings.app_url or "https://daru-pdf.io"
        # URL-safe session token is already suitable for query params
        return f"{base_url}/auth/login?mcp_session={session_token}"

    async def get_user_entitlements(self, user_id: str) -> dict[str, Any]:
        """
        Get user's entitlements from database.

        Args:
            user_id: User ID

        Returns:
            Dict with:
                - plan: 'free', 'pro', or 'enterprise'
                - exports_remaining: Number of exports left
                - exports_total: Total exports for plan
                - features: List of enabled features
        """
        # Query entitlements from Supabase
        entitlements = await self._get_entitlements(user_id)

        if not entitlements:
            # Default to free tier
            return {
                "plan": "free",
                "exports_remaining": 5,
                "exports_total": 5,
                "features": ["basic_fill", "preview", "edit"],
            }

        return entitlements

    async def use_export(self, user_id: str) -> bool:
        """
        Decrement user's export count.

        Args:
            user_id: User ID

        Returns:
            True if decremented successfully
        """
        entitlements = await self._get_entitlements(user_id)

        if not entitlements:
            return False

        if entitlements.get("plan") != "free":
            # Pro/Enterprise have unlimited
            return True

        remaining = entitlements.get("exports_remaining", 0)
        if remaining <= 0:
            return False

        entitlements["exports_remaining"] = remaining - 1
        await self._update_entitlements(user_id, entitlements)

        return True

    def _hash_token(self, token: str) -> str:
        """Hash a token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    # Storage methods - Redis with in-memory fallback for tests

    async def _store_session(self, session: dict[str, Any]) -> None:
        """Store session in Redis."""
        client = _get_redis_client()
        if client:
            # Store session by ID
            client.setex(
                f"{SESSION_PREFIX}{session['id']}",
                SESSION_TTL,
                json.dumps(session),
            )
            # Also index by token hash for lookup
            client.setex(
                f"{SESSION_PREFIX}hash:{session['token_hash']}",
                SESSION_TTL,
                session["id"],
            )
        else:
            _memory_sessions[session["id"]] = session

    async def _get_session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        """Get session by token hash from Redis."""
        client = _get_redis_client()
        if client:
            session_id = client.get(f"{SESSION_PREFIX}hash:{token_hash}")
            if session_id:
                data = client.get(f"{SESSION_PREFIX}{session_id}")
                if data:
                    return json.loads(data)
            return None
        else:
            for session in _memory_sessions.values():
                if session.get("token_hash") == token_hash:
                    return session
            return None

    async def _update_session(self, session: dict[str, Any]) -> None:
        """Update session in Redis."""
        client = _get_redis_client()
        if client:
            client.setex(
                f"{SESSION_PREFIX}{session['id']}",
                SESSION_TTL,
                json.dumps(session),
            )
        else:
            _memory_sessions[session["id"]] = session

    async def _delete_session(self, session_id: str) -> None:
        """Delete session from Redis."""
        client = _get_redis_client()
        if client:
            # Get session to find token hash
            data = client.get(f"{SESSION_PREFIX}{session_id}")
            if data:
                session = json.loads(data)
                token_hash = session.get("token_hash")
                if token_hash:
                    client.delete(f"{SESSION_PREFIX}hash:{token_hash}")
            client.delete(f"{SESSION_PREFIX}{session_id}")
        else:
            if session_id in _memory_sessions:
                del _memory_sessions[session_id]

    async def _get_entitlements(self, user_id: str) -> dict[str, Any] | None:
        """Get user entitlements from Redis."""
        client = _get_redis_client()
        if client:
            data = client.get(f"mcp:entitlements:{user_id}")
            if data:
                return json.loads(data)
        # Return default for now (will be replaced with Supabase query)
        return {
            "plan": "free",
            "exports_remaining": 5,
            "exports_total": 5,
            "features": ["basic_fill", "preview", "edit"],
        }

    async def _update_entitlements(
        self,
        user_id: str,
        entitlements: dict[str, Any],
    ) -> None:
        """Update user entitlements in Redis."""
        client = _get_redis_client()
        if client:
            client.setex(
                f"mcp:entitlements:{user_id}",
                SESSION_TTL,
                json.dumps(entitlements),
            )
