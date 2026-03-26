"""Supabase implementation of DataSourceRepository.

Provides data source persistence using Supabase PostgreSQL database.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.resilience import with_retry
from app.models.data_source import DataSource, DataSourceType
from app.repositories import DataSourceRepository

logger = logging.getLogger(__name__)


class SupabaseDataSourceRepository:
    """Supabase implementation of DataSourceRepository.

    Uses Supabase PostgreSQL to store data source metadata.
    """

    TABLE_NAME = "data_sources"

    def __init__(self) -> None:
        """Initialize the repository."""
        self._client = get_supabase_client()

    def _to_data_source(self, row: dict[str, Any]) -> DataSource:
        """Convert a database row to a DataSource model.

        Args:
            row: Database row as dictionary.

        Returns:
            DataSource model instance.
        """
        created_at_str = row.get("created_at")
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = created_at_str or datetime.now(timezone.utc)

        updated_at_str = row.get("updated_at")
        if isinstance(updated_at_str, str):
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        else:
            updated_at = updated_at_str or datetime.now(timezone.utc)

        return DataSource(
            id=str(row["id"]),
            conversation_id=row["conversation_id"],
            type=DataSourceType(row["type"]),
            name=row["name"],
            document_id=row.get("document_id"),
            text_content=row.get("text_content"),
            content_preview=row.get("content_preview"),
            extracted_data=row.get("extracted_data"),
            file_size_bytes=row.get("file_size_bytes"),
            mime_type=row.get("mime_type"),
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_row(
        self,
        conversation_id: str,
        source_type: DataSourceType,
        name: str,
        document_id: str | None = None,
        text_content: str | None = None,
        content_preview: str | None = None,
        file_size_bytes: int | None = None,
        mime_type: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert data source data to a database row.

        Args:
            conversation_id: ID of the parent conversation.
            source_type: Type of data source.
            name: Display name.
            document_id: Reference to documents table.
            text_content: Direct text content.
            content_preview: Preview text.
            file_size_bytes: File size.
            mime_type: MIME type.
            source_id: Optional source ID.

        Returns:
            Dictionary suitable for database insertion.
        """
        row: dict[str, Any] = {
            "conversation_id": conversation_id,
            "type": source_type.value,
            "name": name,
        }

        if source_id:
            row["id"] = source_id
        if document_id:
            row["document_id"] = document_id
        if text_content is not None:
            row["text_content"] = text_content
        if content_preview is not None:
            row["content_preview"] = content_preview
        if file_size_bytes is not None:
            row["file_size_bytes"] = file_size_bytes
        if mime_type is not None:
            row["mime_type"] = mime_type

        return row

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
        """Create a new data source record with retry on transient errors.

        Args:
            conversation_id: ID of the parent conversation.
            source_type: Type of data source.
            name: Display name.
            document_id: Reference to documents table.
            text_content: Direct text content.
            content_preview: First 500 chars for preview.
            file_size_bytes: File size.
            mime_type: MIME type.

        Returns:
            Created DataSource entity with generated ID.
        """
        source_id = str(uuid4())
        row = self._to_row(
            conversation_id=conversation_id,
            source_type=source_type,
            name=name,
            document_id=document_id,
            text_content=text_content,
            content_preview=content_preview,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            source_id=source_id,
        )

        try:
            return self._create_with_retry(
                row,
                source_id,
                conversation_id,
                source_type,
                name,
                document_id,
                text_content,
                content_preview,
                file_size_bytes,
                mime_type,
            )
        except Exception as e:
            logger.error(f"Failed to create data source: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _create_with_retry(
        self,
        row: dict[str, Any],
        source_id: str,
        conversation_id: str,
        source_type: DataSourceType,
        name: str,
        document_id: str | None,
        text_content: str | None,
        content_preview: str | None,
        file_size_bytes: int | None,
        mime_type: str | None,
    ) -> DataSource:
        """Internal create with retry logic."""
        result = self._client.table(self.TABLE_NAME).insert(row).execute()

        if result.data and len(result.data) > 0:
            return self._to_data_source(result.data[0])

        # If insert succeeded but no data returned, construct the data source
        now = datetime.now(timezone.utc)
        return DataSource(
            id=source_id,
            conversation_id=conversation_id,
            type=source_type,
            name=name,
            document_id=document_id,
            text_content=text_content,
            content_preview=content_preview,
            extracted_data=None,
            file_size_bytes=file_size_bytes,
            mime_type=mime_type,
            created_at=now,
            updated_at=now,
        )

    def get(self, data_source_id: str) -> DataSource | None:
        """Get a data source by ID with retry on transient errors.

        Args:
            data_source_id: Unique data source identifier.

        Returns:
            DataSource if found, None otherwise.
        """
        try:
            return self._get_with_retry(data_source_id)
        except Exception as e:
            logger.error(f"Failed to get data source {data_source_id}: {e}")
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _get_with_retry(self, data_source_id: str) -> DataSource | None:
        """Internal get with retry logic."""
        result = self._client.table(self.TABLE_NAME).select("*").eq("id", data_source_id).execute()

        if result.data and len(result.data) > 0:
            return self._to_data_source(result.data[0])
        return None

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
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .select("*")
                .eq("conversation_id", conversation_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return [self._to_data_source(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to list data sources for conversation {conversation_id}: {e}")
            return []

    def delete(self, data_source_id: str) -> bool:
        """Delete a data source by ID.

        Args:
            data_source_id: Unique data source identifier.

        Returns:
            True if deleted, False if not found.
        """
        try:
            # Check if data source exists first
            existing = self.get(data_source_id)
            if existing is None:
                return False

            self._client.table(self.TABLE_NAME).delete().eq("id", data_source_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete data source {data_source_id}: {e}")
            return False

    def delete_by_conversation(self, conversation_id: str) -> int:
        """Delete all data sources for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of data sources deleted.
        """
        try:
            # Get count first
            count = self.count_by_conversation(conversation_id)

            if count > 0:
                self._client.table(self.TABLE_NAME).delete().eq(
                    "conversation_id", conversation_id
                ).execute()

            return count
        except Exception as e:
            logger.error(f"Failed to delete data sources for conversation {conversation_id}: {e}")
            return 0

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
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .update({"extracted_data": extracted_data})
                .eq("id", data_source_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return self._to_data_source(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to update extracted data for {data_source_id}: {e}")
            return None

    def count_by_conversation(self, conversation_id: str) -> int:
        """Count data sources for a conversation.

        Args:
            conversation_id: ID of the conversation.

        Returns:
            Number of data sources.
        """
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .eq("conversation_id", conversation_id)
                .execute()
            )

            return result.count or 0
        except Exception as e:
            logger.error(f"Failed to count data sources for conversation {conversation_id}: {e}")
            return 0


# Verify protocol compliance
_assert_protocol: DataSourceRepository = SupabaseDataSourceRepository()
