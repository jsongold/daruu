"""Domain rules for PDF validation and processing.

This module contains pure domain logic for:
- PDF validation (format, structure)
- Page range validation
- Render configuration
- Error classification

These functions are pure and have no external dependencies,
making them easy to test and reason about.
"""

from dataclasses import dataclass
from typing import Sequence

from app.config import get_ingest_config
from app.models.ingest import IngestErrorCode


@dataclass(frozen=True)
class ValidationResult:
    """Immutable validation result.

    Represents the outcome of validating PDF input or configuration.
    The frozen=True ensures immutability.
    """

    is_valid: bool
    error_code: IngestErrorCode | None
    error_message: str | None

    @staticmethod
    def success() -> "ValidationResult":
        """Create a successful validation result."""
        return ValidationResult(
            is_valid=True,
            error_code=None,
            error_message=None,
        )

    @staticmethod
    def failure(
        error_code: IngestErrorCode,
        error_message: str,
    ) -> "ValidationResult":
        """Create a failed validation result."""
        return ValidationResult(
            is_valid=False,
            error_code=error_code,
            error_message=error_message,
        )


@dataclass(frozen=True)
class RenderConfig:
    """Immutable configuration for page rendering.

    Contains all parameters needed for rendering PDF pages to images.
    """

    dpi: int
    format: str  # "png" or "jpeg"
    quality: int  # 0-100, only for jpeg
    alpha: bool  # Include alpha channel (transparency)

    def __post_init__(self) -> None:
        """Validate config values after initialization."""
        # Note: We validate in functions below since dataclass frozen
        # doesn't allow raising in __post_init__ easily
        pass


def get_default_render_config() -> RenderConfig:
    """Get default rendering configuration from centralized config.

    Returns:
        RenderConfig with default values from centralized config.
    """
    config = get_ingest_config()
    return RenderConfig(
        dpi=config.default_dpi,
        format=config.default_format,
        quality=config.default_quality,
        alpha=False,
    )


# Default rendering configuration (legacy, use get_default_render_config())
DEFAULT_RENDER_CONFIG = RenderConfig(
    dpi=150,
    format="png",
    quality=95,
    alpha=False,
)

# PDF file signature (magic bytes)
PDF_SIGNATURE = b"%PDF"


def get_max_page_count() -> int:
    """Get maximum page count from centralized config."""
    return get_ingest_config().max_page_count


def get_min_dpi() -> int:
    """Get minimum DPI from centralized config."""
    return get_ingest_config().min_dpi


def get_max_dpi() -> int:
    """Get maximum DPI from centralized config."""
    return get_ingest_config().max_dpi


# Legacy constants (use functions above for config-driven values)
MAX_PAGE_COUNT = 10000
MIN_DPI = 72
MAX_DPI = 600


def validate_pdf_signature(data: bytes) -> ValidationResult:
    """Validate that data has a valid PDF signature.

    Checks if the data starts with the PDF magic bytes (%PDF).

    Args:
        data: Raw bytes to validate.

    Returns:
        ValidationResult indicating if the signature is valid.
    """
    if not data:
        return ValidationResult.failure(
            IngestErrorCode.EMPTY_DOCUMENT,
            "Document data is empty",
        )

    if len(data) < 4:
        return ValidationResult.failure(
            IngestErrorCode.INVALID_PDF,
            "Document too small to be a valid PDF",
        )

    if not data.startswith(PDF_SIGNATURE):
        return ValidationResult.failure(
            IngestErrorCode.INVALID_PDF,
            "Document does not have a valid PDF signature",
        )

    return ValidationResult.success()


def validate_page_range(
    requested_pages: Sequence[int] | None,
    total_pages: int,
) -> ValidationResult:
    """Validate that requested page numbers are within range.

    Args:
        requested_pages: 1-indexed page numbers to validate (None means all pages).
        total_pages: Total number of pages in the document.

    Returns:
        ValidationResult indicating if the page range is valid.
    """
    if total_pages < 1:
        return ValidationResult.failure(
            IngestErrorCode.EMPTY_DOCUMENT,
            "Document has no pages",
        )

    if total_pages > MAX_PAGE_COUNT:
        return ValidationResult.failure(
            IngestErrorCode.INVALID_PDF,
            f"Document has too many pages ({total_pages}). Maximum is {MAX_PAGE_COUNT}",
        )

    if requested_pages is None:
        # All pages requested, which is valid
        return ValidationResult.success()

    if not requested_pages:
        return ValidationResult.failure(
            IngestErrorCode.INVALID_PDF,
            "Page list cannot be empty",
        )

    for page_num in requested_pages:
        if page_num < 1:
            return ValidationResult.failure(
                IngestErrorCode.INVALID_PDF,
                f"Invalid page number {page_num}. Page numbers must be >= 1",
            )
        if page_num > total_pages:
            return ValidationResult.failure(
                IngestErrorCode.INVALID_PDF,
                f"Page {page_num} out of range. Document has {total_pages} pages",
            )

    return ValidationResult.success()


def validate_render_config(config: RenderConfig) -> ValidationResult:
    """Validate render configuration values.

    Args:
        config: Render configuration to validate.

    Returns:
        ValidationResult indicating if the configuration is valid.
    """
    if config.dpi < MIN_DPI:
        return ValidationResult.failure(
            IngestErrorCode.RENDER_FAILED,
            f"DPI too low ({config.dpi}). Minimum is {MIN_DPI}",
        )

    if config.dpi > MAX_DPI:
        return ValidationResult.failure(
            IngestErrorCode.RENDER_FAILED,
            f"DPI too high ({config.dpi}). Maximum is {MAX_DPI}",
        )

    if config.format not in ("png", "jpeg"):
        return ValidationResult.failure(
            IngestErrorCode.RENDER_FAILED,
            f"Unsupported format '{config.format}'. Use 'png' or 'jpeg'",
        )

    if config.quality < 0 or config.quality > 100:
        return ValidationResult.failure(
            IngestErrorCode.RENDER_FAILED,
            f"Quality must be between 0 and 100, got {config.quality}",
        )

    return ValidationResult.success()


def classify_pdf_error(error_message: str) -> tuple[IngestErrorCode, str]:
    """Classify a PDF library error into an IngestErrorCode.

    Maps common PDF library error messages to appropriate error codes
    for user-friendly error reporting.

    Args:
        error_message: Error message from the PDF library.

    Returns:
        Tuple of (error_code, user_friendly_message).
    """
    error_lower = error_message.lower()

    # Password protection errors
    password_keywords = [
        "password",
        "encrypted",
        "decryption",
        "permission",
        "secured",
    ]
    if any(kw in error_lower for kw in password_keywords):
        return (
            IngestErrorCode.PASSWORD_PROTECTED,
            "PDF is password-protected and cannot be processed",
        )

    # Corruption errors
    corruption_keywords = [
        "corrupt",
        "damaged",
        "invalid",
        "malformed",
        "truncated",
        "broken",
        "bad",
        "cannot read",
        "cannot open",
        "failed to open",
    ]
    if any(kw in error_lower for kw in corruption_keywords):
        return (
            IngestErrorCode.CORRUPTED_FILE,
            "PDF file appears to be corrupted or damaged",
        )

    # Format errors
    format_keywords = [
        "not a pdf",
        "format not supported",
        "unsupported",
        "unrecognized",
    ]
    if any(kw in error_lower for kw in format_keywords):
        return (
            IngestErrorCode.UNSUPPORTED_FORMAT,
            "File format is not supported",
        )

    # Default to invalid PDF
    return (
        IngestErrorCode.INVALID_PDF,
        f"Failed to process PDF: {error_message}",
    )


def calculate_render_dimensions(
    width_points: float,
    height_points: float,
    dpi: int,
) -> tuple[int, int]:
    """Calculate pixel dimensions for rendered page.

    PDF dimensions are in points (1/72 inch).
    Converts to pixels based on target DPI.

    Args:
        width_points: Page width in points.
        height_points: Page height in points.
        dpi: Target resolution in dots per inch.

    Returns:
        Tuple of (width_pixels, height_pixels).
    """
    # Points to inches: divide by 72
    # Inches to pixels: multiply by DPI
    scale = dpi / 72.0
    width_pixels = int(width_points * scale)
    height_pixels = int(height_points * scale)
    return (width_pixels, height_pixels)
