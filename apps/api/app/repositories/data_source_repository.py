"""Data source repository interface (Port).

This defines the contract for data source persistence operations.
Implementations can be in-memory, database, or any other storage.
"""

from typing import Any, Protocol

from app.models.data_source import DataSource, DataSourceType


class DataSourceRepository(Protocol):
    """Repository interface for DataSource entities.

    This protocol defines the contract that any data source storage
    implementation must satisfy.
    """

    def create(
        self,
        conversation_id: str,
        source_type: DataSourceType,
        name: str,
        document_id: str | None = None,
        text_content: str | None = None,
        content_preview: str | None = None,
        file_size_bytes: int | None = None,
        mime_type: str | None = None,
    ) -> DataSource:
        """Create a new data source record.

        Args:
            conversation_id: ID of the parent conversation.
            source_type: Type of data source (pdf, image, text, csv).
            name: Display name (usually original filename).
            document_id: Reference to documents table for files.
            text_content: Direct text content for text/csv sources.
            content_preview: First 500 chars for preview.
            file_size_bytes: File size in bytes.
            mime_type: MIME type.

        Returns:
            Created DataSource entity with generated ID.
        """
        ...

    def get(self, data_source_id: str) -> DataSource | None:
        """Get a data source by ID.

        Args:
            data_source_id: Unique data source identifier.

        Returns:
            DataSource if found, None otherwise.
        """
        ...

    def list_by_conversation(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> list[DataSource]:
        """List all data sources for a conversation.

        Args:
            conversation_id: ID of the conversation.
            limit: Maximum number of results.

        Returns:
            List of data sources, ordered by created_at desc.
        """
        ...

    def delete(self, data_source_id: str) -> bool:
        """Delete a data source by ID.

        Args:
            data_source_id: Unique data source identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    def delete_by_conversation(self, conversation_id: str) -> int:
        """Delete all data sources for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of data sources deleted.
        """
        ...

    def update_extracted_data(
        self,
        data_source_id: str,
        extracted_data: dict[str, Any],
    ) -> DataSource | None:
        """Update the extracted data cache for a data source.

        Args:
            data_source_id: Unique data source identifier.
            extracted_data: Extracted field name-value pairs.

        Returns:
            Updated DataSource if found, None otherwise.
        """
        ...

    def count_by_conversation(self, conversation_id: str) -> int:
        """Count data sources for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of data sources.
        """
        ...
