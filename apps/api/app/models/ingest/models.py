"""Domain models for the Ingest service.

All models use frozen=True for immutability, following project conventions.
"""

from enum import Enum

from pydantic import BaseModel, Field


class IngestErrorCode(str, Enum):
    """Error codes for ingest failures."""

    INVALID_PDF = "INVALID_PDF"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    CORRUPTED_FILE = "CORRUPTED_FILE"
    EMPTY_DOCUMENT = "EMPTY_DOCUMENT"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    RENDER_FAILED = "RENDER_FAILED"
    STORAGE_FAILED = "STORAGE_FAILED"


class PageMeta(BaseModel):
    """Metadata for a single page in the document.

    Contains dimensions and rotation information needed for
    accurate rendering and coordinate mapping.
    """

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    width: float = Field(..., gt=0, description="Page width in points (1/72 inch)")
    height: float = Field(..., gt=0, description="Page height in points (1/72 inch)")
    rotation: int = Field(
        default=0,
        ge=0,
        le=270,
        description="Page rotation in degrees (0, 90, 180, 270)",
    )

    model_config = {"frozen": True}


class DocumentMeta(BaseModel):
    """Aggregated metadata for the entire document.

    Contains page count and per-page metadata needed for
    downstream processing stages.
    """

    page_count: int = Field(..., ge=1, description="Total number of pages")
    pages: tuple[PageMeta, ...] = Field(..., description="Metadata for each page (immutable tuple)")

    model_config = {"frozen": True}


class RenderedPage(BaseModel):
    """Reference to a rendered page image artifact.

    Contains the storage reference and dimensions of the
    rendered image for LLM/OCR processing.
    """

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    image_ref: str = Field(..., description="Storage reference/path to the image")
    width: int = Field(..., gt=0, description="Image width in pixels")
    height: int = Field(..., gt=0, description="Image height in pixels")
    dpi: int = Field(default=150, gt=0, description="Resolution in DPI")

    model_config = {"frozen": True}


class IngestError(BaseModel):
    """Error detail for ingest failures.

    Provides structured error information for validation
    and processing failures.
    """

    code: IngestErrorCode = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    page_number: int | None = Field(
        default=None, description="Page number if error is page-specific"
    )

    model_config = {"frozen": True}


class IngestRequest(BaseModel):
    """Request to ingest a PDF document.

    The document_ref points to the location where the PDF
    is stored (e.g., file path or storage URL).
    """

    document_id: str = Field(..., min_length=1, description="Unique document identifier")
    document_ref: str = Field(..., min_length=1, description="Reference/path to the PDF file")
    render_dpi: int = Field(default=150, gt=0, le=600, description="DPI for page rendering")
    render_pages: list[int] | None = Field(
        default=None,
        description="Specific pages to render (None = all pages)",
    )

    model_config = {"frozen": True}


class IngestResult(BaseModel):
    """Result of the ingest operation.

    Contains extracted metadata, rendered page artifacts,
    and any errors encountered during processing.
    """

    document_id: str = Field(..., description="Document identifier from request")
    success: bool = Field(..., description="Whether ingestion completed successfully")
    meta: DocumentMeta | None = Field(default=None, description="Document metadata (if successful)")
    artifacts: tuple[RenderedPage, ...] = Field(
        default=(), description="Rendered page images (immutable tuple)"
    )
    errors: tuple[IngestError, ...] = Field(
        default=(), description="Errors encountered (immutable tuple)"
    )

    model_config = {"frozen": True}
