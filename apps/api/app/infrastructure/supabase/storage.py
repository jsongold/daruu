"""Supabase Storage adapter.

Provides file storage functionality using Supabase Storage.
Implements the StorageGateway interface from application/ports.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.application.ports.storage_gateway import (
    StorageGateway,
    StorageObject,
    UploadResult,
)
from app.infrastructure.supabase.client import get_supabase_client

# Bucket names following PRD specification
BUCKET_DOCUMENTS = "documents"
BUCKET_PREVIEWS = "previews"
BUCKET_CROPS = "crops"
BUCKET_OUTPUTS = "outputs"
BUCKET_RULEBOOKS = "rulebooks"


@dataclass
class SupabaseStorageAdapter:
    """Supabase Storage implementation of StorageGateway.

    This adapter implements file storage using Supabase Storage.
    Currently a stub implementation - will be completed when Supabase is configured.

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

        Raises:
            NotImplementedError: Supabase Storage not configured
        """
        client = get_supabase_client()
        bucket_client = client.storage.from_(bucket)

        # Upload the file
        await bucket_client.upload(
            path=key,
            file=content,
            file_options={"content-type": content_type},
        )

        # Get the URL (may be public or require signed URL)
        try:
            url = bucket_client.get_public_url(key)
        except Exception:
            url = None

        return UploadResult(
            key=key,
            bucket=bucket,
            url=url,
            size=len(content),
        )

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
            NotImplementedError: Supabase Storage not configured
        """
        client = get_supabase_client()
        bucket_client = client.storage.from_(bucket)

        content = await bucket_client.download(key)
        return content

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

        Raises:
            NotImplementedError: Supabase Storage not configured
        """
        client = get_supabase_client()
        bucket_client = client.storage.from_(bucket)

        result = await bucket_client.create_signed_url(key, expires_in)
        return result.get("signedURL", "")

    async def delete_file(
        self,
        bucket: str,
        key: str,
    ) -> None:
        """Delete a file from storage.

        Args:
            bucket: Storage bucket name
            key: Storage key/path within bucket

        Raises:
            NotImplementedError: Supabase Storage not configured
        """
        client = get_supabase_client()
        bucket_client = client.storage.from_(bucket)

        await bucket_client.remove([key])

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

        Raises:
            NotImplementedError: Supabase Storage not configured
        """
        client = get_supabase_client()
        bucket_client = client.storage.from_(bucket)

        items = await bucket_client.list(prefix)

        objects = []
        for item in items[:limit]:
            obj = StorageObject(
                key=item.get("name", ""),
                bucket=bucket,
                size=item.get("metadata", {}).get("size", 0),
                content_type=item.get("metadata", {}).get("mimetype", "application/octet-stream"),
                created_at=item.get("created_at", datetime.now(timezone.utc).isoformat()),
                url=None,
            )
            objects.append(obj)

        return objects

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
        try:
            await self.download_file(bucket, key)
            return True
        except (FileNotFoundError, NotImplementedError):
            return False

    # Convenience methods following PRD bucket organization

    async def upload_document(
        self,
        document_id: str,
        content: bytes,
        filename: str,
    ) -> UploadResult:
        """Upload a PDF document.

        Args:
            document_id: Unique document ID
            content: PDF content as bytes
            filename: Original filename

        Returns:
            Upload result
        """
        key = f"{document_id}/{filename}"
        return await self.upload_file(
            bucket=BUCKET_DOCUMENTS,
            key=key,
            content=content,
            content_type="application/pdf",
        )

    async def upload_preview(
        self,
        document_id: str,
        page: int,
        content: bytes,
    ) -> UploadResult:
        """Upload a page preview image.

        Args:
            document_id: Document ID
            page: Page number (1-indexed)
            content: PNG image content

        Returns:
            Upload result
        """
        key = f"{document_id}/page_{page}.png"
        return await self.upload_file(
            bucket=BUCKET_PREVIEWS,
            key=key,
            content=content,
            content_type="image/png",
        )

    async def upload_crop(
        self,
        job_id: str,
        field_id: str,
        content: bytes,
    ) -> UploadResult:
        """Upload an OCR crop image.

        Args:
            job_id: Job ID
            field_id: Field ID this crop is for
            content: PNG image content

        Returns:
            Upload result
        """
        key = f"{job_id}/{field_id}_crop.png"
        return await self.upload_file(
            bucket=BUCKET_CROPS,
            key=key,
            content=content,
            content_type="image/png",
        )

    async def upload_output(
        self,
        job_id: str,
        content: bytes,
    ) -> UploadResult:
        """Upload a generated output PDF.

        Args:
            job_id: Job ID
            content: PDF content as bytes

        Returns:
            Upload result
        """
        key = f"{job_id}/output.pdf"
        return await self.upload_file(
            bucket=BUCKET_OUTPUTS,
            key=key,
            content=content,
            content_type="application/pdf",
        )


# Ensure the adapter implements the protocol
def _verify_protocol() -> None:
    """Verify that SupabaseStorageAdapter implements StorageGateway."""
    adapter: StorageGateway = SupabaseStorageAdapter()  # noqa: F841
