"""Ingest service for PDF normalization and processing.

This is a deterministic Service (no Agent) that orchestrates PDF ingestion:
1. Validates the PDF document
2. Extracts metadata (page count, dimensions, rotation)
3. Renders pages to images for Agent/OCR processing
4. Stores artifacts and returns results

Service vs Agent:
- This is a Service (deterministic, no LLM reasoning)
- It prepares data for downstream Services that may use Agents
"""

from dataclasses import dataclass
from typing import Sequence

from app.models.ingest import (
    DocumentMeta,
    IngestError,
    IngestErrorCode,
    IngestRequest,
    IngestResult,
    PageMeta,
    RenderedPage,
)
from app.services.ingest.domain.rules import (
    RenderConfig,
    ValidationResult,
    calculate_render_dimensions,
    classify_pdf_error,
    validate_page_range,
    validate_render_config,
)
from app.services.ingest.ports import PdfReaderPort, StoragePort


@dataclass(frozen=True)
class IngestContext:
    """Immutable context for ingest operation.

    Carries all state needed during the ingest workflow.
    Uses frozen=True for immutability.
    """

    document_id: str
    document_ref: str
    render_config: RenderConfig
    pages_to_render: Sequence[int] | None


class IngestService:
    """Application service for PDF ingestion.

    Coordinates PDF validation, metadata extraction, and page rendering
    using injected adapters for PDF reading and storage.

    Example usage:
        pdf_reader = PyMuPdfAdapter()
        storage = LocalStorageAdapter(base_path="/data/artifacts")
        service = IngestService(pdf_reader, storage)

        request = IngestRequest(
            document_id="doc-123",
            document_ref="/uploads/document.pdf",
            render_dpi=150,
        )
        result = await service.ingest(request)
    """

    def __init__(
        self,
        pdf_reader: PdfReaderPort,
        storage: StoragePort,
    ) -> None:
        """Initialize the ingest service with adapters.

        Args:
            pdf_reader: Adapter for reading and rendering PDFs
            storage: Adapter for storing rendered artifacts
        """
        self._pdf_reader = pdf_reader
        self._storage = storage

    async def ingest(self, request: IngestRequest) -> IngestResult:
        """Ingest a PDF document.

        Validates the document, extracts metadata, and renders
        pages to images for downstream processing.

        Workflow:
        1. Validate PDF file (signature, structure)
        2. Extract document metadata (page count, dimensions)
        3. Validate render configuration
        4. Render requested pages to images
        5. Store artifacts and return result

        Args:
            request: Ingest request with document ID and reference

        Returns:
            IngestResult with metadata, artifacts, and any errors
        """
        # Build context from request
        context = self._build_context(request)

        # Step 1: Validate PDF file
        validation_result = self._validate_pdf_file(context.document_ref)
        if not validation_result.is_valid:
            return self._create_error_result(
                context.document_id,
                validation_result.error_code or IngestErrorCode.INVALID_PDF,
                validation_result.error_message or "PDF validation failed",
            )

        # Step 2: Extract document metadata
        try:
            document_meta = self._extract_metadata(context.document_ref)
        except Exception as e:
            error_code, error_message = classify_pdf_error(str(e))
            return self._create_error_result(
                context.document_id,
                error_code,
                error_message,
            )

        # Step 3: Validate page range
        pages_to_render = self._resolve_pages_to_render(
            context.pages_to_render,
            document_meta.page_count,
        )
        page_validation = validate_page_range(
            pages_to_render,
            document_meta.page_count,
        )
        if not page_validation.is_valid:
            return self._create_error_result(
                context.document_id,
                page_validation.error_code or IngestErrorCode.INVALID_PDF,
                page_validation.error_message or "Invalid page range",
            )

        # Step 4: Validate render configuration
        config_validation = validate_render_config(context.render_config)
        if not config_validation.is_valid:
            return self._create_error_result(
                context.document_id,
                config_validation.error_code or IngestErrorCode.RENDER_FAILED,
                config_validation.error_message or "Invalid render configuration",
            )

        # Step 5: Render pages and store artifacts
        artifacts, render_errors = self._render_and_store_pages(
            context,
            document_meta,
            pages_to_render,
        )

        # Build final result
        return self._create_success_result(
            context.document_id,
            document_meta,
            artifacts,
            render_errors,
        )

    async def render_page(
        self,
        document_ref: str,
        page_number: int,
        dpi: int = 150,
    ) -> bytes:
        """Render a single page to PNG image.

        Convenience method for re-rendering a specific page
        without full ingestion.

        Args:
            document_ref: Reference/path to the PDF file
            page_number: 1-indexed page number
            dpi: Resolution for rendering

        Returns:
            PNG image bytes

        Raises:
            ValueError: If page cannot be rendered
        """
        # Validate page number
        if page_number < 1:
            raise ValueError(f"Page number must be >= 1, got {page_number}")

        # Render page
        return self._pdf_reader.render_page(document_ref, page_number, dpi)

    async def get_metadata(self, document_ref: str) -> IngestResult:
        """Extract metadata without rendering pages.

        Lightweight operation for getting document info
        without the overhead of page rendering.

        Args:
            document_ref: Reference/path to the PDF file

        Returns:
            IngestResult with metadata only (no artifacts)
        """
        # Validate PDF
        validation_result = self._validate_pdf_file(document_ref)
        if not validation_result.is_valid:
            return IngestResult(
                document_id="",
                success=False,
                meta=None,
                artifacts=(),
                errors=(
                    IngestError(
                        code=validation_result.error_code or IngestErrorCode.INVALID_PDF,
                        message=validation_result.error_message or "Validation failed",
                    ),
                ),
            )

        # Extract metadata
        try:
            document_meta = self._extract_metadata(document_ref)
            return IngestResult(
                document_id="",
                success=True,
                meta=document_meta,
                artifacts=(),
                errors=(),
            )
        except Exception as e:
            error_code, error_message = classify_pdf_error(str(e))
            return IngestResult(
                document_id="",
                success=False,
                meta=None,
                artifacts=(),
                errors=(IngestError(code=error_code, message=error_message),),
            )

    def _build_context(self, request: IngestRequest) -> IngestContext:
        """Build immutable context from request.

        Args:
            request: The ingest request

        Returns:
            IngestContext with validated parameters
        """
        render_config = RenderConfig(
            dpi=request.render_dpi,
            format="png",
            quality=95,
            alpha=False,
        )

        return IngestContext(
            document_id=request.document_id,
            document_ref=request.document_ref,
            render_config=render_config,
            pages_to_render=(
                tuple(request.render_pages)
                if request.render_pages is not None
                else None
            ),
        )

    def _validate_pdf_file(self, document_ref: str) -> ValidationResult:
        """Validate PDF file using adapter.

        Args:
            document_ref: Path to the PDF file

        Returns:
            ValidationResult from adapter validation
        """
        is_valid, error_message = self._pdf_reader.validate(document_ref)

        if is_valid:
            return ValidationResult.success()

        # Classify the error
        error_code, user_message = classify_pdf_error(error_message or "Unknown error")
        return ValidationResult.failure(error_code, user_message)

    def _extract_metadata(self, document_ref: str) -> DocumentMeta:
        """Extract document metadata using adapter.

        Args:
            document_ref: Path to the PDF file

        Returns:
            DocumentMeta with page information

        Raises:
            Exception: If metadata extraction fails
        """
        return self._pdf_reader.get_meta(document_ref)

    def _resolve_pages_to_render(
        self,
        requested_pages: Sequence[int] | None,
        total_pages: int,
    ) -> tuple[int, ...]:
        """Resolve which pages to render.

        If no specific pages requested, returns all pages.

        Args:
            requested_pages: Specific pages requested (1-indexed)
            total_pages: Total pages in document

        Returns:
            Tuple of 1-indexed page numbers to render
        """
        if requested_pages is not None:
            return tuple(requested_pages)
        return tuple(range(1, total_pages + 1))

    def _render_and_store_pages(
        self,
        context: IngestContext,
        document_meta: DocumentMeta,
        pages_to_render: tuple[int, ...],
    ) -> tuple[tuple[RenderedPage, ...], tuple[IngestError, ...]]:
        """Render pages and store as artifacts.

        Args:
            context: Ingest context with configuration
            document_meta: Document metadata for dimension lookup
            pages_to_render: Pages to render (1-indexed)

        Returns:
            Tuple of (rendered_pages, errors)
        """
        artifacts: list[RenderedPage] = []
        errors: list[IngestError] = []

        for page_num in pages_to_render:
            try:
                # Render page to image bytes
                image_data = self._pdf_reader.render_page(
                    context.document_ref,
                    page_num,
                    context.render_config.dpi,
                )

                # Store the image
                image_ref = self._storage.save_image(
                    document_id=context.document_id,
                    page_number=page_num,
                    image_data=image_data,
                    content_type="image/png",
                )

                # Calculate rendered dimensions
                page_meta = self._get_page_meta(document_meta, page_num)
                width_pixels, height_pixels = calculate_render_dimensions(
                    page_meta.width,
                    page_meta.height,
                    context.render_config.dpi,
                )

                # Create artifact record
                rendered_page = RenderedPage(
                    page_number=page_num,
                    image_ref=image_ref,
                    width=width_pixels,
                    height=height_pixels,
                    dpi=context.render_config.dpi,
                )
                artifacts.append(rendered_page)

            except Exception as e:
                # Record error but continue with other pages
                error_code, error_message = classify_pdf_error(str(e))
                errors.append(
                    IngestError(
                        code=error_code,
                        message=error_message,
                        page_number=page_num,
                    )
                )

        return tuple(artifacts), tuple(errors)

    def _get_page_meta(
        self,
        document_meta: DocumentMeta,
        page_number: int,
    ) -> PageMeta:
        """Get metadata for a specific page.

        Args:
            document_meta: Document metadata with pages
            page_number: 1-indexed page number

        Returns:
            PageMeta for the requested page
        """
        # Pages tuple is 0-indexed, page_number is 1-indexed
        page_index = page_number - 1
        if page_index < 0 or page_index >= len(document_meta.pages):
            raise ValueError(f"Page {page_number} not found in metadata")
        return document_meta.pages[page_index]

    def _create_error_result(
        self,
        document_id: str,
        error_code: IngestErrorCode,
        error_message: str,
    ) -> IngestResult:
        """Create an error result.

        Args:
            document_id: Document identifier
            error_code: Error classification
            error_message: Human-readable error

        Returns:
            IngestResult indicating failure
        """
        return IngestResult(
            document_id=document_id,
            success=False,
            meta=None,
            artifacts=(),
            errors=(
                IngestError(
                    code=error_code,
                    message=error_message,
                ),
            ),
        )

    def _create_success_result(
        self,
        document_id: str,
        document_meta: DocumentMeta,
        artifacts: tuple[RenderedPage, ...],
        errors: tuple[IngestError, ...],
    ) -> IngestResult:
        """Create a success result.

        Note: Success can have partial errors (e.g., some pages failed to render).

        Args:
            document_id: Document identifier
            document_meta: Extracted metadata
            artifacts: Rendered page artifacts
            errors: Any errors encountered during rendering

        Returns:
            IngestResult indicating success (possibly partial)
        """
        # Consider it a success if we have metadata and at least some artifacts
        # or if no pages were requested to render
        has_artifacts = len(artifacts) > 0
        has_critical_errors = any(
            e.code in (IngestErrorCode.CORRUPTED_FILE, IngestErrorCode.PASSWORD_PROTECTED)
            for e in errors
        )

        success = has_artifacts and not has_critical_errors

        return IngestResult(
            document_id=document_id,
            success=success,
            meta=document_meta,
            artifacts=artifacts,
            errors=errors,
        )
