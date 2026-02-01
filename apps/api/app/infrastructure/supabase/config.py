"""Supabase configuration.

Provides Supabase-specific configuration settings that integrate with
the main application settings. Includes validation and defaults.
"""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from app.config import get_settings


class SupabaseConfig(BaseModel):
    """Supabase configuration settings.

    Contains all settings required to connect to and use Supabase
    services including database, auth, and storage.
    """

    # Connection settings
    url: str | None = Field(
        default=None,
        description="Supabase project URL (e.g., https://xxxxx.supabase.co)",
    )
    secret_key: str | None = Field(
        default=None,
        description="Supabase secret key for backend operations (bypasses RLS)",
    )

    # Storage settings
    storage_bucket: str = Field(
        default="daru-pdf",
        description="Default storage bucket name",
    )
    bucket_documents: str = Field(
        default="documents",
        description="Bucket for original PDF files",
    )
    bucket_previews: str = Field(
        default="previews",
        description="Bucket for page preview images",
    )
    bucket_crops: str = Field(
        default="crops",
        description="Bucket for OCR crop images",
    )
    bucket_outputs: str = Field(
        default="outputs",
        description="Bucket for filled/output PDFs",
    )

    # Database settings
    schema_name: str = Field(
        default="public",
        description="Database schema to use",
    )

    # Signed URL settings
    signed_url_expires_in: int = Field(
        default=3600,
        ge=60,
        le=604800,
        description="Signed URL expiration in seconds (default 1 hour, max 7 days)",
    )

    model_config = {"frozen": True}

    @property
    def is_configured(self) -> bool:
        """Check if Supabase is properly configured.

        Returns:
            True if URL and secret key are set.
        """
        return bool(self.url) and bool(self.secret_key)


# Repository mode type alias
# "supabase" is default for production
# "memory" is only for unit tests
RepositoryMode = Literal["memory", "supabase"]

REPOSITORY_MODE_MEMORY: RepositoryMode = "memory"
REPOSITORY_MODE_SUPABASE: RepositoryMode = "supabase"


@lru_cache
def get_supabase_config() -> SupabaseConfig:
    """Get Supabase configuration from application settings.

    Loads settings from environment variables via the main Settings class.

    Returns:
        SupabaseConfig instance with values from environment.
    """
    settings = get_settings()

    return SupabaseConfig(
        url=settings.supabase_url,
        secret_key=settings.supabase_secret_key,
        bucket_documents=settings.storage_bucket_documents,
        bucket_previews=settings.storage_bucket_previews,
        bucket_crops=settings.storage_bucket_crops,
        bucket_outputs=settings.storage_bucket_outputs,
    )


def is_supabase_configured() -> bool:
    """Check if Supabase is properly configured.

    Convenience function for checking configuration status.

    Returns:
        True if Supabase URL and key are configured.
    """
    config = get_supabase_config()
    return config.is_configured


def clear_supabase_config_cache() -> None:
    """Clear the cached Supabase configuration.

    Useful for testing when settings need to be reloaded.
    """
    get_supabase_config.cache_clear()
