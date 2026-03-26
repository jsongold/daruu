"""Adapter implementations for Extract service ports.

These adapters implement the port interfaces using actual libraries:
- PdfPlumberTextAdapter: Native PDF text extraction with pdfplumber
- PaddleOcrAdapter: OCR with PaddleOCR (recommended for Japanese)
- TesseractAdapter: OCR with pytesseract (fallback)

All adapters follow immutable patterns and comprehensive error handling.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException

from app.models.common import BBox
from app.services.extract.domain.models import (
    NativeTextLine,
    NativeTextResult,
    OcrResult,
)
from app.services.extract.ports import NativeTextExtractorPort, OcrServicePort

logger = logging.getLogger(__name__)

# Try to import PyMuPDF for validation (optional)
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


# Thread pool for blocking I/O operations
_executor = ThreadPoolExecutor(max_workers=4)


class PdfPlumberTextAdapter:
    """Native PDF text extractor using pdfplumber.

    Implements NativeTextExtractorPort for extracting text
    directly from PDF vector/text layers.

    Features:
    - Text extraction with position information
    - Support for region-based extraction
    - Text layer detection
    - Async wrapper around blocking pdfplumber calls
    """

    def __init__(self, executor: ThreadPoolExecutor | None = None) -> None:
        """Initialize the adapter.

        Args:
            executor: Optional custom thread pool executor for blocking I/O
        """
        self._executor = executor or _executor

    def _is_pdf_file(self, document_ref: str) -> bool:
        """Check if a file is a PDF by examining its header.

        This is important because PyMuPDF can open image files,
        but pdfplumber only works with actual PDF files.

        Args:
            document_ref: Path to the file

        Returns:
            True if the file has a PDF signature, False otherwise
        """
        pdf_path = Path(document_ref)
        if not pdf_path.exists() or not pdf_path.is_file():
            return False

        try:
            with open(document_ref, "rb") as f:
                header = f.read(4)
                return header == b"%PDF"
        except Exception:
            return False

    def _validate_pdf(self, document_ref: str) -> tuple[bool, str | None]:
        """Validate that the PDF file is readable and not corrupted.

        Uses PyMuPDF if available for robust validation, otherwise
        performs basic checks.

        Args:
            document_ref: Path to the PDF file

        Returns:
            Tuple of (is_valid, error_message)
        """
        pdf_path = Path(document_ref)
        if not pdf_path.exists():
            return (False, f"PDF file not found: {document_ref}")

        if not pdf_path.is_file():
            return (False, f"Not a file: {document_ref}")

        # Check file size
        if pdf_path.stat().st_size == 0:
            return (False, "PDF file is empty")

        # IMPORTANT: Check if this is actually a PDF file
        # PyMuPDF can open image files, but pdfplumber cannot
        if not self._is_pdf_file(document_ref):
            return (False, "File is not a PDF (image or other file type)")

        # Try PyMuPDF validation if available (more robust)
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(document_ref)
                try:
                    # Check if encrypted/password-protected
                    if doc.is_encrypted:
                        doc.close()
                        return (False, "PDF is password protected")
                    # Check if document has pages
                    page_count = doc.page_count
                    if page_count < 1:
                        doc.close()
                        return (False, "Document has no pages")
                finally:
                    doc.close()
                return (True, None)
            except Exception as e:
                return (False, f"Cannot open PDF file: {str(e)}")

        return (True, None)

    async def extract_text(
        self,
        document_ref: str,
        page: int,
        region: BBox | None = None,
    ) -> NativeTextResult:
        """Extract native text from a PDF page.

        Args:
            document_ref: Path to the PDF file
            page: Page number (1-indexed)
            region: Optional bounding box to limit extraction

        Returns:
            NativeTextResult with extracted lines and positions.
            For non-PDF files (images), returns empty result with has_text_layer=False.

        Raises:
            ValueError: If document not found or page out of range
            RuntimeError: If extraction fails
        """
        # Validate inputs
        pdf_path = Path(document_ref)
        if not pdf_path.exists():
            raise ValueError(f"PDF file not found: {document_ref}")
        if page < 1:
            raise ValueError(f"Page number must be >= 1, got {page}")

        # Check if this is actually a PDF file
        # Image files (PNG, JPEG) don't have native text layers - they need OCR
        if not self._is_pdf_file(document_ref):
            logger.info(
                f"File is not a PDF (likely an image): {document_ref}. "
                "Returning empty result - use OCR for text extraction."
            )
            return NativeTextResult(
                page=page,
                lines=(),
                region_bbox=region,
                has_text_layer=False,
            )

        # Validate PDF before attempting extraction
        is_valid, error_msg = self._validate_pdf(document_ref)
        if not is_valid:
            logger.warning(f"Invalid PDF: {error_msg}")
            return NativeTextResult(
                page=page,
                lines=(),
                region_bbox=region,
                has_text_layer=False,
            )

        # Run blocking pdfplumber operation in thread pool
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor,
                self._extract_text_sync,
                document_ref,
                page,
                region,
            )
            return result
        except ValueError:
            raise
        except (PdfminerException, pdfplumber.utils.exceptions.PdfminerException) as e:
            error_str = str(e)
            if "No /Root object" in error_str or "No /Root" in error_str:
                logger.error(
                    f"PDF appears to be corrupted or invalid (missing Root object): {document_ref}",
                    exc_info=True,
                )
                raise ValueError(
                    f"PDF file is corrupted or invalid (missing Root object). "
                    f"The file may not be a valid PDF or may be incomplete. "
                    f"File: {document_ref}"
                ) from e
            logger.error(f"PDF parsing error: {e}", exc_info=True)
            raise RuntimeError(
                f"Failed to parse PDF file. The file may be corrupted or in an unsupported format: {e}"
            ) from e
        except Exception as e:
            logger.error(f"PDF text extraction failed: {e}", exc_info=True)
            raise RuntimeError(f"Failed to extract text from PDF: {e}") from e

    def _extract_text_sync(
        self,
        document_ref: str,
        page: int,
        region: BBox | None,
    ) -> NativeTextResult:
        """Synchronous text extraction implementation.

        Args:
            document_ref: Path to the PDF file
            page: Page number (1-indexed)
            region: Optional bounding box to limit extraction

        Returns:
            NativeTextResult with extracted lines
        """
        with pdfplumber.open(document_ref) as pdf:
            # Validate page range
            if page > len(pdf.pages):
                raise ValueError(f"Page {page} out of range (document has {len(pdf.pages)} pages)")

            pdf_page = pdf.pages[page - 1]  # pdfplumber uses 0-indexed pages

            # Apply region filter if specified
            extraction_page = pdf_page
            if region is not None:
                # pdfplumber uses (x0, top, x1, bottom) format
                try:
                    extraction_page = pdf_page.within_bbox(
                        (
                            region.x,
                            region.y,
                            region.x + region.width,
                            region.y + region.height,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Region extraction failed, using full page: {e}")
                    extraction_page = pdf_page

            # Extract words with position information
            words = extraction_page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=True,
                extra_attrs=["fontname", "size"],
            )

            # Group words into lines based on y-position
            lines = self._group_words_into_lines(words, page)

            return NativeTextResult(
                page=page,
                lines=tuple(lines),
                region_bbox=region,
                has_text_layer=len(lines) > 0,
            )

    def _group_words_into_lines(
        self,
        words: list[dict],
        page: int,
        y_tolerance: float = 5.0,
    ) -> list[NativeTextLine]:
        """Group words into text lines based on vertical position.

        Args:
            words: List of word dictionaries from pdfplumber
            page: Page number for bbox creation
            y_tolerance: Maximum vertical distance to consider same line

        Returns:
            List of NativeTextLine objects
        """
        if not words:
            return []

        # Sort words by vertical position (top), then horizontal (x0)
        sorted_words = sorted(words, key=lambda w: (w.get("top", 0), w.get("x0", 0)))

        lines: list[NativeTextLine] = []
        current_line_words: list[dict] = []
        current_top: float | None = None

        for word in sorted_words:
            word_top = word.get("top", 0)

            # Check if this word belongs to a new line
            if current_top is None or abs(word_top - current_top) > y_tolerance:
                # Finalize current line if it has words
                if current_line_words:
                    line = self._create_line_from_words(current_line_words, page)
                    lines.append(line)

                # Start new line
                current_line_words = [word]
                current_top = word_top
            else:
                # Add to current line
                current_line_words.append(word)

        # Don't forget the last line
        if current_line_words:
            line = self._create_line_from_words(current_line_words, page)
            lines.append(line)

        return lines

    def _create_line_from_words(
        self,
        words: list[dict],
        page: int,
    ) -> NativeTextLine:
        """Create a NativeTextLine from a list of word dictionaries.

        Args:
            words: List of word dictionaries (must not be empty)
            page: Page number for bbox

        Returns:
            NativeTextLine with combined text and bounding box
        """
        # Sort words by x position to ensure correct reading order
        sorted_words = sorted(words, key=lambda w: w.get("x0", 0))

        # Combine text with spaces
        text = " ".join(w.get("text", "") for w in sorted_words)

        # Calculate bounding box that encompasses all words
        x0 = min(w.get("x0", 0) for w in sorted_words)
        y0 = min(w.get("top", 0) for w in sorted_words)
        x1 = max(w.get("x1", 0) for w in sorted_words)
        y1 = max(w.get("bottom", 0) for w in sorted_words)

        bbox = BBox(
            x=x0,
            y=y0,
            width=x1 - x0,
            height=y1 - y0,
            page=page,
        )

        # Extract font information from the first word (most representative)
        first_word = sorted_words[0]
        font_name = first_word.get("fontname")
        font_size = first_word.get("size")

        return NativeTextLine(
            text=text,
            bbox=bbox,
            font_name=font_name,
            font_size=float(font_size) if font_size else None,
        )

    async def has_text_layer(self, document_ref: str) -> bool:
        """Check if document has a native text layer.

        Args:
            document_ref: Path to the PDF file

        Returns:
            True if document has extractable text layer.
            Returns False for non-PDF files (images) since they don't have text layers.
        """
        # Validate path exists
        pdf_path = Path(document_ref)
        if not pdf_path.exists():
            logger.warning(f"PDF file not found for text layer check: {document_ref}")
            return False

        # Non-PDF files (images) don't have native text layers
        if not self._is_pdf_file(document_ref):
            logger.info(f"File is not a PDF: {document_ref}. No native text layer available.")
            return False

        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                self._executor,
                self._has_text_layer_sync,
                document_ref,
            )
        except Exception as e:
            logger.error(f"Text layer check failed: {e}", exc_info=True)
            return False

    def _has_text_layer_sync(self, document_ref: str) -> bool:
        """Synchronous text layer detection.

        Checks multiple pages to improve accuracy since some pages
        may be scanned images while others have text.

        Args:
            document_ref: Path to the PDF file

        Returns:
            True if any page has extractable text
        """
        try:
            with pdfplumber.open(document_ref) as pdf:
                # Check first few pages (up to 3) for text content
                pages_to_check = min(3, len(pdf.pages))

                for i in range(pages_to_check):
                    page = pdf.pages[i]
                    text = page.extract_text() or ""
                    # Consider it has text layer if we find substantial text
                    if len(text.strip()) > 10:
                        return True

                return False
        except (PdfminerException, pdfplumber.utils.exceptions.PdfminerException) as e:
            # If PDF is corrupted, we can't check for text layer
            logger.warning(f"Cannot check text layer due to PDF error: {e}")
            return False
        except Exception as e:
            logger.warning(f"Text layer check failed: {e}")
            return False


# Ensure PdfPlumberTextAdapter satisfies NativeTextExtractorPort
_native_check: NativeTextExtractorPort = PdfPlumberTextAdapter()


class PaddleOcrAdapter:
    """OCR adapter using PaddleOCR.

    Implements OcrServicePort for text recognition.
    PaddleOCR is recommended for:
    - High accuracy on Japanese text
    - Good performance
    - Active development

    Note: This is a stub implementation. Full implementation
    requires PaddleOCR installation and configuration.
    """

    def __init__(
        self,
        lang: str = "japan",
        use_gpu: bool = False,
    ) -> None:
        """Initialize PaddleOCR adapter.

        Args:
            lang: Language for OCR (default: japan)
            use_gpu: Whether to use GPU acceleration
        """
        self._lang = lang
        self._use_gpu = use_gpu
        self._ocr = None  # Lazy initialization

    def _init_ocr(self) -> None:
        """Lazy initialize PaddleOCR to avoid import overhead."""
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(
                    lang=self._lang,
                    use_gpu=self._use_gpu,
                    show_log=False,
                )
            except ImportError:
                logger.warning("PaddleOCR not installed. Install with: pip install paddleocr")
                raise RuntimeError("PaddleOCR not available. Install with: pip install paddleocr")

    async def recognize(
        self,
        image_data: bytes,
        page: int,
        region: BBox | None = None,
        language: str = "ja+en",
    ) -> OcrResult:
        """Perform OCR on an image.

        Args:
            image_data: Image bytes (PNG/JPEG)
            page: Page number for result metadata
            region: Optional region within the image to OCR
            language: Language(s) to recognize

        Returns:
            OcrResult with recognized text

        Raises:
            RuntimeError: If PaddleOCR is not installed
        """
        # For now, raise NotImplementedError until PaddleOCR is added to dependencies
        raise NotImplementedError(
            "PaddleOCR integration pending. Use TesseractAdapter as fallback."
        )

    async def recognize_region(
        self,
        image_data: bytes,
        page: int,
        bbox: BBox,
        language: str = "ja+en",
    ) -> OcrResult:
        """Perform OCR on a specific region.

        Args:
            image_data: Full page image bytes
            page: Page number for result metadata
            bbox: Bounding box of region to OCR
            language: Language(s) to recognize

        Returns:
            OcrResult for the specified region
        """
        return await self.recognize(
            image_data=image_data,
            page=page,
            region=bbox,
            language=language,
        )


# Ensure PaddleOcrAdapter satisfies OcrServicePort
_paddle_check: OcrServicePort = PaddleOcrAdapter()


class TesseractAdapter:
    """OCR adapter using pytesseract.

    Implements OcrServicePort as an alternative to PaddleOCR.
    Tesseract is a fallback option with:
    - Wide language support
    - Well-established codebase
    - No GPU requirement

    Note: This is a stub implementation. Full implementation
    requires pytesseract and Tesseract OCR installation.
    """

    def __init__(
        self,
        lang: str = "jpn+eng",
        tesseract_cmd: str | None = None,
    ) -> None:
        """Initialize Tesseract adapter.

        Args:
            lang: Tesseract language codes (default: jpn+eng)
            tesseract_cmd: Path to tesseract executable
        """
        self._lang = lang
        self._tesseract_cmd = tesseract_cmd

    async def recognize(
        self,
        image_data: bytes,
        page: int,
        region: BBox | None = None,
        language: str = "ja+en",
    ) -> OcrResult:
        """Perform OCR on an image using Tesseract.

        Args:
            image_data: Image bytes (PNG/JPEG)
            page: Page number for result metadata
            region: Optional region to OCR
            language: Language(s) to recognize

        Returns:
            OcrResult with recognized text

        Raises:
            RuntimeError: If pytesseract is not installed
        """
        # For now, raise NotImplementedError until pytesseract is added
        raise NotImplementedError(
            "Tesseract integration pending. Install pytesseract and Tesseract OCR."
        )

    async def recognize_region(
        self,
        image_data: bytes,
        page: int,
        bbox: BBox,
        language: str = "ja+en",
    ) -> OcrResult:
        """Perform OCR on a specific region using Tesseract.

        Args:
            image_data: Full page image bytes
            page: Page number for result metadata
            bbox: Bounding box of region to OCR
            language: Language(s) to recognize

        Returns:
            OcrResult for the specified region
        """
        return await self.recognize(
            image_data=image_data,
            page=page,
            region=bbox,
            language=language,
        )


# Ensure TesseractAdapter satisfies OcrServicePort
_tesseract_check: OcrServicePort = TesseractAdapter()
