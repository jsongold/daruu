"""OCR Gateway interface.

Defines the contract for OCR text extraction operations.
Implementations can use PaddleOCR, pytesseract, EasyOCR, or cloud services.

Key responsibilities:
- Extract text with position information
- Provide confidence scores for extracted text
- Support cropped region extraction
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class OCRToken(BaseModel):
    """A single token/word from OCR extraction."""

    text: str = Field(..., description="Token text")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="Bounding box (x0, y0, x1, y1)"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="OCR confidence")

    model_config = {"frozen": True}


class OCRLine(BaseModel):
    """A line of text from OCR extraction."""

    text: str = Field(..., description="Line text")
    bbox: tuple[float, float, float, float] = Field(
        ..., description="Bounding box (x0, y0, x1, y1)"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Average confidence")
    tokens: list[OCRToken] = Field(default_factory=list, description="Tokens in this line")

    model_config = {"frozen": True}


class OCRResult(BaseModel):
    """Complete OCR extraction result."""

    ocr_text: str = Field(..., description="Full extracted text")
    ocr_tokens: list[OCRToken] = Field(
        default_factory=list, description="Individual tokens with positions"
    )
    ocr_lines: list[OCRLine] = Field(default_factory=list, description="Lines with positions")
    ocr_language: str = Field(default="ja-JP", description="Detected/specified language")
    average_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Average confidence across all tokens"
    )
    artifacts: dict[str, str] = Field(
        default_factory=dict,
        description="Optional artifacts (crop image refs, preprocessing info)",
    )

    model_config = {"frozen": True}


@runtime_checkable
class OCRGateway(Protocol):
    """Interface for OCR operations.

    This gateway abstracts OCR functionality, allowing different
    OCR engines to be swapped (PaddleOCR, pytesseract, EasyOCR, etc.).
    """

    async def extract_text(
        self,
        image_ref: str,
        crop_bbox: tuple[float, float, float, float] | None = None,
        language: str = "ja",
    ) -> OCRResult:
        """Extract text with positions from an image.

        Args:
            image_ref: Reference to the image (path or storage URL)
            crop_bbox: Optional bounding box to crop before OCR (x0, y0, x1, y1)
            language: Language hint for OCR engine

        Returns:
            OCR result with text, tokens, lines, and confidence scores

        The result structure follows the PRD specification:
        - ocr_text: Full text (concatenated lines/words)
        - ocr_tokens[]: Individual tokens with (text, bbox, confidence)
        - ocr_lines[]: Lines with (text, bbox, confidence)
        - ocr_language: Detected or specified language
        - artifacts: Optional preprocessing/crop image references
        """
        ...

    async def extract_text_batch(
        self,
        image_refs: list[str],
        crop_bboxes: list[tuple[float, float, float, float] | None] | None = None,
        language: str = "ja",
    ) -> list[OCRResult]:
        """Batch extract text from multiple images.

        More efficient than calling extract_text multiple times.

        Args:
            image_refs: List of image references
            crop_bboxes: Optional list of crop regions (same length as image_refs)
            language: Language hint for OCR engine

        Returns:
            List of OCR results, one per image
        """
        ...

    async def detect_text_regions(
        self,
        image_ref: str,
    ) -> list[tuple[float, float, float, float]]:
        """Detect text regions in an image without full OCR.

        Useful for identifying potential label/field regions
        before running full OCR.

        Args:
            image_ref: Reference to the image

        Returns:
            List of bounding boxes where text was detected
        """
        ...
