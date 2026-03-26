"""Supabase implementation of FileRepository.

Provides file storage using Supabase Storage.
Implements the FileRepository protocol for document and preview storage.
"""

import logging
from pathlib import Path
from typing import Any

from app.infrastructure.supabase.client import get_supabase_client
from app.infrastructure.supabase.config import get_supabase_config
from app.infrastructure.supabase.resilience import is_retryable_error, with_retry

logger = logging.getLogger(__name__)


def _make_ref(bucket: str, key: str) -> str:
    """Create a supabase:// reference string.

    Uses string concatenation instead of Path to preserve the // in URLs.
    """
    return f"supabase://{bucket}/{key}"


class SupabaseFileRepository:
    """Supabase implementation of FileRepository.

    Uses Supabase Storage to store documents and preview images.
    Files are organized into buckets:
    - documents: Original PDF files
    - previews: Page preview images
    - outputs: Generated filled PDFs
    """

    def __init__(self) -> None:
        """Initialize the repository."""
        self._client = get_supabase_client()
        self._config = get_supabase_config()

    def _get_bucket(self, bucket_name: str | None = None) -> Any:
        """Get a storage bucket client.

        Args:
            bucket_name: Bucket name (defaults to documents bucket).

        Returns:
            Supabase bucket client.
        """
        name = bucket_name or self._config.bucket_documents
        return self._client.storage.from_(name)

    def store(self, file_id: str, content: bytes, filename: str) -> str:
        """Store file content and return the reference with retry on transient errors.

        Args:
            file_id: Unique file identifier.
            content: File content as bytes.
            filename: Original filename.

        Returns:
            Reference string to the stored file.
        """
        try:
            return self._store_with_retry(file_id, content, filename)
        except Exception as e:
            logger.error(f"Failed to store file {file_id}: {e}")
            raise

    @with_retry(max_retries=3, base_delay=1.0)
    def _store_with_retry(self, file_id: str, content: bytes, filename: str) -> str:
        """Internal store with retry logic."""
        bucket = self._get_bucket(self._config.bucket_documents)
        key = f"{file_id}/{filename}"

        # Determine content type
        content_type = "application/pdf"
        if filename.lower().endswith(".png"):
            content_type = "image/png"
        elif filename.lower().endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"

        # Upload to Supabase Storage (upsert to overwrite if exists)
        bucket.upload(
            path=key,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )

        # Return a reference string (not Path to preserve //)
        return _make_ref(self._config.bucket_documents, key)

    def get(self, file_id: str) -> bytes | None:
        """Get file content by ID.

        Args:
            file_id: Unique file identifier.

        Returns:
            File content as bytes if found, None otherwise.
        """
        try:
            bucket = self._get_bucket(self._config.bucket_documents)

            # List files in the file_id directory
            items = bucket.list(file_id)

            if not items:
                return None

            # Get the first file
            first_file = items[0]
            key = f"{file_id}/{first_file.get('name', '')}"

            # Download the file
            content = bucket.download(key)
            return content
        except Exception as e:
            logger.warning(f"Failed to get file {file_id}: {e}")
            return None

    def get_path(self, file_id: str) -> str | None:
        """Get file reference by ID.

        Args:
            file_id: Unique file identifier.

        Returns:
            Reference string if found, None otherwise.
        """
        try:
            bucket = self._get_bucket(self._config.bucket_documents)

            # List files in the file_id directory
            items = bucket.list(file_id)

            if not items:
                return None

            first_file = items[0]
            key = f"{file_id}/{first_file.get('name', '')}"

            return _make_ref(self._config.bucket_documents, key)
        except Exception as e:
            logger.warning(f"Failed to get path for file {file_id}: {e}")
            return None

    def delete(self, file_id: str) -> bool:
        """Delete a file by ID.

        Args:
            file_id: Unique file identifier.

        Returns:
            True if deleted, False if not found.
        """
        try:
            bucket = self._get_bucket(self._config.bucket_documents)

            # List files in the file_id directory
            items = bucket.list(file_id)

            if not items:
                return False

            # Delete all files in the directory
            paths = [f"{file_id}/{item.get('name', '')}" for item in items]
            bucket.remove(paths)

            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False

    def store_preview(self, document_id: str, page: int, content: bytes) -> str:
        """Store a page preview image.

        Args:
            document_id: Document identifier.
            page: Page number (1-indexed).
            content: PNG image content.

        Returns:
            Reference string to the stored preview.
        """
        try:
            bucket = self._get_bucket(self._config.bucket_previews)
            key = f"{document_id}/page_{page}.png"

            bucket.upload(
                path=key,
                file=content,
                file_options={"content-type": "image/png", "upsert": "true"},
            )

            return _make_ref(self._config.bucket_previews, key)
        except Exception as e:
            logger.error(f"Failed to store preview for {document_id} page {page}: {e}")
            raise

    def get_preview_path(self, document_id: str, page: int) -> str | None:
        """Get the reference to a page preview.

        Args:
            document_id: Document identifier.
            page: Page number (1-indexed).

        Returns:
            Reference string if found, None otherwise.
        """
        try:
            key = f"{document_id}/page_{page}.png"
            return _make_ref(self._config.bucket_previews, key)
        except Exception as e:
            logger.warning(f"Failed to get preview path: {e}")
            return None

    def get_content(self, ref: str) -> bytes | None:
        """Get file content by file path reference with retry on transient errors.

        Args:
            ref: File path or reference (as stored in document.ref).

        Returns:
            File content as bytes if found, None otherwise.
        """
        try:
            return self._get_content_with_retry(ref)
        except Exception as e:
            if is_retryable_error(e):
                logger.warning(f"Failed to get content for {ref} after retries: {e}")
            else:
                logger.warning(f"Non-retryable error getting content for {ref}: {e}")
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _get_content_with_retry(self, ref: str) -> bytes | None:
        """Internal get_content with retry logic."""
        # Parse supabase:// or supabase:/ URL (handle legacy single-slash format)
        if ref.startswith("supabase://"):
            path_part = ref[len("supabase://") :]
        elif ref.startswith("supabase:/"):
            # Legacy format with single slash (due to Path normalization bug)
            path_part = ref[len("supabase:/") :]
        else:
            path_part = None

        if path_part:
            parts = path_part.split("/", 1)
            if len(parts) < 2:
                return None

            bucket_name = parts[0]
            key = parts[1]

            bucket = self._get_bucket(bucket_name)
            content = bucket.download(key)
            return content

        # Fallback: treat as local path
        path = Path(ref)
        if path.exists():
            return path.read_bytes()

        return None

    def get_preview_content(self, document_id: str, page: int) -> bytes | None:
        """Get preview image content with retry on transient errors.

        Args:
            document_id: Document identifier.
            page: Page number (1-indexed).

        Returns:
            PNG image content if found, None otherwise.
        """
        try:
            return self._get_preview_content_with_retry(document_id, page)
        except Exception as e:
            if is_retryable_error(e):
                logger.warning(
                    f"Failed to get preview content for {document_id} page {page} after retries: {e}"
                )
            else:
                logger.warning(
                    f"Non-retryable error getting preview content for {document_id} page {page}: {e}"
                )
            return None

    @with_retry(max_retries=3, base_delay=1.0)
    def _get_preview_content_with_retry(self, document_id: str, page: int) -> bytes | None:
        """Internal get_preview_content with retry logic."""
        bucket = self._get_bucket(self._config.bucket_previews)
        key = f"{document_id}/page_{page}.png"

        content = bucket.download(key)
        return content

    def get_signed_url(
        self,
        ref: str,
        expires_in: int = 3600,
    ) -> str | None:
        """Get a signed URL for a file.

        Args:
            ref: File path reference (supabase:// URL).
            expires_in: URL expiration time in seconds.

        Returns:
            Signed URL if successful, None otherwise.
        """
        try:
            if not ref.startswith("supabase://"):
                return None

            path_part = ref[len("supabase://") :]
            parts = path_part.split("/", 1)
            if len(parts) < 2:
                return None

            bucket_name = parts[0]
            key = parts[1]

            bucket = self._get_bucket(bucket_name)
            result = bucket.create_signed_url(key, expires_in)
            return result.get("signedURL")
        except Exception as e:
            logger.warning(f"Failed to get signed URL for {ref}: {e}")
            return None

    def get_public_url(self, ref: str) -> str | None:
        """Get a public URL for a file.

        Args:
            ref: File path reference (supabase:// URL).

        Returns:
            Public URL if available, None otherwise.
        """
        try:
            if not ref.startswith("supabase://"):
                return None

            path_part = ref[len("supabase://") :]
            parts = path_part.split("/", 1)
            if len(parts) < 2:
                return None

            bucket_name = parts[0]
            key = parts[1]

            bucket = self._get_bucket(bucket_name)
            return bucket.get_public_url(key)
        except Exception as e:
            logger.warning(f"Failed to get public URL for {ref}: {e}")
            return None

    def list_previews(self, document_id: str) -> list[str]:
        """List all preview images for a document.

        Args:
            document_id: Document identifier.

        Returns:
            List of preview reference strings.
        """
        try:
            bucket = self._get_bucket(self._config.bucket_previews)
            items = bucket.list(document_id)

            refs = []
            for item in items:
                key = f"{document_id}/{item.get('name', '')}"
                refs.append(_make_ref(self._config.bucket_previews, key))

            return refs
        except Exception as e:
            logger.warning(f"Failed to list previews for {document_id}: {e}")
            return []
