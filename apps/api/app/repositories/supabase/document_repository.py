"""Supabase implementation of DocumentRepository.

Provides document persistence using Supabase PostgreSQL database.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.resilience import is_retryable_error, with_retry
from app.models import Document, DocumentMeta, DocumentType
from app.repositories import DocumentRepository

logger = logging.getLogger(__name__)


class SupabaseDocumentRepository:
    """Supabase implementation of DocumentRepository.

    Uses Supabase PostgreSQL to store document metadata.
    File content is stored separately in Supabase Storage.
    """

    TABLE_NAME = "documents"

    def __init__(self) -> None:
        """Initialize the repository."""
        self._client = get_supabase_client()

    def _to_document(self, row: dict[str, Any]) -> Document:
        """Convert a database row to a Document model.

        Args:
            row: Database row as dictionary.

        Returns:
            Document model instance.
        """
        meta_dict = row.get("meta", {})
        if isinstance(meta_dict, str):
            import json

            meta_dict = json.loads(meta_dict)

        meta = DocumentMeta(
            page_count=meta_dict.get("page_count", 1),
            file_size=meta_dict.get("file_size", 0),
            mime_type=meta_dict.get("mime_type", "application/pdf"),
            filename=meta_dict.get("filename", "unknown.pdf"),
            has_password=meta_dict.get("has_password", False),
            has_acroform=meta_dict.get("has_acroform", False),
        )

        created_at_str = row.get("created_at")
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = created_at_str or datetime.now(timezone.utc)

        return Document(
            id=str(row["id"]),
            ref=row["ref"],
            document_type=DocumentType(row["document_type"]),
            meta=meta,
            created_at=created_at,
        )

    def _to_row(
        self,
        document_type: DocumentType,
        meta: DocumentMeta,
        ref: str,
        doc_id: str | None = None,
    ) -> dict[str, Any]:
        """Convert document data to a database row.

        Args:
            document_type: Type of document.
            meta: Document metadata.
            ref: Storage reference.
            doc_id: Optional document ID.

        Returns:
            Dictionary suitable for database insertion.
        """
        row: dict[str, Any] = {
            "ref": ref,
            "document_type": document_type.value,
            "meta": {
                "page_count": meta.page_count,
                "file_size": meta.file_size,
                "mime_type": meta.mime_type,
                "filename": meta.filename,
                "has_password": meta.has_password,
                "has_acroform": meta.has_acroform,
            },
        }
        if doc_id:
            row["id"] = doc_id
        return row

    def create(
        self,
        document_type: DocumentType,
        meta: DocumentMeta,
        ref: str,
    ) -> Document:
        """Create a new document record with retry on transient errors.

        Args:
            document_type: Type of document (source/target).
            meta: Document metadata (page count, size, etc.).
            ref: Reference/path to the stored file.

        Returns:
            Created Document entity with generated ID.
        """
        doc_id = str(uuid4())
        row = self._to_row(document_type, meta, ref, doc_id)

        try:
            return self._create_with_retry(row, doc_id, document_type, meta, ref)
        except Exception as e:
            logger.error(f"Failed to create document: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _create_with_retry(
        self,
        row: dict[str, Any],
        doc_id: str,
        document_type: DocumentType,
        meta: DocumentMeta,
        ref: str,
    ) -> Document:
        """Internal create with retry logic."""
        result = self._client.table(self.TABLE_NAME).insert(row).execute()

        if result.data and len(result.data) > 0:
            return self._to_document(result.data[0])

        # If insert succeeded but no data returned, construct the document
        now = datetime.now(timezone.utc)
        return Document(
            id=doc_id,
            ref=ref,
            document_type=document_type,
            meta=meta,
            created_at=now,
        )

    def get(self, document_id: str) -> Document | None:
        """Get a document by ID with retry on transient errors.

        Args:
            document_id: Unique document identifier.

        Returns:
            Document if found, None otherwise.
        """
        try:
            return self._get_with_retry(document_id)
        except Exception as e:
            if is_retryable_error(e):
                logger.error(f"Failed to get document {document_id} after retries: {e}")
            else:
                logger.error(f"Non-retryable error getting document {document_id}: {e}")
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _get_with_retry(self, document_id: str) -> Document | None:
        """Internal get with retry logic."""
        result = self._client.table(self.TABLE_NAME).select("*").eq("id", document_id).execute()

        if result.data and len(result.data) > 0:
            return self._to_document(result.data[0])
        return None

    def list_all(self) -> list[Document]:
        """List all documents.

        Returns:
            List of all documents.
        """
        try:
            result = (
                self._client.table(self.TABLE_NAME)
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )

            return [self._to_document(row) for row in result.data]
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []

    def delete(self, document_id: str) -> bool:
        """Delete a document by ID.

        Args:
            document_id: Unique document identifier.

        Returns:
            True if deleted, False if not found.
        """
        try:
            # Check if document exists first
            existing = self.get(document_id)
            if existing is None:
                return False

            self._client.table(self.TABLE_NAME).delete().eq("id", document_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def update(
        self,
        document_id: str,
        **updates: Any,
    ) -> Document | None:
        """Update a document with new values.

        Args:
            document_id: Unique document identifier.
            **updates: Fields to update (ref, meta).

        Returns:
            Updated Document if found, None otherwise.
        """
        try:
            # Build update data
            update_data: dict[str, Any] = {}

            if "ref" in updates:
                update_data["ref"] = updates["ref"]

            if "meta" in updates:
                meta = updates["meta"]
                if isinstance(meta, DocumentMeta):
                    update_data["meta"] = {
                        "page_count": meta.page_count,
                        "file_size": meta.file_size,
                        "mime_type": meta.mime_type,
                        "filename": meta.filename,
                        "has_password": meta.has_password,
                        "has_acroform": meta.has_acroform,
                    }
                else:
                    update_data["meta"] = meta

            if not update_data:
                return self.get(document_id)

            result = (
                self._client.table(self.TABLE_NAME)
                .update(update_data)
                .eq("id", document_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return self._to_document(result.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to update document {document_id}: {e}")
            return None


# Verify protocol compliance
_assert_protocol: DocumentRepository = SupabaseDocumentRepository()
