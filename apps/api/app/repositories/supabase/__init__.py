"""Supabase repository implementations.

This package provides Supabase-backed implementations of the repository
interfaces defined in app.repositories. These implementations persist
data to Supabase PostgreSQL database.

Usage:
    from app.repositories.supabase import (
        SupabaseDocumentRepository,
        SupabaseJobRepository,
        SupabaseFileRepository,
    )

    # Create repositories
    doc_repo = SupabaseDocumentRepository()
    job_repo = SupabaseJobRepository()
    file_repo = SupabaseFileRepository()
"""

from app.repositories.supabase.document_repository import SupabaseDocumentRepository
from app.repositories.supabase.job_repository import SupabaseJobRepository
from app.repositories.supabase.file_repository import SupabaseFileRepository

__all__ = [
    "SupabaseDocumentRepository",
    "SupabaseJobRepository",
    "SupabaseFileRepository",
]
