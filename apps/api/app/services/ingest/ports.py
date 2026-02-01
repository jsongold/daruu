"""Port interfaces for the Ingest service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.
"""

from typing import Protocol

from app.models.ingest import DocumentMeta, PageMeta


class PdfReaderPort(Protocol):
    """Port for reading and processing PDF documents.

    Implementations should handle:
    - PDF validation (format, password, corruption)
    - Metadata extraction (page count, dimensions, rotation)
    - Page rendering to images

    Example implementations:
    - PyMuPdfAdapter: Uses PyMuPDF (fitz) library
    - PdfiumAdapter: Uses pdfium for rendering
    """

    def validate(self, pdf_path: str) -> tuple[bool, str | None]:
        """Validate that the PDF is readable and processable.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if valid
            - (False, "error description") if invalid
        """
        ...

    def get_meta(self, pdf_path: str) -> DocumentMeta:
        """Extract metadata from a PDF document.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            DocumentMeta containing page count and per-page metadata

        Raises:
            ValueError: If PDF cannot be read or is invalid
        """
        ...

    def get_page_meta(self, pdf_path: str, page_number: int) -> PageMeta:
        """Extract metadata for a specific page.

        Args:
            pdf_path: Path to the PDF file
            page_number: 1-indexed page number

        Returns:
            PageMeta for the specified page

        Raises:
            ValueError: If page number is out of range
        """
        ...

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 150,
    ) -> bytes:
        """Render a page to PNG image bytes.

        Args:
            pdf_path: Path to the PDF file
            page_number: 1-indexed page number
            dpi: Resolution for rendering (default 150)

        Returns:
            PNG image bytes

        Raises:
            ValueError: If page number is out of range or rendering fails
        """
        ...


class StoragePort(Protocol):
    """Port for storing and retrieving artifacts.

    Implementations should handle:
    - Storing rendered page images
    - Generating retrieval URLs/paths
    - Managing artifact lifecycle

    Example implementations:
    - LocalStorageAdapter: File system storage
    - S3StorageAdapter: AWS S3 storage
    - GcsStorageAdapter: Google Cloud Storage
    """

    def save_image(
        self,
        document_id: str,
        page_number: int,
        image_data: bytes,
        content_type: str = "image/png",
    ) -> str:
        """Store a rendered page image.

        Args:
            document_id: Document identifier
            page_number: 1-indexed page number
            image_data: Image bytes to store
            content_type: MIME type of the image

        Returns:
            Storage reference/path for the saved image

        Raises:
            IOError: If storage operation fails
        """
        ...

    def get_url(self, image_ref: str) -> str:
        """Get a URL/path for accessing a stored image.

        Args:
            image_ref: Storage reference from save_image

        Returns:
            URL or path for accessing the image
        """
        ...

    def delete_artifacts(self, document_id: str) -> int:
        """Delete all artifacts for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of artifacts deleted
        """
        ...
