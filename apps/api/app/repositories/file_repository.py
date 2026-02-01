"""File repository interface (Port).

This defines the contract for file storage operations.
Implementations can be local filesystem, S3, GCS, or any other storage.
"""

from pathlib import Path
from typing import Protocol


class FileRepository(Protocol):
    """Repository interface for file storage.

    This protocol defines the contract that any file storage
    implementation must satisfy. It handles raw file bytes
    and paths, separate from document metadata.

    Example:
        class S3FileRepository:
            def store(self, ...) -> str: ...
            def get(self, file_id: str) -> bytes | None: ...
            # etc.

        # Inject into service
        service = DocumentService(file_repo=S3FileRepository())
    """

    def store(self, file_id: str, content: bytes, filename: str) -> str:
        """Store file content and return the path/reference.

        Args:
            file_id: Unique file identifier.
            content: File content as bytes.
            filename: Original filename.

        Returns:
            Reference string where file was stored (e.g., supabase://bucket/path).
        """
        ...

    def get(self, file_id: str) -> bytes | None:
        """Get file content by ID.

        Args:
            file_id: Unique file identifier.

        Returns:
            File content as bytes if found, None otherwise.
        """
        ...

    def get_path(self, file_id: str) -> str | None:
        """Get file path/reference by ID.

        Args:
            file_id: Unique file identifier.

        Returns:
            Reference string if found, None otherwise.
        """
        ...

    def delete(self, file_id: str) -> bool:
        """Delete a file by ID.

        Args:
            file_id: Unique file identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    def store_preview(self, document_id: str, page: int, content: bytes) -> str:
        """Store a page preview image.

        Args:
            document_id: Document identifier.
            page: Page number (1-indexed).
            content: PNG image content.

        Returns:
            Reference string where preview was stored.
        """
        ...

    def get_preview_path(self, document_id: str, page: int) -> str | None:
        """Get the reference to a page preview.

        Args:
            document_id: Document identifier.
            page: Page number (1-indexed).

        Returns:
            Reference string if found, None otherwise.
        """
        ...

    def get_content(self, ref: str) -> bytes | None:
        """Get file content by file path reference.

        Args:
            ref: File path or reference (as stored in document.ref).

        Returns:
            File content as bytes if found, None otherwise.
        """
        ...

    def get_preview_content(self, document_id: str, page: int) -> bytes | None:
        """Get preview image content.

        Args:
            document_id: Document identifier.
            page: Page number (1-indexed).

        Returns:
            PNG image content if found, None otherwise.
        """
        ...
