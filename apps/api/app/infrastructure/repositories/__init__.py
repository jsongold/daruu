"""Repository implementations (Adapters) for Clean Architecture.

These are concrete implementations of the repository interfaces
defined in `app.repositories`. They can be swapped without
changing business logic.

Current implementations:
- MemoryRepository: In-memory storage (MVP/development)
- SupabaseRepository: Supabase PostgreSQL storage (production)

Usage:
    from app.infrastructure.repositories import (
        get_document_repository,
        get_job_repository,
        get_file_repository,
        get_event_publisher,
    )

    # Automatically selects Supabase if configured, else memory
    doc_repo = get_document_repository()
    job_repo = get_job_repository()

    # Force a specific mode
    doc_repo = get_document_repository(mode="supabase")
    doc_repo = get_document_repository(mode="memory")
"""

from app.infrastructure.repositories.memory_repository import (
    MemoryDocumentRepository,
    MemoryEventPublisher,
    MemoryFileRepository,
    MemoryJobRepository,
)
from app.infrastructure.repositories.memory_conversation_repository import (
    MemoryConversationRepository,
)
from app.infrastructure.repositories.memory_edit_repository import (
    MemoryEditRepository,
)
from app.infrastructure.repositories.memory_message_repository import (
    MemoryMessageRepository,
)
from app.infrastructure.repositories.memory_template_repository import (
    MemoryTemplateRepository,
)
from app.infrastructure.repositories.factory import (
    clear_repository_singletons,
    get_active_mode,
    get_conversation_repository,
    get_data_source_repository,
    get_document_repository,
    get_edit_repository,
    get_event_publisher,
    get_file_repository,
    get_job_repository,
    get_message_repository,
    get_prompt_attempt_repository,
    get_template_repository,
)

__all__ = [
    # Memory implementations (for direct use if needed)
    "MemoryDocumentRepository",
    "MemoryJobRepository",
    "MemoryFileRepository",
    "MemoryEventPublisher",
    "MemoryConversationRepository",
    "MemoryEditRepository",
    "MemoryMessageRepository",
    "MemoryTemplateRepository",
    # Factory functions (preferred way to get repositories)
    "get_conversation_repository",
    "get_data_source_repository",
    "get_document_repository",
    "get_edit_repository",
    "get_event_publisher",
    "get_file_repository",
    "get_job_repository",
    "get_message_repository",
    "get_prompt_attempt_repository",
    "get_template_repository",
    # Utility functions
    "get_active_mode",
    "clear_repository_singletons",
]
