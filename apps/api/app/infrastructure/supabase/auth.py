"""Supabase Auth adapter.

Provides authentication functionality using Supabase Auth.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.infrastructure.supabase.client import get_supabase_client


class AuthUser(BaseModel):
    """Authenticated user information."""

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    role: str = Field(default="user", description="User role")
    metadata: dict[str, str] = Field(default_factory=dict, description="User metadata")

    model_config = {"frozen": True}


class AuthSession(BaseModel):
    """Authentication session."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str | None = Field(None, description="Refresh token")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: AuthUser = Field(..., description="Authenticated user")

    model_config = {"frozen": True}


@runtime_checkable
class AuthGateway(Protocol):
    """Interface for authentication operations."""

    async def sign_in(self, email: str, password: str) -> AuthSession:
        """Sign in with email and password."""
        ...

    async def sign_up(
        self, email: str, password: str, metadata: dict[str, str] | None = None
    ) -> AuthSession:
        """Sign up a new user."""
        ...

    async def sign_out(self, access_token: str) -> None:
        """Sign out the current user."""
        ...

    async def get_user(self, access_token: str) -> AuthUser | None:
        """Get user from access token."""
        ...

    async def refresh_token(self, refresh_token: str) -> AuthSession:
        """Refresh the access token."""
        ...

    async def verify_token(self, access_token: str) -> bool:
        """Verify if a token is valid."""
        ...


@dataclass
class SupabaseAuthAdapter:
    """Supabase Auth implementation.

    This adapter implements the AuthGateway interface using Supabase Auth.
    Currently a stub implementation - will be completed when Supabase is configured.
    """

    async def sign_in(self, email: str, password: str) -> AuthSession:
        """Sign in with email and password.

        Args:
            email: User email
            password: User password

        Returns:
            Authentication session with tokens and user info

        Raises:
            NotImplementedError: Supabase Auth not configured
            AuthenticationError: Invalid credentials
        """
        client = get_supabase_client()

        # This will raise NotImplementedError if Supabase is not configured
        result = await client.auth.sign_in_with_password(email, password)

        # Parse response (actual structure depends on supabase-py version)
        user_data = result.get("user", {})
        session_data = result.get("session", {})

        user = AuthUser(
            id=user_data.get("id", ""),
            email=user_data.get("email", ""),
            role=user_data.get("role", "user"),
            metadata=user_data.get("user_metadata", {}),
        )

        return AuthSession(
            access_token=session_data.get("access_token", ""),
            refresh_token=session_data.get("refresh_token"),
            expires_in=session_data.get("expires_in", 3600),
            user=user,
        )

    async def sign_up(
        self, email: str, password: str, metadata: dict[str, str] | None = None
    ) -> AuthSession:
        """Sign up a new user.

        Args:
            email: User email
            password: User password
            metadata: Optional user metadata

        Returns:
            Authentication session with tokens and user info

        Raises:
            NotImplementedError: Supabase Auth not configured
            RegistrationError: Registration failed
        """
        client = get_supabase_client()

        # This will raise NotImplementedError if Supabase is not configured
        result = await client.auth.sign_up(email, password)

        # Parse response
        user_data = result.get("user", {})
        session_data = result.get("session", {})

        user = AuthUser(
            id=user_data.get("id", ""),
            email=user_data.get("email", ""),
            role=user_data.get("role", "user"),
            metadata=metadata or {},
        )

        return AuthSession(
            access_token=session_data.get("access_token", ""),
            refresh_token=session_data.get("refresh_token"),
            expires_in=session_data.get("expires_in", 3600),
            user=user,
        )

    async def sign_out(self, access_token: str) -> None:
        """Sign out the current user.

        Args:
            access_token: Current access token

        Raises:
            NotImplementedError: Supabase Auth not configured
        """
        client = get_supabase_client()
        await client.auth.sign_out()

    async def get_user(self, access_token: str) -> AuthUser | None:
        """Get user from access token.

        Args:
            access_token: JWT access token

        Returns:
            User info if token is valid, None otherwise

        Raises:
            NotImplementedError: Supabase Auth not configured
        """
        client = get_supabase_client()

        user_data = await client.auth.get_user(access_token)
        if not user_data:
            return None

        return AuthUser(
            id=user_data.get("id", ""),
            email=user_data.get("email", ""),
            role=user_data.get("role", "user"),
            metadata=user_data.get("user_metadata", {}),
        )

    async def refresh_token(self, refresh_token: str) -> AuthSession:
        """Refresh the access token.

        Args:
            refresh_token: Refresh token

        Returns:
            New authentication session

        Raises:
            NotImplementedError: Supabase Auth not configured
        """
        # TODO: Implement when Supabase is configured
        raise NotImplementedError("Token refresh not yet implemented")

    async def verify_token(self, access_token: str) -> bool:
        """Verify if a token is valid.

        Args:
            access_token: JWT access token

        Returns:
            True if token is valid, False otherwise
        """
        try:
            user = await self.get_user(access_token)
            return user is not None
        except (NotImplementedError, Exception):
            return False
