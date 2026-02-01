"""Review service for visual inspection and issue detection.

This is a deterministic Service (no Agent/LLM) that performs:
1. Renders filled PDF documents to images
2. Generates visual diffs/overlays for quality inspection
3. Detects issues (overflow, overlap, missing values)
4. Produces preview artifacts for UI display

Service vs Agent:
- This is a Service (deterministic, same input -> same output)
- No LLM reasoning is used
- Pure geometric and visual analysis
"""

from typing import Sequence
from uuid import uuid4

from app.models.common import BBox
from app.models.field import FieldModel
from app.models.job import Issue, IssueSeverity, IssueType
from app.models.review import (
    ConfidenceUpdate,
    PreviewArtifact,
    ReviewRequest,
    ReviewResult,
)
from app.services.review.domain.rules import (
    calculate_confidence_update,
    check_boxes_overlap,
    check_text_overflow,
    detect_missing_value,
)
from app.services.review.ports import (
    DiffGeneratorPort,
    IssueDetectorPort,
    PdfRendererPort,
    PreviewStoragePort,
)


class ReviewService:
    """Application service for document review and issue detection.

    Coordinates PDF rendering, diff generation, and issue detection
    using injected adapters for each capability.

    Example usage:
        renderer = PyMuPdfRenderer()
        diff_gen = OpenCVDiffGenerator()
        detector = RuleBasedIssueDetector()
        storage = LocalPreviewStorage(base_path="/data/previews")

        service = ReviewService(renderer, diff_gen, detector, storage)

        request = ReviewRequest(
            document_id="doc-123",
            filled_document_ref="/uploads/filled.pdf",
            original_document_ref="/uploads/original.pdf",
            fields=[...],
            page_meta=[...],
        )
        result = await service.review(request)
    """

    def __init__(
        self,
        pdf_renderer: PdfRendererPort,
        diff_generator: DiffGeneratorPort,
        issue_detector: IssueDetectorPort,
        preview_storage: PreviewStoragePort,
    ) -> None:
        """Initialize the review service with adapters.

        Args:
            pdf_renderer: Adapter for rendering PDF pages
            diff_generator: Adapter for generating visual diffs
            issue_detector: Adapter for detecting visual issues
            preview_storage: Adapter for storing preview artifacts
        """
        self._pdf_renderer = pdf_renderer
        self._diff_generator = diff_generator
        self._issue_detector = issue_detector
        self._preview_storage = preview_storage

    async def review(self, request: ReviewRequest) -> ReviewResult:
        """Review a filled document for issues.

        Performs comprehensive review including:
        1. Render filled document pages
        2. Generate diffs against original (if provided)
        3. Detect issues (overflow, overlap, missing values)
        4. Store preview artifacts
        5. Calculate confidence updates

        Args:
            request: Review request with document refs and fields

        Returns:
            ReviewResult with issues, previews, and confidence updates
        """
        issues: list[Issue] = []
        previews: list[PreviewArtifact] = []
        confidence_updates: list[ConfidenceUpdate] = []

        # Step 1: Detect field-level issues (overflow, overlap, missing)
        field_issues = self._detect_field_issues(
            fields=request.fields,
            default_font_size=request.default_font_size,
        )
        issues.extend(field_issues)

        # Step 2: Render pages and generate previews
        rendered_pages = self._render_document(
            pdf_path=request.filled_document_ref,
            render_dpi=request.render_dpi,
        )

        # Step 3: Generate diffs if original document is provided
        diff_images: dict[int, bytes] = {}
        if request.original_document_ref:
            diff_images = self._generate_diffs(
                filled_ref=request.filled_document_ref,
                original_ref=request.original_document_ref,
                render_dpi=request.render_dpi,
            )

        # Step 4: Store preview artifacts
        for page_num, render_result in enumerate(rendered_pages, start=1):
            preview_ref = self._preview_storage.save_preview(
                document_id=request.document_id,
                page_number=page_num,
                image_data=render_result.image_data,
                artifact_type="preview",
            )

            diff_ref = None
            if page_num in diff_images:
                diff_ref = self._preview_storage.save_preview(
                    document_id=request.document_id,
                    page_number=page_num,
                    image_data=diff_images[page_num],
                    artifact_type="diff",
                )

            # Count fields on this page
            fields_on_page = [
                f for f in request.fields
                if f.page == page_num
            ]

            preview = PreviewArtifact(
                page=page_num,
                preview_ref=preview_ref,
                preview_url=self._preview_storage.get_url(preview_ref),
                diff_ref=diff_ref,
                diff_url=self._preview_storage.get_url(diff_ref) if diff_ref else None,
                width=render_result.width,
                height=render_result.height,
                field_count=len(fields_on_page),
            )
            previews.append(preview)

        # Step 5: Calculate confidence updates based on detected issues
        confidence_updates = self._calculate_confidence_updates(
            fields=request.fields,
            issues=issues,
        )

        return ReviewResult(
            document_id=request.document_id,
            success=True,
            issues=tuple(issues),
            preview_artifacts=tuple(previews),
            confidence_updates=tuple(confidence_updates),
            total_issues=len(issues),
            critical_issues=sum(
                1 for i in issues
                if i.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH)
            ),
        )

    def _detect_field_issues(
        self,
        fields: Sequence[FieldModel],
        default_font_size: float,
    ) -> list[Issue]:
        """Detect issues for each field.

        Checks for:
        - Text overflow (text exceeding bounding box)
        - Field overlap (bounding boxes intersecting)
        - Missing values (required fields without values)

        Args:
            fields: List of fields to check
            default_font_size: Default font size for overflow detection

        Returns:
            List of detected issues
        """
        issues: list[Issue] = []

        # Check each field for issues
        for field in fields:
            # Check for missing required values
            is_missing, message = detect_missing_value(
                value=field.value,
                is_required=field.is_required,
            )
            if is_missing:
                issue = Issue(
                    id=f"issue-{uuid4().hex[:8]}",
                    field_id=field.id,
                    issue_type=IssueType.MISSING_VALUE,
                    message=message,
                    severity=IssueSeverity.HIGH,
                    suggested_action="Provide a value for this required field",
                )
                issues.append(issue)

            # Check for text overflow
            if field.value and field.bbox:
                overflow_result = check_text_overflow(
                    text=field.value,
                    bbox=field.bbox,
                    font_size=default_font_size,
                )
                if overflow_result.has_overflow:
                    issue = Issue(
                        id=f"issue-{uuid4().hex[:8]}",
                        field_id=field.id,
                        issue_type=IssueType.LAYOUT_ISSUE,
                        message=f"Text overflows bounding box ({overflow_result.direction.value})",
                        severity=IssueSeverity.WARNING,
                        suggested_action="Reduce text length or font size",
                    )
                    issues.append(issue)

        # Check for overlapping fields (pairwise comparison)
        for i, field1 in enumerate(fields):
            if not field1.bbox:
                continue
            for field2 in fields[i + 1:]:
                if not field2.bbox:
                    continue

                overlap_result = check_boxes_overlap(
                    bbox1=field1.bbox,
                    bbox2=field2.bbox,
                )
                if overlap_result.has_overlap:
                    issue = Issue(
                        id=f"issue-{uuid4().hex[:8]}",
                        field_id=field1.id,
                        issue_type=IssueType.LAYOUT_ISSUE,
                        message=(
                            f"Field overlaps with '{field2.name}' "
                            f"({overlap_result.overlap_percentage:.0%} overlap)"
                        ),
                        severity=(
                            IssueSeverity.HIGH
                            if overlap_result.overlap_percentage > 0.5
                            else IssueSeverity.WARNING
                        ),
                        suggested_action="Adjust field positions to eliminate overlap",
                    )
                    issues.append(issue)

        return issues

    def _render_document(
        self,
        pdf_path: str,
        render_dpi: int,
    ) -> tuple:
        """Render all pages of a PDF document.

        Args:
            pdf_path: Path to the PDF file
            render_dpi: DPI for rendering

        Returns:
            Tuple of RenderResult for each page
        """
        return self._pdf_renderer.render_all_pages(
            pdf_path=pdf_path,
            dpi=render_dpi,
        )

    def _generate_diffs(
        self,
        filled_ref: str,
        original_ref: str,
        render_dpi: int,
    ) -> dict[int, bytes]:
        """Generate diff images between filled and original documents.

        Args:
            filled_ref: Path to filled PDF
            original_ref: Path to original PDF
            render_dpi: DPI for rendering

        Returns:
            Dictionary mapping page numbers to diff image bytes
        """
        diff_images: dict[int, bytes] = {}

        filled_pages = self._pdf_renderer.render_all_pages(
            pdf_path=filled_ref,
            dpi=render_dpi,
        )
        original_pages = self._pdf_renderer.render_all_pages(
            pdf_path=original_ref,
            dpi=render_dpi,
        )

        # Generate diff for each page
        for page_num, (filled, original) in enumerate(
            zip(filled_pages, original_pages),
            start=1,
        ):
            diff_result = self._diff_generator.generate_diff(
                original_image=original.image_data,
                filled_image=filled.image_data,
            )
            if diff_result.has_significant_changes:
                diff_images[page_num] = diff_result.diff_image

        return diff_images

    def _calculate_confidence_updates(
        self,
        fields: Sequence[FieldModel],
        issues: Sequence[Issue],
    ) -> list[ConfidenceUpdate]:
        """Calculate confidence updates based on detected issues.

        Args:
            fields: List of fields
            issues: List of detected issues

        Returns:
            List of confidence updates for affected fields
        """
        updates: list[ConfidenceUpdate] = []

        # Group issues by field
        issues_by_field: dict[str, list[Issue]] = {}
        for issue in issues:
            if issue.field_id not in issues_by_field:
                issues_by_field[issue.field_id] = []
            issues_by_field[issue.field_id].append(issue)

        # Calculate updates for fields with issues
        for field in fields:
            if field.id not in issues_by_field:
                continue

            field_issues = issues_by_field[field.id]
            has_overflow = any(
                i.issue_type == IssueType.LAYOUT_ISSUE and "overflow" in i.message.lower()
                for i in field_issues
            )
            has_overlap = any(
                i.issue_type == IssueType.LAYOUT_ISSUE and "overlap" in i.message.lower()
                for i in field_issues
            )

            original_confidence = field.confidence or 1.0
            new_confidence = calculate_confidence_update(
                original_confidence=original_confidence,
                has_overflow=has_overflow,
                has_overlap=has_overlap,
            )

            if new_confidence != original_confidence:
                update = ConfidenceUpdate(
                    field_id=field.id,
                    original_confidence=original_confidence,
                    updated_confidence=new_confidence,
                    reason=", ".join(i.message for i in field_issues),
                )
                updates.append(update)

        return updates

    async def render_page(
        self,
        document_ref: str,
        page_number: int,
        dpi: int = 150,
    ) -> bytes:
        """Render a single page from a document.

        Convenience method for rendering individual pages.

        Args:
            document_ref: Path to the PDF file
            page_number: 1-indexed page number
            dpi: Resolution for rendering

        Returns:
            PNG image bytes
        """
        result = self._pdf_renderer.render_page(
            pdf_path=document_ref,
            page_number=page_number,
            dpi=dpi,
        )
        return result.image_data

    async def generate_overlay(
        self,
        original_ref: str,
        filled_ref: str,
        page_number: int,
        dpi: int = 150,
        opacity: float = 0.5,
    ) -> bytes:
        """Generate an overlay of original and filled pages.

        Creates a composite image showing both original and
        filled content for visual comparison.

        Args:
            original_ref: Path to original PDF
            filled_ref: Path to filled PDF
            page_number: 1-indexed page number
            dpi: Resolution for rendering
            opacity: Opacity of the overlay (0.0 to 1.0)

        Returns:
            PNG image bytes of the overlay
        """
        original = self._pdf_renderer.render_page(
            pdf_path=original_ref,
            page_number=page_number,
            dpi=dpi,
        )
        filled = self._pdf_renderer.render_page(
            pdf_path=filled_ref,
            page_number=page_number,
            dpi=dpi,
        )

        return self._diff_generator.generate_overlay(
            base_image=original.image_data,
            overlay_image=filled.image_data,
            opacity=opacity,
        )
