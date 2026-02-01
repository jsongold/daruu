"""Fill service for PDF form filling and text overlay.

This is a deterministic Service (no Agent) that orchestrates PDF filling:
1. Analyzes the target PDF to detect fill method
2. For AcroForm PDFs: fills form fields directly
3. For non-AcroForm PDFs: creates text overlays and merges

Service vs Agent:
- This is a Service (deterministic, no LLM reasoning)
- Same input always produces the same output
- All text rendering rules are algorithmic
"""

import uuid
from typing import Callable

from app.models.fill import (
    FieldFillResult,
    FillError,
    FillErrorCode,
    FillIssue,
    FillMethod,
    FillRequest,
    FillResult,
    FillValue,
    IssueSeverity,
    IssueType,
    RenderArtifact,
    RenderParams,
)
from app.services.fill.domain.models import (
    AcroFormField,
    BoundingBox,
    FieldSpec,
    FontConfig,
    OverlaySpec,
)
from app.services.fill.domain.rules import (
    detect_overlap,
    layout_text_block,
)
from app.services.fill.ports import (
    AcroFormWriterPort,
    OverlayRendererPort,
    PdfMergerPort,
    PdfReaderPort,
    StoragePort,
    TextMeasurePort,
)


class FillService:
    """Application service for filling PDF documents.

    Coordinates PDF form filling using injected adapters for
    PDF reading, writing, overlay generation, and storage.

    Example usage:
        pdf_reader = PyMuPdfReaderAdapter()
        acroform_writer = PyMuPdfAcroFormAdapter()
        overlay_renderer = ReportlabOverlayAdapter()
        pdf_merger = PyMuPdfMergerAdapter()
        storage = LocalStorageAdapter(base_path="/data/filled")
        text_measure = ReportlabMeasureAdapter()

        service = FillService(
            pdf_reader=pdf_reader,
            acroform_writer=acroform_writer,
            overlay_renderer=overlay_renderer,
            pdf_merger=pdf_merger,
            storage=storage,
            text_measure=text_measure,
        )

        request = FillRequest(
            target_document_ref="/uploads/form.pdf",
            fields=(FillValue(field_id="name", value="John Doe"),),
        )
        result = await service.fill(request)
    """

    def __init__(
        self,
        pdf_reader: PdfReaderPort,
        acroform_writer: AcroFormWriterPort,
        overlay_renderer: OverlayRendererPort,
        pdf_merger: PdfMergerPort,
        storage: StoragePort,
        text_measure: TextMeasurePort,
    ) -> None:
        """Initialize the fill service with adapters.

        Args:
            pdf_reader: Adapter for reading PDFs and detecting form fields
            acroform_writer: Adapter for filling AcroForm fields
            overlay_renderer: Adapter for creating text overlay PDFs
            pdf_merger: Adapter for merging overlays with base PDFs
            storage: Adapter for storing filled PDFs
            text_measure: Adapter for measuring text dimensions
        """
        self._pdf_reader = pdf_reader
        self._acroform_writer = acroform_writer
        self._overlay_renderer = overlay_renderer
        self._pdf_merger = pdf_merger
        self._storage = storage
        self._text_measure = text_measure

    async def fill(self, request: FillRequest) -> FillResult:
        """Fill a PDF document with values.

        Automatically detects the appropriate fill method (AcroForm or overlay)
        based on the document structure when method is AUTO.

        Args:
            request: Fill request with document reference and field values

        Returns:
            FillResult with filled document reference and any issues
        """
        # Load and validate the document
        if not self._pdf_reader.load(request.target_document_ref):
            return self._create_error_result(
                FillErrorCode.DOCUMENT_NOT_FOUND,
                f"Could not load document: {request.target_document_ref}",
            )

        try:
            # Determine fill method
            method = self._determine_method(request.method)

            if method == FillMethod.ACROFORM:
                return await self._fill_acroform(request)
            else:
                return await self._fill_overlay(request)

        finally:
            self._pdf_reader.close()

    def _determine_method(self, requested: FillMethod) -> FillMethod:
        """Determine the actual fill method to use.

        Args:
            requested: The requested fill method

        Returns:
            The actual method to use
        """
        if requested == FillMethod.AUTO:
            if self._pdf_reader.has_acroform():
                return FillMethod.ACROFORM
            return FillMethod.OVERLAY

        return requested

    async def _fill_acroform(self, request: FillRequest) -> FillResult:
        """Fill the document using AcroForm fields.

        Args:
            request: Fill request

        Returns:
            FillResult
        """
        if not self._acroform_writer.load(request.target_document_ref):
            return self._create_error_result(
                FillErrorCode.DOCUMENT_NOT_FOUND,
                "Could not load document for AcroForm editing",
            )

        try:
            field_results: list[FieldFillResult] = []
            issues: list[FillIssue] = []

            for fill_value in request.fields:
                result = self._fill_single_acroform_field(
                    fill_value,
                    request.render_params,
                    request.field_params,
                )
                field_results.append(result)
                issues.extend(result.issues)

            # Flatten form fields for consistent rendering
            self._acroform_writer.flatten()

            # Save the filled document
            output_id = str(uuid.uuid4())
            temp_path = self._storage.save_temp_file(
                prefix="filled_acroform",
                data=b"",  # Placeholder
                extension=".pdf",
            )

            if not self._acroform_writer.save(temp_path):
                return self._create_error_result(
                    FillErrorCode.STORAGE_FAILED,
                    "Failed to save filled document",
                )

            # Move to permanent storage
            with open(temp_path, "rb") as f:
                pdf_data = f.read()

            filled_ref = self._storage.save_pdf(
                document_id=output_id,
                pdf_data=pdf_data,
                suffix="_filled",
            )

            # Clean up temp file
            self._storage.delete(temp_path)

            # Calculate statistics
            filled_count = sum(1 for r in field_results if r.success)
            failed_count = len(field_results) - filled_count

            return FillResult(
                success=True,
                filled_document_ref=filled_ref,
                method_used=FillMethod.ACROFORM,
                field_results=tuple(field_results),
                filled_count=filled_count,
                failed_count=failed_count,
                errors=(),
                artifacts=(),
            )

        finally:
            self._acroform_writer.close()

    def _fill_single_acroform_field(
        self,
        fill_value: FillValue,
        default_params: RenderParams,
        field_params: dict[str, RenderParams] | None,
    ) -> FieldFillResult:
        """Fill a single AcroForm field.

        Args:
            fill_value: Field value to fill
            default_params: Default render parameters
            field_params: Field-specific render parameters

        Returns:
            FieldFillResult
        """
        # Get field-specific params or use defaults
        params = default_params
        if field_params and fill_value.field_id in field_params:
            params = field_params[fill_value.field_id]

        font_config = self._render_params_to_font_config(params)

        success = self._acroform_writer.set_field_value(
            field_name=fill_value.field_id,
            value=fill_value.value,
            font_config=font_config,
        )

        if not success:
            return FieldFillResult(
                field_id=fill_value.field_id,
                success=False,
                value_written=None,
                issues=(
                    FillIssue(
                        field_id=fill_value.field_id,
                        issue_type=IssueType.OVERFLOW,
                        severity=IssueSeverity.ERROR,
                        message=f"Field not found: {fill_value.field_id}",
                    ),
                ),
            )

        return FieldFillResult(
            field_id=fill_value.field_id,
            success=True,
            value_written=fill_value.value,
            issues=(),
        )

    async def _fill_overlay(self, request: FillRequest) -> FillResult:
        """Fill the document using text overlay method.

        Args:
            request: Fill request

        Returns:
            FillResult
        """
        field_results: list[FieldFillResult] = []
        all_issues: list[FillIssue] = []
        artifacts: list[RenderArtifact] = []

        # Group fields by page
        page_fields = self._group_fields_by_page(request.fields)

        # Create overlays for each page
        overlay_paths: dict[int, str] = {}
        bboxes: list[BoundingBox] = []

        for page_num, fields in page_fields.items():
            page_width, page_height = self._pdf_reader.get_page_dimensions(page_num)

            # Create overlay for this page
            self._overlay_renderer.create_overlay(page_width, page_height)

            # Check if borders should be rendered
            render_borders = (
                request.options.get("render_borders", False)
                if request.options
                else False
            )

            for fill_value in fields:
                result, bbox = self._render_field_to_overlay(
                    fill_value,
                    page_num,
                    request.render_params,
                    request.field_params,
                )
                field_results.append(result)
                all_issues.extend(result.issues)
                if bbox:
                    bboxes.append(bbox)

                    # Draw border around field if requested
                    if render_borders and bbox:
                        self._overlay_renderer.draw_rectangle(
                            x=bbox.x,
                            y=bbox.y,
                            width=bbox.width,
                            height=bbox.height,
                            stroke_color="#3b82f6",  # Blue border
                            stroke_width=0.5,
                            fill_color=None,
                        )

            # Save the overlay
            overlay_path = self._storage.save_temp_file(
                prefix=f"overlay_page_{page_num}",
                data=b"",
                extension=".pdf",
            )
            self._overlay_renderer.save_overlay(overlay_path)
            overlay_paths[page_num] = overlay_path

            artifacts.append(RenderArtifact(
                artifact_type="overlay",
                artifact_ref=overlay_path,
                page_number=page_num,
            ))

        # Detect overlapping fields
        overlap_issues = self._check_overlaps(bboxes, request.fields)
        all_issues.extend(overlap_issues)

        # Merge all overlays with the base document
        output_id = str(uuid.uuid4())
        output_path = self._storage.save_temp_file(
            prefix="filled_overlay",
            data=b"",
            extension=".pdf",
        )

        merge_success = self._pdf_merger.merge_all_overlays(
            base_pdf_path=request.target_document_ref,
            overlays=overlay_paths,
            output_path=output_path,
        )

        if not merge_success:
            return self._create_error_result(
                FillErrorCode.MERGE_FAILED,
                "Failed to merge overlays with base document",
            )

        # Move to permanent storage
        with open(output_path, "rb") as f:
            pdf_data = f.read()

        filled_ref = self._storage.save_pdf(
            document_id=output_id,
            pdf_data=pdf_data,
            suffix="_filled",
        )

        # Clean up temp files
        self._storage.delete(output_path)
        for overlay_path in overlay_paths.values():
            self._storage.delete(overlay_path)

        # Calculate statistics
        filled_count = sum(1 for r in field_results if r.success)
        failed_count = len(field_results) - filled_count

        return FillResult(
            success=True,
            filled_document_ref=filled_ref,
            method_used=FillMethod.OVERLAY,
            field_results=tuple(field_results),
            filled_count=filled_count,
            failed_count=failed_count,
            errors=(),
            artifacts=tuple(artifacts),
        )

    def _group_fields_by_page(
        self,
        fields: tuple[FillValue, ...],
    ) -> dict[int, list[FillValue]]:
        """Group fields by page number.

        Args:
            fields: Fields to group

        Returns:
            Dictionary mapping page numbers to field lists
        """
        result: dict[int, list[FillValue]] = {}

        for field in fields:
            # Default to page 1 if no bbox specified
            page = 1
            if field.bbox:
                page = field.bbox.page

            if page not in result:
                result[page] = []
            result[page].append(field)

        return result

    def _render_field_to_overlay(
        self,
        fill_value: FillValue,
        page_num: int,
        default_params: RenderParams,
        field_params: dict[str, RenderParams] | None,
    ) -> tuple[FieldFillResult, BoundingBox | None]:
        """Render a single field to the overlay.

        Args:
            fill_value: Field value to render
            page_num: Page number
            default_params: Default render parameters
            field_params: Field-specific render parameters

        Returns:
            Tuple of (FieldFillResult, BoundingBox or None)
        """
        # Get field-specific params or use defaults
        params = default_params
        if field_params and fill_value.field_id in field_params:
            params = field_params[fill_value.field_id]

        font_config = self._render_params_to_font_config(params)

        # Get bounding box
        if fill_value.bbox:
            bbox = BoundingBox(
                x=fill_value.bbox.x,
                y=fill_value.bbox.y,
                width=fill_value.bbox.width,
                height=fill_value.bbox.height,
                page=fill_value.bbox.page,
            )
        else:
            # Try to get bbox from document field definition
            bbox = self._pdf_reader.get_field_bbox(fill_value.field_id)
            if bbox is None:
                return (
                    FieldFillResult(
                        field_id=fill_value.field_id,
                        success=False,
                        value_written=None,
                        issues=(
                            FillIssue(
                                field_id=fill_value.field_id,
                                issue_type=IssueType.OUT_OF_BOUNDS,
                                severity=IssueSeverity.ERROR,
                                message=f"No bounding box for field: {fill_value.field_id}",
                            ),
                        ),
                    ),
                    None,
                )

        # Layout the text
        text_block = layout_text_block(
            text=fill_value.value,
            bbox=bbox,
            font=font_config,
            alignment=params.alignment,
            line_height=params.line_height,
            word_wrap=params.word_wrap,
            overflow_handling=params.overflow_handling,
            measure_fn=self._text_measure.measure,
        )

        # Track issues
        issues: list[FillIssue] = []
        if text_block.overflow:
            issues.append(FillIssue(
                field_id=fill_value.field_id,
                issue_type=IssueType.OVERFLOW,
                severity=IssueSeverity.WARNING,
                message=f"Text overflows bounding box for field: {fill_value.field_id}",
            ))
        if text_block.truncated:
            issues.append(FillIssue(
                field_id=fill_value.field_id,
                issue_type=IssueType.TRUNCATED,
                severity=IssueSeverity.WARNING,
                message=f"Text was truncated for field: {fill_value.field_id}",
            ))

        # Draw the text block
        success = self._overlay_renderer.draw_text_block(text_block, font_config)

        return (
            FieldFillResult(
                field_id=fill_value.field_id,
                success=success,
                value_written=fill_value.value if success else None,
                issues=tuple(issues),
            ),
            bbox,
        )

    def _check_overlaps(
        self,
        bboxes: list[BoundingBox],
        fields: tuple[FillValue, ...],
    ) -> list[FillIssue]:
        """Check for overlapping field bounding boxes.

        Args:
            bboxes: List of bounding boxes
            fields: Original field values for IDs

        Returns:
            List of overlap issues
        """
        issues: list[FillIssue] = []
        overlaps = detect_overlap(tuple(bboxes))

        for i, j in overlaps:
            field1_id = fields[i].field_id if i < len(fields) else "unknown"
            field2_id = fields[j].field_id if j < len(fields) else "unknown"

            issues.append(FillIssue(
                field_id=field1_id,
                issue_type=IssueType.OVERLAP,
                severity=IssueSeverity.WARNING,
                message=f"Field '{field1_id}' overlaps with '{field2_id}'",
                details={"overlapping_field": field2_id},
            ))

        return issues

    def _render_params_to_font_config(self, params: RenderParams) -> FontConfig:
        """Convert RenderParams to FontConfig.

        Args:
            params: Render parameters

        Returns:
            FontConfig for rendering
        """
        return FontConfig(
            family=params.font_name,
            size=params.font_size,
            color=params.font_color,
        )

    def _create_error_result(
        self,
        code: FillErrorCode,
        message: str,
        field_id: str | None = None,
    ) -> FillResult:
        """Create a FillResult with an error.

        Args:
            code: Error code
            message: Error message
            field_id: Optional field ID

        Returns:
            FillResult with error
        """
        return FillResult(
            success=False,
            filled_document_ref=None,
            method_used=FillMethod.AUTO,
            field_results=(),
            filled_count=0,
            failed_count=0,
            errors=(
                FillError(
                    code=code,
                    message=message,
                    field_id=field_id,
                ),
            ),
            artifacts=(),
        )
