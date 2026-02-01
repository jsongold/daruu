"""Document repository interface (Port).

This defines the contract for document persistence operations.
Implementations can be in-memory, database, or any other storage.
"""

from typing import Protocol

from app.models import Document, DocumentMeta, DocumentType


class DocumentRepository(Protocol):
    """Repository interface for Document entities.

    This protocol defines the contract that any document storage
    implementation must satisfy. Following Clean Architecture,
    the application layer depends on this interface, not on
    concrete implementations.

    Example:
        class PostgresDocumentRepository:
            def create(self, ...) -> Document: ...
            def get(self, document_id: str) -> Document | None: ...
            # etc.

        # Inject into service
        service = DocumentService(repo=PostgresDocumentRepository())
    """

    def create(
        self,
        document_type: DocumentType,
        meta: DocumentMeta,
        ref: str,
    ) -> Document:
        """Create a new document record.

        Args:
            document_type: Type of document (source/target).
            meta: Document metadata (page count, size, etc.).
            ref: Reference/path to the stored file.

        Returns:
            Created Document entity with generated ID.
        """
        ...

    def get(self, document_id: str) -> Document | None:
        """Get a document by ID.

        Args:
            document_id: Unique document identifier.

        Returns:
            Document if found, None otherwise.
        """
        ...

    def list_all(self) -> list[Document]:
        """List all documents.

        Returns:
            List of all documents.
        """
        ...

    def delete(self, document_id: str) -> bool:
        """Delete a document by ID.

        Args:
            document_id: Unique document identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...
