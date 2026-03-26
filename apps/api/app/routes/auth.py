"""Authentication routes (stub implementation for MVP)."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """Login request body."""

    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")


class LoginResponse(BaseModel):
    """Login response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_at: datetime = Field(..., description="Token expiration time")


class UserInfo(BaseModel):
    """Current user information."""

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str | None = Field(None, description="Email address")
    roles: list[str] = Field(default_factory=list, description="User roles")


# Simple in-memory session store for MVP
_sessions: dict[str, dict[str, Any]] = {}


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest) -> LoginResponse:
    """Login and get access token.

    Note: This is a stub implementation for MVP.
    Production would validate against a real auth system.
    """
    # Stub: Accept any credentials for MVP
    token = str(uuid4())
    expires = datetime(2099, 12, 31)  # Far future for MVP

    _sessions[token] = {
        "user_id": str(uuid4()),
        "username": request.username,
        "created_at": datetime.now(timezone.utc),
    }

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_at=expires,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """Logout and invalidate token.

    Note: This is a stub implementation for MVP.
    In production, would invalidate the token from the request header.
    """
    # Stub: No-op for MVP (would extract token from header and invalidate)
    pass


@router.get("/me", response_model=UserInfo)
async def get_current_user() -> UserInfo:
    """Get current user information.

    Note: This is a stub implementation for MVP.
    Production would validate token and return actual user data.
    """
    # Stub: Return mock user for MVP
    return UserInfo(
        id=str(uuid4()),
        username="demo_user",
        email="demo@example.com",
        roles=["user"],
    )
