"""Storage Gateway interface.

Defines the contract for file/document storage operations.
The primary implementation will use Supabase Storage.

Key responsibilities:
- Upload/download PDF documents
- Store preview images
- Store OCR crop images
- Store generated output PDFs
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class StorageObject(BaseModel):
    """Metadata about a stored object."""

    key: str = Field(..., description="Storage key/path")
    bucket: str = Field(..., description="Storage bucket name")
    size: int = Field(..., ge=0, description="Size in bytes")
    content_type: str = Field(..., description="MIME type")
    created_at: str = Field(..., description="ISO-8601 creation timestamp")
    url: str | None = Field(None, description="Public/signed URL if available")

    model_config = {"frozen": True}


class UploadResult(BaseModel):
    """Result of an upload operation."""

    key: str = Field(..., description="Storage key where file was stored")
    bucket: str = Field(..., description="Storage bucket name")
    url: str | None = Field(None, description="Public/signed URL")
    size: int = Field(..., ge=0, description="Size in bytes")

    model_config = {"frozen": True}


@runtime_checkable
class StorageGateway(Protocol):
    """Interface for file storage operations (implemented by Supabase Storage).

    This gateway abstracts storage functionality, allowing different
    storage backends to be used (Supabase, S3, local filesystem, etc.).

    Bucket organization (following PRD):
    - documents: Original PDF files (source/target)
    - previews: Page preview images
    - crops: OCR crop images
    - outputs: Generated filled PDFs
    """

    async def upload_file(
        self,
        bucket: str,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> UploadResult:
        """Upload a file to storage.

        Args:
            bucket: Storage bucket name
            key: Storage key/path within bucket
            content: File content as bytes
            content_type: MIME type of the content

        Returns:
            Upload result with key and optional URL
        """
        ...

    async def download_file(
        self,
        bucket: str,
        key: str,
    ) -> bytes:
        """Download a file from storage.

        Args:
            bucket: Storage bucket name
            key: Storage key/path within bucket

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If the file does not exist
        """
        ...

    async def get_file_url(
        self,
        bucket: str,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Get a signed URL for a file.

        Args:
            bucket: Storage bucket name
            key: Storage key/path within bucket
            expires_in: URL expiration time in seconds

        Returns:
            Signed URL for accessing the file
        """
        ...

    async def delete_file(
        self,
        bucket: str,
        key: str,
    ) -> None:
        """Delete a file from storage.

        Args:
            bucket: Storage bucket name
            key: Storage key/path within bucket
        """
        ...

    async def list_files(
        self,
        bucket: str,
        prefix: str = "",
        limit: int = 100,
    ) -> list[StorageObject]:
        """List files in a bucket.

        Args:
            bucket: Storage bucket name
            prefix: Key prefix to filter by
            limit: Maximum number of results

        Returns:
            List of storage objects
        """
        ...

    async def file_exists(
        self,
        bucket: str,
        key: str,
    ) -> bool:
        """Check if a file exists in storage.

        Args:
            bucket: Storage bucket name
            key: Storage key/path within bucket

        Returns:
            True if file exists, False otherwise
        """
        ...

    async def upload_document(
        self,
        document_id: str,
        content: bytes,
        filename: str,
    ) -> UploadResult:
        """Upload a PDF document (convenience method).

        Args:
            document_id: Unique document ID
            content: PDF content as bytes
            filename: Original filename

        Returns:
            Upload result
        """
        ...

    async def upload_preview(
        self,
        document_id: str,
        page: int,
        content: bytes,
    ) -> UploadResult:
        """Upload a page preview image (convenience method).

        Args:
            document_id: Document ID
            page: Page number (1-indexed)
            content: PNG image content

        Returns:
            Upload result
        """
        ...

    async def upload_crop(
        self,
        job_id: str,
        field_id: str,
        content: bytes,
    ) -> UploadResult:
        """Upload an OCR crop image (convenience method).

        Args:
            job_id: Job ID
            field_id: Field ID this crop is for
            content: PNG image content

        Returns:
            Upload result
        """
        ...

    async def upload_output(
        self,
        job_id: str,
        content: bytes,
    ) -> UploadResult:
        """Upload a generated output PDF (convenience method).

        Args:
            job_id: Job ID
            content: PDF content as bytes

        Returns:
            Upload result
        """
        ...
