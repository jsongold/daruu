"""Supabase client setup for the Rule Service.

Simplified version — only table() and rpc() are needed.
"""

from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_supabase_client():
    """Get the Supabase client instance.

    Returns a real Supabase client if configured, otherwise None.
    """
    settings = get_settings()

    supabase_url = settings.supabase_url
    supabase_key = settings.supabase_secret_key

    if not supabase_url or not supabase_key:
        return None

    try:
        from supabase import create_client

        return create_client(supabase_url, supabase_key)
    except ImportError:
        return None
