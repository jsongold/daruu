"""Adapter implementations for Fill service ports.

These adapters provide real PDF manipulation capabilities using:
- PyMuPDF (fitz) for PDF reading, writing, form filling, and merging
- reportlab for overlay generation and text measurement
"""

import io
import os
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from reportlab.lib.colors import Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from app.services.fill.domain.models import (
    AcroFormField,
    BoundingBox,
    FontConfig,
    TextBlock,
)
from app.services.fill.ports import (
    AcroFormWriterPort,
    OverlayRendererPort,
    PdfMergerPort,
    PdfReaderPort,
    StoragePort,
    TextMeasurePort,
)

# Register CJK fonts for Japanese text support
_FONTS_REGISTERED = False


def _register_cjk_fonts() -> None:
    """Register CJK fonts for Japanese text support.

    This function registers the HeiseiMin-W3 and HeiseiKakuGo-W5 fonts
    which provide Japanese character support in reportlab.
    """
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return

    try:
        # Register standard CJK fonts
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
        pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    except Exception:
        # CJK fonts may not be available on all systems
        pass

    _FONTS_REGISTERED = True


def _get_font_name(family: str) -> str:
    """Map font family name to reportlab font name.

    Args:
        family: Font family name (e.g., "Helvetica", "MS Gothic")

    Returns:
        Reportlab-compatible font name
    """
    # Standard PDF fonts
    standard_fonts = {
        "helvetica": "Helvetica",
        "times": "Times-Roman",
        "courier": "Courier",
    }

    # Japanese fonts
    japanese_fonts = {
        "ms gothic": "HeiseiKakuGo-W5",
        "msgothic": "HeiseiKakuGo-W5",
        "ms mincho": "HeiseiMin-W3",
        "msmincho": "HeiseiMin-W3",
        "gothic": "HeiseiKakuGo-W5",
        "mincho": "HeiseiMin-W3",
    }

    family_lower = family.lower().replace("-", " ").replace("_", " ")

    if family_lower in standard_fonts:
        return standard_fonts[family_lower]
    if family_lower in japanese_fonts:
        _register_cjk_fonts()
        return japanese_fonts[family_lower]

    # Default to Helvetica for unknown fonts
    return "Helvetica"


class ReportlabMeasureAdapter:
    """Text measurement adapter using reportlab.

    Implements TextMeasurePort for measuring text dimensions
    using reportlab's font metrics.
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        _register_cjk_fonts()

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
        font_name = _get_font_name(font_family)

        try:
            width = pdfmetrics.stringWidth(text, font_name, font_size)
        except KeyError:
            # Fallback to estimation if font not found
            avg_char_width = font_size * 0.6
            width = len(text) * avg_char_width

        # Height is approximated as font size with typical ascender/descender
        height = font_size * 1.2
        return (width, height)

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
        font_name = _get_font_name(font_family)

        try:
            face = pdfmetrics.getFont(font_name).face
            ascent = face.ascent * font_size / 1000.0
            descent = abs(face.descent) * font_size / 1000.0
            return (ascent + descent) * line_height_multiplier
        except (KeyError, AttributeError):
            # Fallback to estimation
            return font_size * 1.2 * line_height_multiplier


# Ensure adapter satisfies port
_measure_check: TextMeasurePort = ReportlabMeasureAdapter()


class PyMuPdfReaderAdapter:
    """PDF reader adapter using PyMuPDF (fitz).

    Implements PdfReaderPort for loading PDFs and detecting
    AcroForm fields.
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        self._doc: fitz.Document | None = None
        self._path: str | None = None

    def load(self, pdf_path: str) -> bool:
        """Load a PDF document.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if loaded successfully, False otherwise
        """
        if not os.path.exists(pdf_path):
            return False

        try:
            self._doc = fitz.open(pdf_path)
            self._path = pdf_path
            return True
        except Exception:
            self._doc = None
            self._path = None
            return False

    def get_page_count(self) -> int:
        """Get the number of pages in the loaded document.

        Returns:
            Number of pages

        Raises:
            RuntimeError: If no document is loaded
        """
        if self._doc is None:
            raise RuntimeError("No document loaded")
        return len(self._doc)

    def get_page_dimensions(self, page_number: int) -> tuple[float, float]:
        """Get the dimensions of a page.

        Args:
            page_number: 1-indexed page number

        Returns:
            Tuple of (width, height) in points

        Raises:
            ValueError: If page number is out of range
        """
        if self._doc is None:
            raise RuntimeError("No document loaded")

        page_count = len(self._doc)
        if page_number < 1 or page_number > page_count:
            raise ValueError(f"Page number {page_number} out of range (1-{page_count})")

        page = self._doc[page_number - 1]
        rect = page.rect
        return (rect.width, rect.height)

    def has_acroform(self) -> bool:
        """Check if the document has AcroForm fields.

        Returns:
            True if AcroForm is present, False otherwise
        """
        if self._doc is None:
            return False

        # Check if document has form fields
        if self._doc.is_form_pdf:
            return True

        # Also check for widget annotations on pages
        for page in self._doc:
            widgets = page.widgets()
            if widgets:
                for _ in widgets:
                    return True

        return False

    def get_acroform_fields(self) -> tuple[AcroFormField, ...]:
        """Get all AcroForm fields in the document.

        Returns:
            Tuple of AcroFormField objects
        """
        if self._doc is None:
            return ()

        fields: list[AcroFormField] = []

        for page in self._doc:
            for widget in page.widgets():
                field_name = widget.field_name or ""
                field_type_code = widget.field_type

                # Map PyMuPDF field types to string
                field_type_map = {
                    fitz.PDF_WIDGET_TYPE_UNKNOWN: "unknown",
                    fitz.PDF_WIDGET_TYPE_BUTTON: "button",
                    fitz.PDF_WIDGET_TYPE_CHECKBOX: "checkbox",
                    fitz.PDF_WIDGET_TYPE_RADIOBUTTON: "radio",
                    fitz.PDF_WIDGET_TYPE_TEXT: "text",
                    fitz.PDF_WIDGET_TYPE_LISTBOX: "listbox",
                    fitz.PDF_WIDGET_TYPE_COMBOBOX: "combobox",
                    fitz.PDF_WIDGET_TYPE_SIGNATURE: "signature",
                }
                field_type = field_type_map.get(field_type_code, "unknown")

                value = widget.field_value or ""
                readonly = bool(widget.field_flags & 1)  # ReadOnly flag

                field = AcroFormField(
                    field_name=field_name,
                    field_type=field_type,
                    value=str(value),
                    appearance_stream=True,
                    readonly=readonly,
                )
                fields.append(field)

        return tuple(fields)

    def get_field_bbox(self, field_name: str) -> BoundingBox | None:
        """Get the bounding box for a named form field.

        Args:
            field_name: Name of the form field

        Returns:
            BoundingBox for the field, or None if not found
        """
        if self._doc is None:
            return None

        for page_num, page in enumerate(self._doc):
            for widget in page.widgets():
                if widget.field_name == field_name:
                    rect = widget.rect
                    return BoundingBox(
                        x=rect.x0,
                        y=rect.y0,
                        width=rect.width,
                        height=rect.height,
                        page=page_num + 1,
                    )

        return None

    def close(self) -> None:
        """Close the loaded document and release resources."""
        if self._doc is not None:
            self._doc.close()
        self._doc = None
        self._path = None


# Ensure adapter satisfies port
_reader_check: PdfReaderPort = PyMuPdfReaderAdapter()


class PyMuPdfAcroFormAdapter:
    """AcroForm writer adapter using PyMuPDF.

    Implements AcroFormWriterPort for filling PDF form fields.
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        self._doc: fitz.Document | None = None
        self._path: str | None = None

    def load(self, pdf_path: str) -> bool:
        """Load a PDF document for editing.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            True if loaded successfully, False otherwise
        """
        if not os.path.exists(pdf_path):
            return False

        try:
            self._doc = fitz.open(pdf_path)
            self._path = pdf_path
            return True
        except Exception:
            self._doc = None
            self._path = None
            return False

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
        if self._doc is None:
            return False

        found = False
        for page in self._doc:
            for widget in page.widgets():
                if widget.field_name == field_name:
                    # Set the field value
                    widget.field_value = value

                    # Apply font configuration if provided
                    if font_config is not None:
                        widget.text_fontsize = font_config.size
                        # Set text color (RGB values 0-1)
                        r, g, b = font_config.color
                        widget.text_color = (r, g, b)

                    # Update the widget appearance
                    widget.update()
                    found = True

        return found

    def set_checkbox(self, field_name: str, checked: bool) -> bool:
        """Set the state of a checkbox field.

        Args:
            field_name: Name of the checkbox field
            checked: Whether the checkbox should be checked

        Returns:
            True if checkbox was set, False if field not found
        """
        if self._doc is None:
            return False

        found = False
        for page in self._doc:
            for widget in page.widgets():
                if widget.field_name == field_name:
                    if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                        # Set checkbox state
                        widget.field_value = checked
                        widget.update()
                        found = True

        return found

    def flatten(self) -> None:
        """Flatten the form fields into the page content."""
        if self._doc is None:
            return

        # Iterate through all pages and reset form fields
        for page in self._doc:
            # Get all widget annotations
            annots = page.annots()
            if annots:
                for annot in annots:
                    if annot.type[0] == fitz.PDF_ANNOT_WIDGET:
                        # Create appearance stream for the annotation
                        # This embeds the field value into the page content
                        annot.update()

            # Clean up form fields by redacting their interactive elements
            # This effectively "flattens" the form
            page.clean_contents()

    def save(self, output_path: str) -> bool:
        """Save the modified PDF to a file.

        Args:
            output_path: Path for the output file

        Returns:
            True if saved successfully, False otherwise
        """
        if self._doc is None:
            return False

        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            self._doc.save(output_path, garbage=4, deflate=True)
            return True
        except Exception:
            return False

    def close(self) -> None:
        """Close the document and release resources."""
        if self._doc is not None:
            self._doc.close()
        self._doc = None
        self._path = None


# Ensure adapter satisfies port
_acroform_check: AcroFormWriterPort = PyMuPdfAcroFormAdapter()


class ReportlabOverlayAdapter:
    """Overlay renderer adapter using reportlab.

    Implements OverlayRendererPort for creating transparent
    overlay PDFs with text content.
    """

    def __init__(self) -> None:
        """Initialize the adapter."""
        _register_cjk_fonts()
        self._buffer: io.BytesIO | None = None
        self._canvas: canvas.Canvas | None = None
        self._width: float = 0
        self._height: float = 0

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
        self._width = page_width
        self._height = page_height
        self._buffer = io.BytesIO()
        self._canvas = canvas.Canvas(
            self._buffer,
            pagesize=(page_width, page_height),
        )

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
        if self._canvas is None:
            return False

        font_name = _get_font_name(font.family)

        try:
            self._canvas.setFont(font_name, font.size)
        except KeyError:
            # Fallback to Helvetica
            self._canvas.setFont("Helvetica", font.size)

        # Set text color
        r, g, b = font.color
        self._canvas.setFillColor(Color(r, g, b))

        # Draw each line
        for line in block.lines:
            self._canvas.drawString(line.x, line.y, line.text)

        return True

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
        if self._canvas is None:
            return False

        font_name = _get_font_name(font.family)

        try:
            self._canvas.setFont(font_name, font.size)
        except KeyError:
            # Fallback to Helvetica
            self._canvas.setFont("Helvetica", font.size)

        # Set text color
        r, g, b = font.color
        self._canvas.setFillColor(Color(r, g, b))

        # Draw the text
        self._canvas.drawString(x, y, text)

        return True

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
        if self._canvas is None:
            return False

        try:
            # Parse hex color
            if stroke_color.startswith("#"):
                hex_color = stroke_color[1:]
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
                self._canvas.setStrokeColor(Color(r, g, b))
            else:
                self._canvas.setStrokeColor(stroke_color)

            self._canvas.setLineWidth(stroke_width)

            if fill_color:
                if fill_color.startswith("#"):
                    hex_fill = fill_color[1:]
                    fr = int(hex_fill[0:2], 16) / 255.0
                    fg = int(hex_fill[2:4], 16) / 255.0
                    fb = int(hex_fill[4:6], 16) / 255.0
                    self._canvas.setFillColor(Color(fr, fg, fb, alpha=0.1))
                else:
                    self._canvas.setFillColor(fill_color)
                self._canvas.rect(x, y, width, height, stroke=1, fill=1)
            else:
                self._canvas.rect(x, y, width, height, stroke=1, fill=0)

            return True
        except Exception:
            return False

    def save_overlay(self, output_path: str) -> bool:
        """Save the overlay to a PDF file.

        Args:
            output_path: Path for the output file

        Returns:
            True if saved successfully, False otherwise
        """
        if self._canvas is None or self._buffer is None:
            return False

        try:
            # Finalize the canvas
            self._canvas.save()

            # Write buffer to file
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            pdf_data = self._buffer.getvalue()
            Path(output_path).write_bytes(pdf_data)

            return True
        except Exception:
            return False


# Ensure adapter satisfies port
_overlay_check: OverlayRendererPort = ReportlabOverlayAdapter()


class PyMuPdfMergerAdapter:
    """PDF merger adapter using PyMuPDF.

    Implements PdfMergerPort for overlaying PDFs.
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
        try:
            # Open both documents
            base_doc = fitz.open(base_pdf_path)
            overlay_doc = fitz.open(overlay_pdf_path)

            # Validate page number
            if page_number < 1 or page_number > len(base_doc):
                base_doc.close()
                overlay_doc.close()
                return False

            # Get the target page (0-indexed)
            base_page = base_doc[page_number - 1]

            # Get the overlay page (assuming single page overlay)
            if len(overlay_doc) > 0:
                # Overlay the content using show_pdf_page
                # This renders the overlay page on top of the base page
                base_page.show_pdf_page(
                    base_page.rect,
                    overlay_doc,
                    0,  # First page of overlay
                    overlay=True,
                )

            # Save the result
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            base_doc.save(output_path, garbage=4, deflate=True)

            # Clean up
            overlay_doc.close()
            base_doc.close()

            return True
        except Exception:
            return False

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
        try:
            # Open the base document
            base_doc = fitz.open(base_pdf_path)

            # Process each overlay
            for page_number, overlay_path in overlays.items():
                # Validate page number
                if page_number < 1 or page_number > len(base_doc):
                    continue

                # Skip if overlay file doesn't exist
                if not os.path.exists(overlay_path):
                    continue

                # Open the overlay document
                overlay_doc = fitz.open(overlay_path)

                if len(overlay_doc) > 0:
                    # Get the target page (0-indexed)
                    base_page = base_doc[page_number - 1]

                    # Overlay the content
                    base_page.show_pdf_page(
                        base_page.rect,
                        overlay_doc,
                        0,  # First page of overlay
                        overlay=True,
                    )

                overlay_doc.close()

            # Save the result
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            base_doc.save(output_path, garbage=4, deflate=True)

            # Clean up
            base_doc.close()

            return True
        except Exception:
            return False


# Ensure adapter satisfies port
_merger_check: PdfMergerPort = PyMuPdfMergerAdapter()


class LocalStorageAdapter:
    """Storage adapter for local filesystem.

    Implements StoragePort for storing filled PDFs
    on the local filesystem.
    """

    def __init__(self, base_path: str = "/tmp/fill-artifacts") -> None:
        """Initialize with storage base path.

        Args:
            base_path: Base directory for storing artifacts
        """
        self._base_path = Path(base_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

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
        filename = f"{document_id}{suffix}.pdf"
        filepath = self._base_path / filename
        filepath.write_bytes(pdf_data)
        return str(filepath)

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
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{prefix}_{unique_id}{extension}"
        filepath = self._base_path / "temp" / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        if data:
            filepath.write_bytes(data)
        else:
            filepath.touch()
        return str(filepath)

    def get_url(self, pdf_ref: str) -> str:
        """Get file path for accessing a stored PDF.

        Args:
            pdf_ref: Storage reference from save_pdf

        Returns:
            File path for the PDF
        """
        # For local storage, the ref is the path
        return pdf_ref

    def delete(self, ref: str) -> bool:
        """Delete a stored file.

        Args:
            ref: Storage reference to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            path = Path(ref)
            if path.exists():
                path.unlink()
                return True
            return False
        except Exception:
            return False

    def read_file(self, ref: str) -> bytes:
        """Read a file from storage.

        Args:
            ref: Storage reference to read

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If file does not exist
        """
        path = Path(ref)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {ref}")
        return path.read_bytes()


# Ensure adapter satisfies port
_storage_check: StoragePort = LocalStorageAdapter()
