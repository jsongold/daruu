"""Port interfaces for the Fill service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.
"""

from typing import Protocol

from app.services.fill.domain.models import (
    AcroFormField,
    BoundingBox,
    FontConfig,
    TextBlock,
)


class TextMeasurePort(Protocol):
    """Port for measuring text dimensions.

    Implementations should provide accurate text measurement
    using the actual font metrics that will be used for rendering.

    Example implementations:
    - ReportlabMeasureAdapter: Uses reportlab's stringWidth
    - PyMuPdfMeasureAdapter: Uses PyMuPDF's text_length
    """

    def measure(
        self,
        text: str,
        font_family: str,
        font_size: float,
    ) -> tuple[float, float]:
        """Measure the width and height of text.

        Args:
            text: Text to measure (single line)
            font_family: Font family name
            font_size: Font size in points

        Returns:
            Tuple of (width, height) in points
        """
        ...

    def get_line_height(
        self,
        font_family: str,
        font_size: float,
        line_height_multiplier: float = 1.0,
    ) -> float:
        """Get the line height for a font.

        Args:
            font_family: Font family name
            font_size: Font size in points
            line_height_multiplier: Multiplier for line spacing

        Returns:
            Line height in points
        """
        ...


class PdfReaderPort(Protocol):
    """Port for reading PDF documents and detecting form fields.

    Implementations should handle:
    - Loading PDF documents
    - Detecting AcroForm fields
    - Extracting page dimensions
    - Identifying form field types and locations

    Example implementations:
    - PyMuPdfReaderAdapter: Uses PyMuPDF (fitz)
    - PypdfReaderAdapter: Uses pypdf library
    """

    def load(self, pdf_path: str) -> bool:
        """Load a PDF document.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if loaded successfully, False otherwise
        """
        ...

    def get_page_count(self) -> int:
        """Get the number of pages in the loaded document.

        Returns:
            Number of pages

        Raises:
            RuntimeError: If no document is loaded
        """
        ...

    def get_page_dimensions(self, page_number: int) -> tuple[float, float]:
        """Get the dimensions of a page.

        Args:
            page_number: 1-indexed page number

        Returns:
            Tuple of (width, height) in points

        Raises:
            ValueError: If page number is out of range
        """
        ...

    def has_acroform(self) -> bool:
        """Check if the document has AcroForm fields.

        Returns:
            True if AcroForm is present, False otherwise
        """
        ...

    def get_acroform_fields(self) -> tuple[AcroFormField, ...]:
        """Get all AcroForm fields in the document.

        Returns:
            Tuple of AcroFormField objects

        Raises:
            RuntimeError: If no document is loaded
        """
        ...

    def get_field_bbox(self, field_name: str) -> BoundingBox | None:
        """Get the bounding box for a named form field.

        Args:
            field_name: Name of the form field

        Returns:
            BoundingBox for the field, or None if not found
        """
        ...

    def close(self) -> None:
        """Close the loaded document and release resources."""
        ...


class AcroFormWriterPort(Protocol):
    """Port for writing to AcroForm fields.

    Implementations should handle:
    - Filling AcroForm text fields
    - Setting checkbox states
    - Selecting radio button options
    - Flattening forms (optionally)

    Example implementations:
    - PyMuPdfAcroFormAdapter: Uses PyMuPDF for form filling
    - PypdfAcroFormAdapter: Uses pypdf for form filling
    """

    def load(self, pdf_path: str) -> bool:
        """Load a PDF document for editing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if loaded successfully, False otherwise
        """
        ...

    def set_field_value(
        self,
        field_name: str,
        value: str,
        font_config: FontConfig | None = None,
    ) -> bool:
        """Set the value of an AcroForm field.

        Args:
            field_name: Name of the form field
            value: Value to set
            font_config: Optional font configuration

        Returns:
            True if field was set, False if field not found
        """
        ...

    def set_checkbox(self, field_name: str, checked: bool) -> bool:
        """Set the state of a checkbox field.

        Args:
            field_name: Name of the checkbox field
            checked: Whether the checkbox should be checked

        Returns:
            True if checkbox was set, False if field not found
        """
        ...

    def flatten(self) -> None:
        """Flatten the form fields into the page content.

        This makes fields non-editable and ensures consistent
        rendering across all PDF viewers.
        """
        ...

    def save(self, output_path: str) -> bool:
        """Save the modified PDF to a file.

        Args:
            output_path: Path for the output file

        Returns:
            True if saved successfully, False otherwise
        """
        ...

    def close(self) -> None:
        """Close the document and release resources."""
        ...


class OverlayRendererPort(Protocol):
    """Port for rendering text overlay PDFs.

    Implementations should handle:
    - Creating transparent overlay PDFs
    - Rendering text with proper fonts
    - Handling Japanese/Unicode text
    - Embedding fonts for portability

    Example implementations:
    - ReportlabOverlayAdapter: Uses reportlab for overlay generation
    - PyMuPdfOverlayAdapter: Uses PyMuPDF for overlay generation
    """

    def create_overlay(
        self,
        page_width: float,
        page_height: float,
    ) -> None:
        """Create a new overlay canvas.

        Args:
            page_width: Width of the page in points
            page_height: Height of the page in points
        """
        ...

    def draw_text_block(
        self,
        block: TextBlock,
        font: FontConfig,
    ) -> bool:
        """Draw a text block on the overlay.

        Args:
            block: TextBlock with positioned lines
            font: Font configuration for rendering

        Returns:
            True if drawn successfully, False otherwise
        """
        ...

    def draw_text(
        self,
        text: str,
        x: float,
        y: float,
        font: FontConfig,
    ) -> bool:
        """Draw text at a specific position.

        Args:
            text: Text to draw
            x: X coordinate (from left)
            y: Y coordinate (from bottom)
            font: Font configuration

        Returns:
            True if drawn successfully, False otherwise
        """
        ...

    def draw_rectangle(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        stroke_color: str = "#3b82f6",
        stroke_width: float = 1.0,
        fill_color: str | None = None,
    ) -> bool:
        """Draw a rectangle (border) on the overlay.

        Used for rendering field bounding boxes in the output PDF.

        Args:
            x: X coordinate (from left)
            y: Y coordinate (from bottom in PDF coordinates)
            width: Width of the rectangle
            height: Height of the rectangle
            stroke_color: Border color (hex or named color)
            stroke_width: Border width in points
            fill_color: Optional fill color (None for transparent)

        Returns:
            True if drawn successfully, False otherwise
        """
        ...

    def save_overlay(self, output_path: str) -> bool:
        """Save the overlay to a PDF file.

        Args:
            output_path: Path for the output file

        Returns:
            True if saved successfully, False otherwise
        """
        ...


class PdfMergerPort(Protocol):
    """Port for merging PDFs (overlaying pages).

    Implementations should handle:
    - Overlaying transparent PDFs on base documents
    - Preserving original document content
    - Handling multi-page documents

    Example implementations:
    - PyMuPdfMergerAdapter: Uses PyMuPDF for merging
    - PypdfMergerAdapter: Uses pypdf for merging
    """

    def merge_overlay(
        self,
        base_pdf_path: str,
        overlay_pdf_path: str,
        output_path: str,
        page_number: int,
    ) -> bool:
        """Merge an overlay PDF onto a specific page.

        Args:
            base_pdf_path: Path to the base PDF
            overlay_pdf_path: Path to the overlay PDF
            output_path: Path for the output file
            page_number: 1-indexed page number to overlay

        Returns:
            True if merged successfully, False otherwise
        """
        ...

    def merge_all_overlays(
        self,
        base_pdf_path: str,
        overlays: dict[int, str],
        output_path: str,
    ) -> bool:
        """Merge multiple overlays onto a document.

        Args:
            base_pdf_path: Path to the base PDF
            overlays: Dict mapping page numbers to overlay paths
            output_path: Path for the output file

        Returns:
            True if all merged successfully, False otherwise
        """
        ...


class StoragePort(Protocol):
    """Port for storing and retrieving PDF artifacts.

    Implementations should handle:
    - Storing filled PDFs
    - Storing temporary overlay files
    - Generating retrieval URLs/paths
    - Managing artifact lifecycle

    Example implementations:
    - LocalStorageAdapter: File system storage
    - S3StorageAdapter: AWS S3 storage
    """

    def save_pdf(
        self,
        document_id: str,
        pdf_data: bytes,
        suffix: str = "",
    ) -> str:
        """Store a PDF document.

        Args:
            document_id: Document identifier
            pdf_data: PDF bytes to store
            suffix: Optional suffix for the filename

        Returns:
            Storage reference/path for the saved PDF
        """
        ...

    def save_temp_file(
        self,
        prefix: str,
        data: bytes,
        extension: str = ".pdf",
    ) -> str:
        """Store a temporary file.

        Args:
            prefix: Prefix for the filename
            data: File bytes to store
            extension: File extension

        Returns:
            Path to the temporary file
        """
        ...

    def get_url(self, pdf_ref: str) -> str:
        """Get a URL/path for accessing a stored PDF.

        Args:
            pdf_ref: Storage reference from save_pdf

        Returns:
            URL or path for accessing the PDF
        """
        ...

    def delete(self, ref: str) -> bool:
        """Delete a stored file.

        Args:
            ref: Storage reference to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    def read_file(self, ref: str) -> bytes:
        """Read a file from storage.

        Args:
            ref: Storage reference to read

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        ...
