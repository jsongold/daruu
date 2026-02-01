"""Adjust service for bbox and render parameter corrections.

This is a deterministic Service (no Agent) that:
1. Analyzes fields and issues to determine necessary adjustments
2. Calculates bbox corrections for overflow/overlap
3. Generates patches for orchestrator to apply or review
4. Returns deterministic results (same input -> same output)

Service vs Agent:
- This is a Service (deterministic, no LLM reasoning)
- Uses pure computational rules for adjustments
"""

from app.models.adjust import (
    AdjustError,
    AdjustErrorCode,
    AdjustRequest,
    AdjustResult,
    ConfidenceUpdate,
    FieldPatch,
    PatchType,
    RenderParams,
)
from app.models.common import BBox
from app.models.field import FieldEdit, FieldModel
from app.models.job import Issue, IssueType
from app.services.adjust.domain.models import BboxAdjustment, BboxValues
from app.services.adjust.domain.rules import (
    bbox_from_dict,
    calculate_adjustment_confidence_impact,
    calculate_bbox_adjustment_for_overflow,
    calculate_bbox_adjustment_for_overlap,
    calculate_overlap,
    check_bbox_within_bounds,
    compute_adjusted_bbox,
)
from app.services.adjust.ports import OverlapDetectorPort


class AdjustService:
    """Application service for field bbox adjustments.

    Coordinates the analysis of issues and generation of patches
    using injected adapters for overlap detection.

    Example usage:
        detector = SimpleOverlapDetector()
        service = AdjustService(detector)

        request = AdjustRequest(
            fields=(...),
            issues=(...),
            page_meta=(...),
        )
        result = await service.adjust(request)
    """

    def __init__(
        self,
        overlap_detector: OverlapDetectorPort,
    ) -> None:
        """Initialize the adjust service with adapters.

        Args:
            overlap_detector: Adapter for detecting overlaps.
        """
        self._overlap_detector = overlap_detector

    async def adjust(self, request: AdjustRequest) -> AdjustResult:
        """Perform field bbox adjustments.

        Analyzes issues and generates patches to resolve them.
        Patches are proposals - the orchestrator decides whether to apply.

        Args:
            request: Adjust request with fields, issues, and page metadata.

        Returns:
            AdjustResult with patches and confidence updates.
        """
        # Validate request
        if not request.fields:
            return AdjustResult(
                success=False,
                errors=(
                    AdjustError(
                        code=AdjustErrorCode.NO_FIELDS,
                        message="No fields provided for adjustment",
                    ),
                ),
            )

        # Build page metadata lookup
        page_meta_map = {pm.page_number: pm for pm in request.page_meta}

        # Build field lookup
        field_map = {f.id: f for f in request.fields}

        # Apply user edits first (they take precedence)
        user_edit_map = {ue.field_id: ue for ue in request.user_edits}

        # Process issues and generate patches
        patches: list[FieldPatch] = []
        confidence_updates: list[ConfidenceUpdate] = []
        resolved_issue_ids: list[str] = []
        errors: list[AdjustError] = []

        # Group issues by type for systematic processing
        layout_issues = [
            i for i in request.issues
            if i.issue_type == IssueType.LAYOUT_ISSUE
        ]

        # Process layout issues (overflow, overlap)
        for issue in layout_issues:
            field = field_map.get(issue.field_id)
            if field is None or field.bbox is None:
                continue

            # Check for user edit override
            user_edit = user_edit_map.get(issue.field_id)
            if user_edit and user_edit.bbox:
                # User edit takes precedence
                patch = self._create_user_edit_patch(field, user_edit, issue)
                patches.append(patch)
                resolved_issue_ids.append(issue.id)
                continue

            # Get page metadata
            page_meta = page_meta_map.get(field.bbox.page)
            if page_meta is None:
                errors.append(
                    AdjustError(
                        code=AdjustErrorCode.INVALID_BBOX,
                        message=f"No page metadata for page {field.bbox.page}",
                        field_id=field.id,
                    )
                )
                continue

            # Calculate adjustment
            patch_result = self._calculate_layout_adjustment(
                field=field,
                issue=issue,
                page_width=page_meta.width,
                page_height=page_meta.height,
                all_fields=request.fields,
                overlap_threshold=request.overlap_threshold,
            )

            if patch_result is not None:
                patches.append(patch_result)
                resolved_issue_ids.append(issue.id)

                # Track confidence change
                if patch_result.confidence_delta is not None:
                    original_conf = field.confidence or 0.5
                    new_conf = max(0.0, min(1.0, original_conf + patch_result.confidence_delta))
                    if new_conf != original_conf:
                        confidence_updates.append(
                            ConfidenceUpdate(
                                field_id=field.id,
                                original_confidence=original_conf,
                                updated_confidence=new_conf,
                                reason=patch_result.reason,
                            )
                        )

        # Process fields without explicit issues but with potential problems
        # (proactive overlap/overflow detection)
        processed_field_ids = {p.field_id for p in patches}
        for field in request.fields:
            if field.id in processed_field_ids:
                continue
            if field.bbox is None:
                continue

            # Check for user edit
            user_edit = user_edit_map.get(field.id)
            if user_edit and user_edit.bbox:
                patch = self._create_user_edit_patch(field, user_edit, issue=None)
                patches.append(patch)
                continue

            # Check for overflow
            page_meta = page_meta_map.get(field.bbox.page)
            if page_meta is None:
                continue

            overflow_patch = self._check_and_fix_overflow(
                field=field,
                page_width=page_meta.width,
                page_height=page_meta.height,
            )
            if overflow_patch is not None:
                patches.append(overflow_patch)

        # Calculate remaining issues
        remaining_count = len(request.issues) - len(resolved_issue_ids)

        return AdjustResult(
            success=len(errors) == 0,
            field_patches=tuple(patches),
            confidence_updates=tuple(confidence_updates),
            resolved_issue_ids=tuple(resolved_issue_ids),
            remaining_issue_count=max(0, remaining_count),
            iterations_used=1,
            errors=tuple(errors),
        )

    def _create_user_edit_patch(
        self,
        field: FieldModel,
        user_edit: FieldEdit,
        issue: Issue | None,
    ) -> FieldPatch:
        """Create a patch from user edit.

        User edits take precedence over automatic calculations.
        """
        render_params = None
        if user_edit.render_params:
            render_params = RenderParams(
                font_size=user_edit.render_params.get("font_size"),  # type: ignore[arg-type]
                line_height=user_edit.render_params.get("line_height"),  # type: ignore[arg-type]
                wrap=user_edit.render_params.get("wrap"),  # type: ignore[arg-type]
                max_lines=user_edit.render_params.get("max_lines"),  # type: ignore[arg-type]
                alignment=user_edit.render_params.get("alignment"),  # type: ignore[arg-type]
                overflow_mode=user_edit.render_params.get("overflow_mode"),  # type: ignore[arg-type]
            )

        adjusted_bbox = None
        if user_edit.bbox:
            adjusted_bbox = user_edit.bbox

        patch_type = PatchType.COMBINED
        if user_edit.bbox and not render_params:
            patch_type = PatchType.BBOX_FULL
        elif render_params and not user_edit.bbox:
            patch_type = PatchType.RENDER_PARAMS

        return FieldPatch(
            field_id=field.id,
            patch_type=patch_type,
            original_bbox=field.bbox,
            adjusted_bbox=adjusted_bbox,
            render_params=render_params,
            reason="User edit applied",
            issue_id=issue.id if issue else None,
            confidence_delta=0.1,  # User edits boost confidence
        )

    def _calculate_layout_adjustment(
        self,
        field: FieldModel,
        issue: Issue,
        page_width: float,
        page_height: float,
        all_fields: tuple[FieldModel, ...],
        overlap_threshold: float,
    ) -> FieldPatch | None:
        """Calculate bbox adjustment for a layout issue.

        Determines if issue is overflow or overlap and calculates fix.
        """
        if field.bbox is None:
            return None

        bbox = self._to_bbox_values(field.bbox)

        # Check for overflow first
        overflow = check_bbox_within_bounds(bbox, page_width, page_height)
        if overflow.has_overflow:
            adjustment = calculate_bbox_adjustment_for_overflow(
                bbox=bbox,
                overflow=overflow,
                preserve_size=True,
            )
            if not adjustment.is_identity:
                new_bbox = compute_adjusted_bbox(bbox, adjustment)
                confidence_impact = calculate_adjustment_confidence_impact(
                    adjustment, bbox
                )

                return FieldPatch(
                    field_id=field.id,
                    patch_type=PatchType.BBOX_MOVE,
                    original_bbox=field.bbox,
                    adjusted_bbox=self._to_bbox_model(new_bbox),
                    reason=adjustment.reason,
                    issue_id=issue.id,
                    confidence_delta=confidence_impact + 0.02,  # Bonus for fixing issue
                )

        # Check for overlap with other fields
        overlap_patch = self._find_and_fix_overlap(
            field=field,
            all_fields=all_fields,
            page_width=page_width,
            page_height=page_height,
            overlap_threshold=overlap_threshold,
            issue_id=issue.id,
        )
        if overlap_patch is not None:
            return overlap_patch

        return None

    def _find_and_fix_overlap(
        self,
        field: FieldModel,
        all_fields: tuple[FieldModel, ...],
        page_width: float,
        page_height: float,
        overlap_threshold: float,
        issue_id: str | None = None,
    ) -> FieldPatch | None:
        """Find overlapping fields and calculate fix."""
        if field.bbox is None:
            return None

        bbox = self._to_bbox_values(field.bbox)

        # Find overlaps with other fields
        for other_field in all_fields:
            if other_field.id == field.id:
                continue
            if other_field.bbox is None:
                continue
            if other_field.bbox.page != field.bbox.page:
                continue

            other_bbox = self._to_bbox_values(other_field.bbox)
            overlap = calculate_overlap(
                bbox_a=bbox,
                bbox_b=other_bbox,
                field_id_a=field.id,
                field_id_b=other_field.id,
            )

            if overlap is None:
                continue

            # Check if overlap exceeds threshold
            if overlap.overlap_ratio_a < overlap_threshold:
                continue

            # Calculate adjustment to resolve overlap
            adjustment = calculate_bbox_adjustment_for_overlap(
                bbox_to_move=bbox,
                bbox_stationary=other_bbox,
                overlap=overlap,
                page_width=page_width,
                page_height=page_height,
            )

            if not adjustment.is_identity:
                new_bbox = compute_adjusted_bbox(bbox, adjustment)
                confidence_impact = calculate_adjustment_confidence_impact(
                    adjustment, bbox
                )

                return FieldPatch(
                    field_id=field.id,
                    patch_type=PatchType.BBOX_MOVE,
                    original_bbox=field.bbox,
                    adjusted_bbox=self._to_bbox_model(new_bbox),
                    reason=f"Overlap with field {other_field.id}: {adjustment.reason}",
                    issue_id=issue_id,
                    confidence_delta=confidence_impact + 0.02,
                )

        return None

    def _check_and_fix_overflow(
        self,
        field: FieldModel,
        page_width: float,
        page_height: float,
    ) -> FieldPatch | None:
        """Proactively check and fix overflow for a field."""
        if field.bbox is None:
            return None

        bbox = self._to_bbox_values(field.bbox)
        overflow = check_bbox_within_bounds(bbox, page_width, page_height)

        if not overflow.has_overflow:
            return None

        adjustment = calculate_bbox_adjustment_for_overflow(
            bbox=bbox,
            overflow=overflow,
            preserve_size=True,
        )

        if adjustment.is_identity:
            return None

        new_bbox = compute_adjusted_bbox(bbox, adjustment)
        confidence_impact = calculate_adjustment_confidence_impact(adjustment, bbox)

        return FieldPatch(
            field_id=field.id,
            patch_type=PatchType.BBOX_MOVE,
            original_bbox=field.bbox,
            adjusted_bbox=self._to_bbox_model(new_bbox),
            reason=f"Proactive overflow fix: {adjustment.reason}",
            issue_id=None,
            confidence_delta=confidence_impact,
        )

    def _to_bbox_values(self, bbox: BBox) -> BboxValues:
        """Convert BBox model to BboxValues domain object."""
        return bbox_from_dict(
            x=bbox.x,
            y=bbox.y,
            width=bbox.width,
            height=bbox.height,
            page=bbox.page,
        )

    def _to_bbox_model(self, bbox: BboxValues) -> BBox:
        """Convert BboxValues domain object to BBox model."""
        return BBox(
            x=bbox.x,
            y=bbox.y,
            width=bbox.width,
            height=bbox.height,
            page=bbox.page,
        )
