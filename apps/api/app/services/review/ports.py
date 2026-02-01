"""Port interfaces for the Review service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.

The Review service is deterministic (no LLM) and performs:
- PDF rendering of filled documents
- Visual diff/overlay generation
- Issue detection (overflow, overlap, missing values)
"""

from typing import Protocol

from app.models.common import BBox
from app.services.review.domain.models import (
    DiffResult,
    OverflowCheckResult,
    OverlapCheckResult,
    RenderResult,
)


class PdfRendererPort(Protocol):
    """Port for rendering PDF pages to images.

    Implementations should handle:
    - PDF rendering at configurable DPI
    - Page-specific rendering
    - Image format conversion (PNG preferred)

    Example implementations:
    - PyMuPdfRenderer: Uses PyMuPDF (fitz) library
    - PdfiumRenderer: Uses pdfium for rendering
    """

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 150,
    ) -> RenderResult:
        """Render a single page from a PDF to an image.

        Args:
            pdf_path: Path to the PDF file
            page_number: 1-indexed page number
            dpi: Resolution for rendering (default 150)

        Returns:
            RenderResult containing image bytes and metadata

        Raises:
            ValueError: If page number is out of range
            IOError: If PDF cannot be read
        """
        ...

    def render_all_pages(
        self,
        pdf_path: str,
        dpi: int = 150,
    ) -> tuple[RenderResult, ...]:
        """Render all pages from a PDF to images.

        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for rendering (default 150)

        Returns:
            Tuple of RenderResult for each page

        Raises:
            IOError: If PDF cannot be read
        """
        ...


class DiffGeneratorPort(Protocol):
    """Port for generating visual diffs between images.

    Implementations should handle:
    - Pixel-by-pixel comparison
    - Difference highlighting
    - Overlay generation

    Example implementations:
    - OpenCVDiffGenerator: Uses OpenCV for image processing
    - PillowDiffGenerator: Uses Pillow for basic diff
    """

    def generate_diff(
        self,
        original_image: bytes,
        filled_image: bytes,
        highlight_color: tuple[int, int, int] = (255, 0, 0),
    ) -> DiffResult:
        """Generate a visual diff between two images.

        Args:
            original_image: PNG bytes of the original (unfilled) page
            filled_image: PNG bytes of the filled page
            highlight_color: RGB color for highlighting differences

        Returns:
            DiffResult with diff image and change regions

        Raises:
            ValueError: If images have incompatible dimensions
        """
        ...

    def generate_overlay(
        self,
        base_image: bytes,
        overlay_image: bytes,
        opacity: float = 0.5,
    ) -> bytes:
        """Generate an overlay of two images.

        Args:
            base_image: PNG bytes of the base image
            overlay_image: PNG bytes of the overlay image
            opacity: Opacity of the overlay (0.0 to 1.0)

        Returns:
            PNG bytes of the combined overlay image

        Raises:
            ValueError: If images have incompatible dimensions
        """
        ...


class IssueDetectorPort(Protocol):
    """Port for detecting issues in filled documents.

    Implementations should handle:
    - Text overflow detection
    - Field overlap detection
    - Missing value detection
    - Visual quality checks

    Example implementations:
    - RuleBasedIssueDetector: Uses geometric rules
    - OpenCVIssueDetector: Uses computer vision
    """

    def detect_overflow(
        self,
        text: str,
        bbox: BBox,
        font_size: float,
        image: bytes,
    ) -> OverflowCheckResult:
        """Detect if text overflows its bounding box.

        Args:
            text: The text content to check
            bbox: The bounding box constraint
            font_size: Font size in points
            image: Rendered page image for visual verification

        Returns:
            OverflowCheckResult with detection details
        """
        ...

    def detect_overlap(
        self,
        bbox1: BBox,
        bbox2: BBox,
        image: bytes,
    ) -> OverlapCheckResult:
        """Detect if two bounding boxes overlap.

        Args:
            bbox1: First bounding box
            bbox2: Second bounding box
            image: Rendered page image for visual verification

        Returns:
            OverlapCheckResult with detection details
        """
        ...


class PreviewStoragePort(Protocol):
    """Port for storing and retrieving preview artifacts.

    Implementations should handle:
    - Storing preview images
    - Storing diff images
    - Generating retrieval URLs

    Example implementations:
    - LocalPreviewStorage: File system storage
    - S3PreviewStorage: AWS S3 storage
    """

    def save_preview(
        self,
        document_id: str,
        page_number: int,
        image_data: bytes,
        artifact_type: str = "preview",
    ) -> str:
        """Store a preview image artifact.

        Args:
            document_id: Document identifier
            page_number: 1-indexed page number
            image_data: PNG image bytes
            artifact_type: Type of artifact ("preview", "diff", "overlay")

        Returns:
            Storage reference/URL for the saved image

        Raises:
            IOError: If storage operation fails
        """
        ...

    def get_url(self, artifact_ref: str) -> str:
        """Get a URL for accessing a stored artifact.

        Args:
            artifact_ref: Storage reference from save_preview

        Returns:
            URL or path for accessing the artifact
        """
        ...

    def delete_artifacts(self, document_id: str) -> int:
        """Delete all preview artifacts for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of artifacts deleted
        """
        ...
