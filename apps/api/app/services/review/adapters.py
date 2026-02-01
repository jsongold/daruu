"""Adapter implementations for Review service ports.

These are REAL implementations using:
- PyMuPDF (fitz) for PDF rendering
- OpenCV for diff/overlay generation
- Local filesystem for artifact storage
"""

import shutil
from pathlib import Path

import cv2
import fitz
import numpy as np
from numpy.typing import NDArray

from app.models.common import BBox
from app.services.review.domain.models import (
    ChangeRegion,
    DiffResult,
    OverflowCheckResult,
    OverlapCheckResult,
    RenderResult,
)
from app.services.review.domain.rules import (
    check_boxes_overlap,
    check_text_overflow,
)
from app.services.review.ports import (
    DiffGeneratorPort,
    IssueDetectorPort,
    PdfRendererPort,
    PreviewStoragePort,
)


class PdfRenderError(Exception):
    """Exception raised when PDF rendering fails."""

    pass


class ImageProcessingError(Exception):
    """Exception raised when image processing fails."""

    pass


class StorageError(Exception):
    """Exception raised when storage operations fail."""

    pass


class PyMuPdfRenderer:
    """PDF renderer adapter using PyMuPDF (fitz) library.

    Implements PdfRendererPort for rendering PDF pages to images.
    Uses PyMuPDF's pixmap functionality for high-quality rendering.
    """

    def render_page(
        self,
        pdf_path: str,
        page_number: int,
        dpi: int = 150,
    ) -> RenderResult:
        """Render a single page from a PDF.

        Args:
            pdf_path: Path to the PDF file
            page_number: 1-indexed page number
            dpi: Resolution for rendering (default 150)

        Returns:
            RenderResult with image bytes and metadata

        Raises:
            PdfRenderError: If PDF cannot be opened or page is invalid
            ValueError: If page number is out of range
        """
        if page_number < 1:
            raise ValueError("page_number must be >= 1")

        if dpi <= 0:
            raise ValueError("dpi must be > 0")

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PdfRenderError(f"Failed to open PDF: {pdf_path}") from e

        try:
            if page_number > len(doc):
                raise ValueError(
                    f"Page {page_number} out of range. PDF has {len(doc)} pages."
                )

            # Get the page (0-indexed internally)
            page = doc[page_number - 1]

            # Create transformation matrix for DPI scaling
            # PDF default is 72 DPI, scale to requested DPI
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)

            # Render page to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to PNG bytes
            image_data = pix.tobytes("png")

            return RenderResult(
                page_number=page_number,
                image_data=image_data,
                width=pix.width,
                height=pix.height,
                dpi=dpi,
            )
        finally:
            doc.close()

    def render_all_pages(
        self,
        pdf_path: str,
        dpi: int = 150,
    ) -> tuple[RenderResult, ...]:
        """Render all pages from a PDF.

        Args:
            pdf_path: Path to the PDF file
            dpi: Resolution for rendering (default 150)

        Returns:
            Tuple of RenderResult for each page

        Raises:
            PdfRenderError: If PDF cannot be opened
        """
        if dpi <= 0:
            raise ValueError("dpi must be > 0")

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise PdfRenderError(f"Failed to open PDF: {pdf_path}") from e

        try:
            results: list[RenderResult] = []
            scale = dpi / 72.0
            mat = fitz.Matrix(scale, scale)

            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=mat, alpha=False)
                image_data = pix.tobytes("png")

                result = RenderResult(
                    page_number=page_num + 1,
                    image_data=image_data,
                    width=pix.width,
                    height=pix.height,
                    dpi=dpi,
                )
                results.append(result)

            return tuple(results)
        finally:
            doc.close()


# Ensure PyMuPdfRenderer satisfies PdfRendererPort
_renderer_check: PdfRendererPort = PyMuPdfRenderer()


class OpenCVDiffGenerator:
    """Diff generator adapter using OpenCV.

    Implements DiffGeneratorPort for generating visual diffs
    between PDF page images using OpenCV image processing.
    """

    # Threshold for detecting meaningful differences (0-255)
    DEFAULT_DIFF_THRESHOLD = 30

    # Minimum contour area to be considered a significant change
    MIN_CONTOUR_AREA = 100

    # Threshold for significant changes (percentage of image area)
    SIGNIFICANT_CHANGE_THRESHOLD = 0.01  # 1% of image

    def _decode_image(self, image_bytes: bytes) -> NDArray[np.uint8]:
        """Decode PNG bytes to OpenCV image array.

        Args:
            image_bytes: PNG image bytes

        Returns:
            OpenCV image array (BGR format)

        Raises:
            ImageProcessingError: If image cannot be decoded
        """
        np_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if image is None:
            raise ImageProcessingError("Failed to decode image bytes")

        return image

    def _encode_image(self, image: NDArray[np.uint8]) -> bytes:
        """Encode OpenCV image array to PNG bytes.

        Args:
            image: OpenCV image array

        Returns:
            PNG image bytes

        Raises:
            ImageProcessingError: If image cannot be encoded
        """
        success, encoded = cv2.imencode(".png", image)

        if not success:
            raise ImageProcessingError("Failed to encode image to PNG")

        return encoded.tobytes()

    def generate_diff(
        self,
        original_image: bytes,
        filled_image: bytes,
        highlight_color: tuple[int, int, int] = (255, 0, 0),
    ) -> DiffResult:
        """Generate a visual diff between two images.

        Args:
            original_image: PNG bytes of the original page
            filled_image: PNG bytes of the filled page
            highlight_color: RGB color for highlighting differences (default red)

        Returns:
            DiffResult with diff image and change regions

        Raises:
            ImageProcessingError: If images cannot be processed
            ValueError: If images have incompatible dimensions
        """
        # Decode images
        orig = self._decode_image(original_image)
        filled = self._decode_image(filled_image)

        # Verify dimensions match
        if orig.shape != filled.shape:
            raise ValueError(
                f"Image dimensions do not match: "
                f"original {orig.shape} vs filled {filled.shape}"
            )

        # Calculate absolute difference
        diff = cv2.absdiff(orig, filled)

        # Convert to grayscale for threshold
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

        # Apply threshold to find significant differences
        _, thresh = cv2.threshold(
            gray_diff, self.DEFAULT_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY
        )

        # Find contours of changed regions
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Build list of change regions
        change_regions: list[ChangeRegion] = []
        total_image_area = orig.shape[0] * orig.shape[1]
        total_change_area = 0.0

        # Create result image (copy of filled with highlights)
        result = filled.copy()

        # Convert RGB highlight color to BGR for OpenCV
        bgr_highlight = (highlight_color[2], highlight_color[1], highlight_color[0])

        for contour in contours:
            area = cv2.contourArea(contour)

            # Skip tiny contours (noise)
            if area < self.MIN_CONTOUR_AREA:
                continue

            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)

            # Calculate change percentage for this region
            region_area = w * h
            change_percentage = area / region_area if region_area > 0 else 0.0

            change_regions.append(
                ChangeRegion(
                    x=float(x),
                    y=float(y),
                    width=float(w),
                    height=float(h),
                    page=1,  # Page number set by caller
                    change_percentage=min(1.0, change_percentage),
                )
            )

            total_change_area += area

            # Draw contour highlight on result
            cv2.drawContours(result, [contour], -1, bgr_highlight, 2)

            # Draw bounding rectangle
            cv2.rectangle(result, (x, y), (x + w, y + h), bgr_highlight, 1)

        # Calculate total change percentage
        total_change_percentage = total_change_area / total_image_area

        # Determine if changes are significant
        has_significant_changes = total_change_percentage > self.SIGNIFICANT_CHANGE_THRESHOLD

        # Encode result image
        diff_image_bytes = self._encode_image(result)

        return DiffResult(
            diff_image=diff_image_bytes,
            change_regions=tuple(change_regions),
            total_change_percentage=min(1.0, total_change_percentage),
            has_significant_changes=has_significant_changes,
        )

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
            ImageProcessingError: If images cannot be processed
            ValueError: If images have incompatible dimensions or invalid opacity
        """
        if not 0.0 <= opacity <= 1.0:
            raise ValueError("opacity must be between 0.0 and 1.0")

        # Decode images
        base = self._decode_image(base_image)
        overlay = self._decode_image(overlay_image)

        # Verify dimensions match
        if base.shape != overlay.shape:
            raise ValueError(
                f"Image dimensions do not match: "
                f"base {base.shape} vs overlay {overlay.shape}"
            )

        # Blend images using weighted addition
        result = cv2.addWeighted(
            base,
            1.0 - opacity,
            overlay,
            opacity,
            0,
        )

        return self._encode_image(result)


# Ensure OpenCVDiffGenerator satisfies DiffGeneratorPort
_diff_gen_check: DiffGeneratorPort = OpenCVDiffGenerator()


class RuleBasedIssueDetector:
    """Issue detector using geometric rules.

    Implements IssueDetectorPort for detecting overflow and overlap
    using geometric calculations. Visual verification can enhance
    detection accuracy.
    """

    def detect_overflow(
        self,
        text: str,
        bbox: BBox,
        font_size: float,
        image: bytes,
    ) -> OverflowCheckResult:
        """Detect if text overflows its bounding box.

        Uses geometric estimation with optional visual verification.

        Args:
            text: The text content to check
            bbox: The bounding box constraint
            font_size: Font size in points
            image: Rendered page image for visual verification

        Returns:
            OverflowCheckResult with detection details
        """
        # Use geometric rule-based detection
        result = check_text_overflow(
            text=text,
            bbox=bbox,
            font_size=font_size,
        )

        # Future enhancement: Use OpenCV to verify overflow visually
        # by analyzing the rendered image in the bbox region
        _ = image  # Reserved for visual verification

        return result

    def detect_overlap(
        self,
        bbox1: BBox,
        bbox2: BBox,
        image: bytes,
    ) -> OverlapCheckResult:
        """Detect if two bounding boxes overlap.

        Uses geometric calculation with optional visual verification.

        Args:
            bbox1: First bounding box
            bbox2: Second bounding box
            image: Rendered page image for visual verification

        Returns:
            OverlapCheckResult with detection details
        """
        # Use geometric rule-based detection
        result = check_boxes_overlap(
            bbox1=bbox1,
            bbox2=bbox2,
        )

        # Future enhancement: Use OpenCV to verify overlap visually
        # by analyzing the rendered regions in the image
        _ = image  # Reserved for visual verification

        return result


# Ensure RuleBasedIssueDetector satisfies IssueDetectorPort
_detector_check: IssueDetectorPort = RuleBasedIssueDetector()


class LocalPreviewStorage:
    """Preview storage adapter for local filesystem.

    Implements PreviewStoragePort for storing preview artifacts
    on the local filesystem with proper directory structure.
    """

    DEFAULT_BASE_PATH = "/tmp/review-previews"

    def __init__(self, base_path: str | None = None) -> None:
        """Initialize with storage base path.

        Args:
            base_path: Base directory for storing preview artifacts.
                      Defaults to /tmp/review-previews
        """
        self._base_path = Path(base_path or self.DEFAULT_BASE_PATH)

    def _get_document_dir(self, document_id: str) -> Path:
        """Get the directory path for a document's artifacts.

        Args:
            document_id: Document identifier

        Returns:
            Path to the document's artifact directory
        """
        # Sanitize document_id to prevent path traversal
        safe_id = "".join(c for c in document_id if c.isalnum() or c in "-_")
        if not safe_id:
            raise ValueError("Invalid document_id")
        return self._base_path / safe_id

    def _get_artifact_filename(
        self,
        page_number: int,
        artifact_type: str,
    ) -> str:
        """Generate filename for an artifact.

        Args:
            page_number: 1-indexed page number
            artifact_type: Type of artifact

        Returns:
            Filename string
        """
        # Sanitize artifact_type
        safe_type = "".join(c for c in artifact_type if c.isalnum() or c in "-_")
        if not safe_type:
            safe_type = "preview"
        return f"{safe_type}_page_{page_number:04d}.png"

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
            File path reference for the saved image

        Raises:
            StorageError: If storage operation fails
            ValueError: If inputs are invalid
        """
        if page_number < 1:
            raise ValueError("page_number must be >= 1")

        if not image_data:
            raise ValueError("image_data cannot be empty")

        try:
            # Create document directory
            doc_dir = self._get_document_dir(document_id)
            doc_dir.mkdir(parents=True, exist_ok=True)

            # Generate filename and full path
            filename = self._get_artifact_filename(page_number, artifact_type)
            filepath = doc_dir / filename

            # Write image data
            filepath.write_bytes(image_data)

            return str(filepath)

        except ValueError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to save preview: {e}") from e

    def get_url(self, artifact_ref: str) -> str:
        """Get file path URL for accessing a stored artifact.

        Args:
            artifact_ref: Storage reference from save_preview

        Returns:
            File URL for the artifact
        """
        # For local storage, return a file:// URL
        # In production with cloud storage, this would return a signed URL
        return f"file://{artifact_ref}"

    def delete_artifacts(self, document_id: str) -> int:
        """Delete all preview artifacts for a document.

        Args:
            document_id: Document identifier

        Returns:
            Number of files deleted

        Raises:
            StorageError: If deletion fails
        """
        try:
            doc_dir = self._get_document_dir(document_id)

            if not doc_dir.exists():
                return 0

            # Count files before deletion
            files = list(doc_dir.glob("*.png"))
            count = len(files)

            # Remove entire directory
            shutil.rmtree(doc_dir)

            return count

        except ValueError:
            return 0
        except Exception as e:
            raise StorageError(f"Failed to delete artifacts: {e}") from e

    def list_artifacts(self, document_id: str) -> list[str]:
        """List all artifacts for a document.

        Args:
            document_id: Document identifier

        Returns:
            List of artifact file paths
        """
        try:
            doc_dir = self._get_document_dir(document_id)

            if not doc_dir.exists():
                return []

            return sorted(str(f) for f in doc_dir.glob("*.png"))

        except ValueError:
            return []

    def exists(self, artifact_ref: str) -> bool:
        """Check if an artifact exists.

        Args:
            artifact_ref: Storage reference from save_preview

        Returns:
            True if artifact exists
        """
        return Path(artifact_ref).exists()


# Ensure LocalPreviewStorage satisfies PreviewStoragePort
_storage_check: PreviewStoragePort = LocalPreviewStorage()
