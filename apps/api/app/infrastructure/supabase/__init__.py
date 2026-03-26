"""Supabase infrastructure adapters.

This package provides adapters for Supabase services:
- Client: Supabase client setup and connection
- Config: Supabase configuration and settings
- Auth: Supabase Auth integration
- Storage: Supabase Storage implementation

Usage:
    from app.infrastructure.supabase import (
        get_supabase_client,
        get_supabase_config,
        is_supabase_configured,
    )

    if is_supabase_configured():
        client = get_supabase_client()
        # Use client for database operations
"""

from app.infrastructure.supabase.auth import SupabaseAuthAdapter
from app.infrastructure.supabase.client import SupabaseClient, get_supabase_client
from app.infrastructure.supabase.config import (
    REPOSITORY_MODE_MEMORY,
    REPOSITORY_MODE_SUPABASE,
    RepositoryMode,
    SupabaseConfig,
    get_supabase_config,
    is_supabase_configured,
)
from app.infrastructure.supabase.storage import SupabaseStorageAdapter

__all__ = [
    # Client
    "get_supabase_client",
    "SupabaseClient",
    # Config
    "get_supabase_config",
    "is_supabase_configured",
    "SupabaseConfig",
    "RepositoryMode",
    "REPOSITORY_MODE_MEMORY",
    "REPOSITORY_MODE_SUPABASE",
    # Adapters
    "SupabaseAuthAdapter",
    "SupabaseStorageAdapter",
]
