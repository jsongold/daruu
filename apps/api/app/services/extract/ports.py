"""Port interfaces for the Extract service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.

Ports defined:
- NativeTextExtractorPort: For extracting text from PDF natively
- OcrServicePort: For OCR processing
- ValueExtractionAgentPort: For LLM-assisted value extraction
"""

from typing import Protocol

from app.models.common import BBox
from app.models.extract.models import ExtractField, FollowupQuestion
from app.services.extract.domain.models import (
    NativeTextResult,
    OcrResult,
    ValueCandidate,
)


class NativeTextExtractorPort(Protocol):
    """Port for extracting native text from PDF documents.

    Implementations should handle:
    - Text extraction from vector/text-based PDFs
    - Position/bbox preservation
    - Font information extraction

    Example implementations:
    - PdfPlumberAdapter: Uses pdfplumber library
    - PyMuPdfTextAdapter: Uses PyMuPDF (fitz) library
    """

    async def extract_text(
        self,
        document_ref: str,
        page: int,
        region: BBox | None = None,
    ) -> NativeTextResult:
        """Extract native text from a PDF page or region.

        Args:
            document_ref: Reference/path to the PDF file
            page: Page number (1-indexed)
            region: Optional bounding box to limit extraction

        Returns:
            NativeTextResult with extracted lines and positions

        Raises:
            ValueError: If document or page not found
            RuntimeError: If extraction fails
        """
        ...

    async def has_text_layer(self, document_ref: str) -> bool:
        """Check if document has a native text layer.

        Args:
            document_ref: Reference/path to the PDF file

        Returns:
            True if document has extractable text layer
        """
        ...


class OcrServicePort(Protocol):
    """Port for OCR (Optical Character Recognition) processing.

    Implementations should handle:
    - Text recognition from images
    - Position/bbox calculation
    - Confidence scoring
    - Line/token segmentation

    Example implementations:
    - PaddleOcrAdapter: Uses PaddleOCR (recommended)
    - TesseractAdapter: Uses pytesseract
    - EasyOcrAdapter: Uses EasyOCR
    """

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
            language: Language(s) to recognize (default: Japanese + English)

        Returns:
            OcrResult with recognized text, tokens, and confidence

        Raises:
            ValueError: If image format is invalid
            RuntimeError: If OCR fails
        """
        ...

    async def recognize_region(
        self,
        image_data: bytes,
        page: int,
        bbox: BBox,
        language: str = "ja+en",
    ) -> OcrResult:
        """Perform OCR on a specific region of an image.

        Convenience method that crops the image before OCR.

        Args:
            image_data: Full page image bytes
            page: Page number for result metadata
            bbox: Bounding box of region to OCR
            language: Language(s) to recognize

        Returns:
            OcrResult for the specified region

        Raises:
            ValueError: If bbox is out of bounds
            RuntimeError: If OCR fails
        """
        ...


class ValueExtractionAgentPort(Protocol):
    """Port for LLM-assisted value extraction and normalization.

    This agent uses LLM to:
    - Resolve ambiguity when multiple value candidates exist
    - Normalize values (dates, addresses, names, numbers)
    - Detect conflicts between different sources
    - Generate follow-up questions for missing/uncertain fields

    NOTE: This is NOT an OCR replacement. It only assists with:
    - Ambiguity resolution
    - Format normalization
    - Conflict detection
    - Question generation

    Example implementations:
    - LangChainValueExtractionAgent: Uses LangChain framework
    - OpenAIValueExtractionAgent: Direct OpenAI API
    """

    async def resolve_candidates(
        self,
        field: ExtractField,
        candidates: tuple[ValueCandidate, ...],
        context: dict[str, any] | None = None,
    ) -> ValueCandidate:
        """Resolve ambiguity when multiple candidates exist.

        Uses LLM reasoning to select the best candidate based on:
        - Field type and validation rules
        - Confidence scores
        - Contextual clues

        Args:
            field: Field definition with type and validation
            candidates: Possible value candidates
            context: Optional additional context

        Returns:
            Selected best candidate with updated confidence

        Raises:
            ValueError: If no candidates provided
            RuntimeError: If LLM call fails
        """
        ...

    async def normalize_value(
        self,
        field: ExtractField,
        value: str,
        target_format: str | None = None,
    ) -> str:
        """Normalize a value to a standard format.

        Handles:
        - Date format standardization (YYYY-MM-DD)
        - Full-width to half-width conversion
        - Address normalization
        - Name format standardization

        Args:
            field: Field definition with type
            value: Raw extracted value
            target_format: Optional target format specification

        Returns:
            Normalized value string

        Raises:
            ValueError: If value cannot be normalized
        """
        ...

    async def detect_conflicts(
        self,
        field: ExtractField,
        candidates: tuple[ValueCandidate, ...],
    ) -> tuple[bool, str | None]:
        """Detect conflicts between value candidates.

        Args:
            field: Field definition
            candidates: Value candidates from different sources

        Returns:
            Tuple of (has_conflict, conflict_description)
        """
        ...

    async def generate_question(
        self,
        field: ExtractField,
        reason: str,
        candidates: tuple[ValueCandidate, ...] | None = None,
    ) -> FollowupQuestion:
        """Generate a follow-up question for user clarification.

        Args:
            field: Field that needs clarification
            reason: Why clarification is needed
            candidates: Optional candidates to present to user

        Returns:
            FollowupQuestion with user-friendly question

        Raises:
            RuntimeError: If question generation fails
        """
        ...
