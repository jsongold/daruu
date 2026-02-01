"""Adapter implementations for Ingest service ports.

Provides concrete implementations of the PDF reading and storage ports
using PyMuPDF (fitz) for PDF operations and local filesystem for storage.
"""

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.models.ingest import DocumentMeta, PageMeta
from app.services.ingest.ports import PdfReaderPort, StoragePort

# Try to import PyMuPDF (fitz)
# If not available, we'll use stub implementations
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


class PyMuPdfAdapter:
    """PDF reader adapter using PyMuPDF (fitz) library.

    Implements PdfReaderPort for PDF and image file validation, metadata extraction,
    and page rendering using the PyMuPDF library.

    Supports PDF files and image files (PNG, JPEG, TIFF, WebP).
    Image files are automatically converted to PDF for processing.
    Also supports supabase:// URLs by downloading content to a temp file.

    If PyMuPDF is not installed, methods will raise NotImplementedError.
    """

    @contextmanager
    def _resolve_path(self, pdf_path: str) -> Generator[str, None, None]:
        """Resolve a path that may be a supabase:// URL or local path.

        For supabase:// URLs, downloads content to a temp file.
        For local paths, yields the path as-is.

        Args:
            pdf_path: Local path or supabase:// URL

        Yields:
            Local file path to use
        """
        if pdf_path.startswith("supabase://") or pdf_path.startswith("supabase:/"):
            # Download from Supabase to temp file
            from app.repositories.supabase.file_repository import SupabaseFileRepository

            file_repo = SupabaseFileRepository()
            content = file_repo.get_content(pdf_path)

            if content is None:
                raise FileNotFoundError(f"File not found in storage: {pdf_path}")

            # Determine extension from path
            ext = Path(pdf_path).suffix or ".pdf"

            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            try:
                yield tmp_path
            finally:
                # Clean up temp file
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass
        else:
            # Local path - yield as-is
            yield pdf_path

    def validate(self, pdf_path: str) -> tuple[bool, str | None]:
        """Validate that the PDF or image file is readable.

        Attempts to open the file and checks for:
        - File existence
        - Valid PDF or image format
        - Password protection (PDF only)
        - Corruption

        Supports both local paths and supabase:// URLs.

        Args:
            pdf_path: Path to the PDF or image file (local or supabase://)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not PYMUPDF_AVAILABLE:
            raise NotImplementedError(
                "PyMuPDF (fitz) is not installed. "
                "Install with: pip install PyMuPDF"
            )

        try:
            with self._resolve_path(pdf_path) as local_path:
                # Check file exists
                path = Path(local_path)
                if not path.exists():
                    return (False, f"File not found: {pdf_path}")

                if not path.is_file():
                    return (False, f"Not a file: {pdf_path}")

                # Try to open the file (PyMuPDF can open PDFs and images)
                try:
                    doc = fitz.open(local_path)
                except Exception as e:
                    return (False, f"Cannot open file: {str(e)}")

                # Check if encrypted/password-protected (PDF only)
                try:
                    if doc.is_encrypted:
                        doc.close()
                        return (False, "PDF is password protected")
                except Exception:
                    pass

                # Check if document has pages
                try:
                    page_count = doc.page_count
                    if page_count < 1:
                        doc.close()
                        return (False, "Document has no pages")
                except Exception as e:
                    doc.close()
                    return (False, f"Cannot read document: {str(e)}")

                doc.close()
                return (True, None)
        except FileNotFoundError as e:
            return (False, str(e))

    def get_meta(self, pdf_path: str) -> DocumentMeta:
        """Extract metadata from a PDF or image document.

        Opens the file (PDF or image) and extracts:
        - Total page count
        - Per-page dimensions (width, height in points)
        - Per-page rotation

        Image files are treated as single-page documents.
        PyMuPDF automatically handles image files.
        Supports both local paths and supabase:// URLs.

        Args:
            pdf_path: Path to the PDF or image file (local or supabase://)

        Returns:
            DocumentMeta with page count and per-page metadata

        Raises:
            ValueError: If PDF cannot be read or is invalid
        """
        if not PYMUPDF_AVAILABLE:
            raise NotImplementedError(
                "PyMuPDF (fitz) is not installed. "
                "Install with: pip install PyMuPDF"
            )

        with self._resolve_path(pdf_path) as local_path:
            try:
                doc = fitz.open(local_path)
            except Exception as e:
                raise ValueError(f"Cannot open PDF: {str(e)}") from e

            try:
                pages_meta: list[PageMeta] = []

                for page_num in range(doc.page_count):
                    page = doc[page_num]
                    rect = page.rect

                    page_meta = PageMeta(
                        page_number=page_num + 1,  # 1-indexed
                        width=rect.width,
                        height=rect.height,
                        rotation=page.rotation,
                    )
                    pages_meta.append(page_meta)

                return DocumentMeta(
                    page_count=doc.page_count,
                    pages=tuple(pages_meta),
                )
            finally:
                doc.close()

    def get_page_meta(self, pdf_path: str, page_number: int) -> PageMeta:
        """Extract metadata for a specific page.

        Supports both local paths and supabase:// URLs.

        Args:
            pdf_path: Path to the PDF file (local or supabase://)
            page_number: 1-indexed page number

        Returns:
            PageMeta for the specified page

        Raises:
            ValueError: If page number is out of range
        """
        if not PYMUPDF_AVAILABLE:
            raise NotImplementedError(
                "PyMuPDF (fitz) is not installed. "
                "Install with: pip install PyMuPDF"
            )

        with self._resolve_path(pdf_path) as local_path:
            try:
                doc = fitz.open(local_path)
            except Exception as e:
                raise ValueError(f"Cannot open PDF: {str(e)}") from e

            try:
                # Convert to 0-indexed
                page_index = page_number - 1

                if page_index < 0 or page_index >= doc.page_count:
                    raise ValueError(
                        f"Page {page_number} out of range. "
                        f"Document has {doc.page_count} pages."
                    )

                page = doc[page_index]
                rect = page.rect

                return PageMeta(
                    page_number=page_number,
                    width=rect.width,
                    height=rect.height,
                    rotation=page.rotation,
                )
            finally:
                doc.close()

    def _is_image_file(self, file_path: str) -> bool:
        """Check if a file is an image using Pillow.

        Args:
            file_path: Path to the file

        Returns:
            True if file is a recognized image format
        """
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                img.verify()  # Verify it's a valid image
            return True
        except Exception:
            return False

    def _convert_image_to_png(self, file_path: str) -> bytes:
        """Convert any image format to PNG using Pillow.

        Args:
            file_path: Path to the image file

        Returns:
            PNG image bytes
        """
        import io
        from PIL import Image

        with Image.open(file_path) as img:
            # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Save to PNG bytes
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 150,
    ) -> bytes:
        """Render a page to PNG image bytes.

        Uses PyMuPDF's get_pixmap() to render the page at the
        specified DPI resolution. Works with both PDF and image files.
        Supports both local paths and supabase:// URLs.

        For image files (PNG, JPEG, etc.), converts to PNG using Pillow
        to ensure consistent output format.

        Args:
            pdf_path: Path to the PDF or image file (local or supabase://)
            page_number: 1-indexed page number
            dpi: Resolution for rendering (default 150)

        Returns:
            PNG image bytes

        Raises:
            ValueError: If page number is out of range or rendering fails
        """
        if not PYMUPDF_AVAILABLE:
            raise NotImplementedError(
                "PyMuPDF (fitz) is not installed. "
                "Install with: pip install PyMuPDF"
            )

        with self._resolve_path(pdf_path) as local_path:
            # If the source is already an image file, convert to PNG using Pillow
            # This handles all image formats properly (JPEG, PNG, TIFF, WebP, etc.)
            if self._is_image_file(local_path) and page_number == 1:
                try:
                    return self._convert_image_to_png(local_path)
                except Exception:
                    # Fall through to PyMuPDF if Pillow fails
                    pass

            try:
                doc = fitz.open(local_path)
            except Exception as e:
                raise ValueError(f"Cannot open PDF: {str(e)}") from e

            try:
                # Convert to 0-indexed
                page_index = page_number - 1

                if page_index < 0 or page_index >= doc.page_count:
                    raise ValueError(
                        f"Page {page_number} out of range. "
                        f"Document has {doc.page_count} pages."
                    )

                page = doc[page_index]

                # Calculate zoom factor from DPI
                # PyMuPDF default is 72 DPI
                zoom = dpi / 72.0
                matrix = fitz.Matrix(zoom, zoom)

                # Render page to pixmap
                pixmap = page.get_pixmap(matrix=matrix, alpha=False)

                # Convert to PNG bytes
                png_bytes = pixmap.tobytes("png")

                return png_bytes
            finally:
                doc.close()


# Ensure PyMuPdfAdapter satisfies PdfReaderPort
_pdf_reader_check: PdfReaderPort = PyMuPdfAdapter()


class LocalStorageAdapter:
    """Storage adapter for local filesystem.

    Implements StoragePort for storing rendered page images
    on the local filesystem.

    Directory structure:
    {base_path}/{document_id}/page_{page_number}.png
    """

    def __init__(self, base_path: str = "/tmp/ingest-artifacts") -> None:
        """Initialize with storage base path.

        Args:
            base_path: Base directory for storing artifacts
        """
        self._base_path = Path(base_path)

    def save_image(
        self,
        document_id: str,
        page_number: int,
        image_data: bytes,
        content_type: str = "image/png",
    ) -> str:
        """Store a rendered page image.

        Creates the directory structure if it doesn't exist
        and writes the image data to a file.

        Args:
            document_id: Document identifier
            page_number: 1-indexed page number
            image_data: Image bytes to store
            content_type: MIME type of the image

        Returns:
            File path reference for the saved image

        Raises:
            IOError: If storage operation fails
        """
        # Determine file extension from content type
        extension = self._get_extension(content_type)

        # Create directory for document
        doc_dir = self._base_path / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Create file path
        filename = f"page_{page_number}{extension}"
        file_path = doc_dir / filename

        # Write image data
        try:
            file_path.write_bytes(image_data)
        except Exception as e:
            raise IOError(f"Failed to save image: {str(e)}") from e

        return str(file_path)

    def get_url(self, image_ref: str) -> str:
        """Get file path for accessing a stored image.

        For local storage, the URL is just the file path.

        Args:
            image_ref: Storage reference from save_image

        Returns:
            File path for the image
        """
        return image_ref

    def delete_artifacts(self, document_id: str) -> int:
        """Delete all artifacts for a document.

        Removes the document directory and all its contents.

        Args:
            document_id: Document identifier

        Returns:
            Number of files deleted
        """
        doc_dir = self._base_path / document_id

        if not doc_dir.exists():
            return 0

        deleted_count = 0
        try:
            # Delete all files in directory
            for file_path in doc_dir.iterdir():
                if file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1

            # Remove the directory itself
            doc_dir.rmdir()
        except Exception:
            # Best effort deletion
            pass

        return deleted_count

    def _get_extension(self, content_type: str) -> str:
        """Get file extension from content type.

        Args:
            content_type: MIME type

        Returns:
            File extension including the dot
        """
        extensions = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
        }
        return extensions.get(content_type, ".png")


# Ensure LocalStorageAdapter satisfies StoragePort
_storage_check: StoragePort = LocalStorageAdapter()
