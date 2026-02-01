"""Repository interfaces (Ports) for Clean Architecture.

This module defines the contracts (protocols) for data access.
The application layer depends on these interfaces, not on
concrete implementations. This allows:

1. Easy testing with mock implementations
2. Swapping storage backends without changing business logic
3. Clear separation between domain and infrastructure

Usage:
    from app.repositories import DocumentRepository, JobRepository

    class MyService:
        def __init__(
            self,
            doc_repo: DocumentRepository,
            job_repo: JobRepository,
        ):
            self._doc_repo = doc_repo
            self._job_repo = job_repo

Directory structure:
    repositories/           # Interfaces (this module)
        document_repository.py
        job_repository.py
        file_repository.py
        event_publisher.py

    storage/               # Implementations
        memory/            # In-memory (MVP)
        postgres/          # PostgreSQL (future)
        redis/             # Redis cache (future)
"""

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.edit_repository import EditRepository
from app.repositories.event_publisher import EventPublisher
from app.repositories.file_repository import FileRepository
from app.repositories.job_repository import JobRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.template_repository import TemplateRepository

__all__ = [
    "ConversationRepository",
    "DocumentRepository",
    "EditRepository",
    "EventPublisher",
    "FileRepository",
    "JobRepository",
    "MessageRepository",
    "TemplateRepository",
]
