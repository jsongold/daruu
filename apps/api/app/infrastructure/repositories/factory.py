"""Repository factory for selecting implementations.

Provides factory functions that return appropriate repository implementations.
Supabase is the default and required for production.
In-memory mode is only for unit tests.

Usage:
    from app.infrastructure.repositories.factory import (
        get_document_repository,
        get_job_repository,
        get_file_repository,
        get_event_publisher,
    )

    # Get repositories (Supabase by default)
    doc_repo = get_document_repository()
    job_repo = get_job_repository()

    # For unit tests only
    doc_repo = get_document_repository(mode="memory")

    # Or set environment variable for tests:
    # DARU_REPOSITORY_MODE=memory pytest ...
"""

import os
from typing import Literal

from app.infrastructure.observability import get_logger
from app.infrastructure.supabase.config import is_supabase_configured


def _is_test_mode() -> bool:
    """Check if running in test mode (use memory repositories)."""
    return os.environ.get("DARU_REPOSITORY_MODE", "").lower() == "memory"
from app.repositories import (
    ConversationRepository,
    DocumentRepository,
    EventPublisher,
    FileRepository,
    JobRepository,
    MessageRepository,
)

logger = get_logger("repositories")

# Type for repository mode
# "supabase" is default for production
# "memory" is only for unit tests
RepositoryMode = Literal["memory", "supabase"]

# Singleton instances for each mode
_memory_doc_repo: "DocumentRepository | None" = None
_memory_job_repo: "JobRepository | None" = None
_memory_file_repo: "FileRepository | None" = None
_memory_event_pub: "EventPublisher | None" = None

_supabase_doc_repo: "DocumentRepository | None" = None
_supabase_job_repo: "JobRepository | None" = None
_supabase_file_repo: "FileRepository | None" = None

# Conversation repositories (in-memory only for now)
_memory_conv_repo: "ConversationRepository | None" = None
_memory_msg_repo: "MessageRepository | None" = None


def _get_memory_document_repository() -> DocumentRepository:
    """Get in-memory document repository singleton (for tests only)."""
    global _memory_doc_repo
    if _memory_doc_repo is None:
        from app.infrastructure.repositories.memory_repository import (
            MemoryDocumentRepository,
        )
        _memory_doc_repo = MemoryDocumentRepository()
    return _memory_doc_repo


def _get_memory_job_repository() -> JobRepository:
    """Get in-memory job repository singleton (for tests only)."""
    global _memory_job_repo
    if _memory_job_repo is None:
        from app.infrastructure.repositories.memory_repository import (
            MemoryJobRepository,
        )
        _memory_job_repo = MemoryJobRepository()
    return _memory_job_repo


def _get_memory_file_repository() -> FileRepository:
    """Get in-memory file repository singleton (for tests only)."""
    global _memory_file_repo
    if _memory_file_repo is None:
        from app.infrastructure.repositories.memory_repository import (
            MemoryFileRepository,
        )
        _memory_file_repo = MemoryFileRepository()
    return _memory_file_repo


def _get_memory_event_publisher() -> EventPublisher:
    """Get in-memory event publisher singleton."""
    global _memory_event_pub
    if _memory_event_pub is None:
        from app.infrastructure.repositories.memory_repository import (
            MemoryEventPublisher,
        )
        _memory_event_pub = MemoryEventPublisher()
    return _memory_event_pub


def _ensure_supabase_configured() -> None:
    """Ensure Supabase is configured, raise if not."""
    if not is_supabase_configured():
        raise RuntimeError(
            "Supabase is not configured. "
            "Set DARU_SUPABASE_URL and DARU_SUPABASE_ANON_KEY environment variables. "
            "Use mode='memory' only for unit tests."
        )


def _get_supabase_document_repository() -> DocumentRepository:
    """Get Supabase document repository singleton."""
    global _supabase_doc_repo
    _ensure_supabase_configured()
    if _supabase_doc_repo is None:
        from app.repositories.supabase import SupabaseDocumentRepository
        _supabase_doc_repo = SupabaseDocumentRepository()
        logger.debug("Initialized Supabase document repository")
    return _supabase_doc_repo


def _get_supabase_job_repository() -> JobRepository:
    """Get Supabase job repository singleton."""
    global _supabase_job_repo
    _ensure_supabase_configured()
    if _supabase_job_repo is None:
        from app.repositories.supabase import SupabaseJobRepository
        _supabase_job_repo = SupabaseJobRepository()
        logger.debug("Initialized Supabase job repository")
    return _supabase_job_repo


def _get_supabase_file_repository() -> FileRepository:
    """Get Supabase file repository singleton."""
    global _supabase_file_repo
    _ensure_supabase_configured()
    if _supabase_file_repo is None:
        from app.repositories.supabase import SupabaseFileRepository
        _supabase_file_repo = SupabaseFileRepository()
        logger.debug("Initialized Supabase file repository")
    return _supabase_file_repo


def get_document_repository(
    mode: RepositoryMode = "supabase",
) -> DocumentRepository:
    """Get the document repository.

    Args:
        mode: Repository mode:
            - "supabase": Use Supabase (default, required for production)
            - "memory": Use in-memory storage (for unit tests only)

    Returns:
        DocumentRepository implementation.

    Raises:
        RuntimeError: If supabase mode but Supabase is not configured.
    """
    if mode == "memory" or _is_test_mode():
        return _get_memory_document_repository()

    return _get_supabase_document_repository()


def get_job_repository(
    mode: RepositoryMode = "supabase",
) -> JobRepository:
    """Get the job repository.

    Args:
        mode: Repository mode:
            - "supabase": Use Supabase (default, required for production)
            - "memory": Use in-memory storage (for unit tests only)

    Returns:
        JobRepository implementation.

    Raises:
        RuntimeError: If supabase mode but Supabase is not configured.
    """
    if mode == "memory" or _is_test_mode():
        return _get_memory_job_repository()

    return _get_supabase_job_repository()


def get_file_repository(
    mode: RepositoryMode = "supabase",
) -> FileRepository:
    """Get the file repository.

    Args:
        mode: Repository mode:
            - "supabase": Use Supabase (default, required for production)
            - "memory": Use in-memory storage (for unit tests only)

    Returns:
        FileRepository implementation.

    Raises:
        RuntimeError: If supabase mode but Supabase is not configured.
    """
    if mode == "memory" or _is_test_mode():
        return _get_memory_file_repository()

    return _get_supabase_file_repository()


def get_event_publisher() -> EventPublisher:
    """Get the event publisher.

    Currently only in-memory implementation is available.
    Future: Redis pub/sub or Supabase Realtime.

    Returns:
        EventPublisher implementation.
    """
    return _get_memory_event_publisher()


def get_conversation_repository(
    mode: RepositoryMode = "memory",
) -> ConversationRepository:
    """Get the conversation repository.

    Currently only in-memory implementation is available.
    Future: Supabase implementation.

    Args:
        mode: Repository mode (only "memory" is supported for now).

    Returns:
        ConversationRepository implementation.
    """
    global _memory_conv_repo
    if _memory_conv_repo is None:
        from app.infrastructure.repositories.memory_conversation_repository import (
            MemoryConversationRepository,
        )
        _memory_conv_repo = MemoryConversationRepository()
        logger.debug("Initialized memory conversation repository")
    return _memory_conv_repo


def get_message_repository(
    mode: RepositoryMode = "memory",
) -> MessageRepository:
    """Get the message repository.

    Currently only in-memory implementation is available.
    Future: Supabase implementation.

    Args:
        mode: Repository mode (only "memory" is supported for now).

    Returns:
        MessageRepository implementation.
    """
    global _memory_msg_repo
    if _memory_msg_repo is None:
        from app.infrastructure.repositories.memory_message_repository import (
            MemoryMessageRepository,
        )
        _memory_msg_repo = MemoryMessageRepository()
        logger.debug("Initialized memory message repository")
    return _memory_msg_repo


def clear_repository_singletons() -> None:
    """Clear all repository singleton instances.

    Useful for testing when configuration changes.
    """
    global _memory_doc_repo, _memory_job_repo, _memory_file_repo, _memory_event_pub
    global _supabase_doc_repo, _supabase_job_repo, _supabase_file_repo
    global _memory_conv_repo, _memory_msg_repo

    _memory_doc_repo = None
    _memory_job_repo = None
    _memory_file_repo = None
    _memory_event_pub = None
    _supabase_doc_repo = None
    _supabase_job_repo = None
    _supabase_file_repo = None
    _memory_conv_repo = None
    _memory_msg_repo = None


def get_active_mode() -> str:
    """Get the currently active repository mode.

    Returns:
        "supabase" if Supabase is configured, raises error otherwise.

    Raises:
        RuntimeError: If Supabase is not configured.
    """
    _ensure_supabase_configured()
    return "supabase"
