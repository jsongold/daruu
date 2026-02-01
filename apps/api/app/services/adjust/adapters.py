"""Adapter implementations for Adjust service ports.

These are the concrete implementations of the port interfaces.
Follows Clean Architecture pattern - adapters depend on ports.
"""

from typing import Sequence

from app.services.adjust.domain.models import BboxValues, OverflowInfo, OverlapInfo
from app.services.adjust.domain.rules import calculate_overlap, check_bbox_within_bounds
from app.services.adjust.ports import (
    BboxCalculatorPort,
    OverlapDetectorPort,
    UserEditApplierPort,
)


class SimpleOverlapDetector:
    """Simple O(n^2) overlap detector implementation.

    Implements OverlapDetectorPort for detecting overlaps using
    pairwise comparison. Suitable for small to medium field counts.

    For large documents with many fields, consider using
    ShapelyOverlapDetector or RTreeOverlapDetector instead.
    """

    def detect_overlaps(
        self,
        bboxes: Sequence[tuple[str, BboxValues]],
        threshold: float = 0.0,
    ) -> tuple[OverlapInfo, ...]:
        """Detect all overlapping bbox pairs.

        Performs O(n^2) pairwise comparison of all bboxes.

        Args:
            bboxes: Sequence of (field_id, bbox) tuples.
            threshold: Minimum overlap ratio to report.

        Returns:
            Tuple of OverlapInfo for each overlapping pair.
        """
        overlaps: list[OverlapInfo] = []
        bbox_list = list(bboxes)
        n = len(bbox_list)

        for i in range(n):
            field_id_a, bbox_a = bbox_list[i]
            for j in range(i + 1, n):
                field_id_b, bbox_b = bbox_list[j]

                overlap = calculate_overlap(
                    bbox_a=bbox_a,
                    bbox_b=bbox_b,
                    field_id_a=field_id_a,
                    field_id_b=field_id_b,
                )

                if overlap is not None:
                    # Check if overlap exceeds threshold
                    if overlap.overlap_ratio_a >= threshold or overlap.overlap_ratio_b >= threshold:
                        overlaps.append(overlap)

        return tuple(overlaps)

    def detect_overflow(
        self,
        field_id: str,
        bbox: BboxValues,
        page_width: float,
        page_height: float,
    ) -> OverflowInfo:
        """Detect if a bbox overflows page boundaries.

        Args:
            field_id: ID of the field.
            bbox: The bounding box to check.
            page_width: Width of the page.
            page_height: Height of the page.

        Returns:
            OverflowInfo with overflow amounts.
        """
        base_overflow = check_bbox_within_bounds(bbox, page_width, page_height)

        # Create new OverflowInfo with field_id set
        return OverflowInfo(
            field_id=field_id,
            overflow_left=base_overflow.overflow_left,
            overflow_right=base_overflow.overflow_right,
            overflow_top=base_overflow.overflow_top,
            overflow_bottom=base_overflow.overflow_bottom,
        )


# Ensure SimpleOverlapDetector satisfies OverlapDetectorPort
_overlap_detector_check: OverlapDetectorPort = SimpleOverlapDetector()


class SimpleBboxCalculator:
    """Simple bbox calculator implementation.

    Implements BboxCalculatorPort for basic coordinate transformations
    and relative positioning calculations.
    """

    def transform_to_page_coords(
        self,
        bbox: BboxValues,
        source_dpi: int,
        target_dpi: int,
    ) -> BboxValues:
        """Transform bbox coordinates between DPI spaces.

        Args:
            bbox: Bounding box in source coordinates.
            source_dpi: DPI of source coordinate system.
            target_dpi: DPI of target coordinate system.

        Returns:
            Transformed BboxValues in target coordinates.
        """
        if source_dpi == target_dpi:
            return bbox

        scale = target_dpi / source_dpi

        return BboxValues(
            x=bbox.x * scale,
            y=bbox.y * scale,
            width=bbox.width * scale,
            height=bbox.height * scale,
            page=bbox.page,
        )

    def calculate_relative_position(
        self,
        bbox: BboxValues,
        anchor_bbox: BboxValues,
    ) -> tuple[float, float]:
        """Calculate relative position from an anchor point.

        Uses top-left corner of anchor as reference.

        Args:
            bbox: The bounding box to calculate position for.
            anchor_bbox: The anchor/reference bounding box.

        Returns:
            Tuple of (relative_x, relative_y) offsets from anchor.
        """
        relative_x = bbox.x - anchor_bbox.x
        relative_y = bbox.y - anchor_bbox.y
        return (relative_x, relative_y)

    def apply_relative_position(
        self,
        relative_x: float,
        relative_y: float,
        anchor_bbox: BboxValues,
        original_width: float,
        original_height: float,
    ) -> BboxValues:
        """Create bbox at relative position from anchor.

        Args:
            relative_x: X offset from anchor.
            relative_y: Y offset from anchor.
            anchor_bbox: The anchor/reference bounding box.
            original_width: Width of the bbox to create.
            original_height: Height of the bbox to create.

        Returns:
            New BboxValues positioned relative to anchor.
        """
        return BboxValues(
            x=anchor_bbox.x + relative_x,
            y=anchor_bbox.y + relative_y,
            width=original_width,
            height=original_height,
            page=anchor_bbox.page,
        )


# Ensure SimpleBboxCalculator satisfies BboxCalculatorPort
_bbox_calculator_check: BboxCalculatorPort = SimpleBboxCalculator()


class SimpleUserEditApplier:
    """Simple user edit applier implementation.

    Implements UserEditApplierPort for merging user edits
    with system-calculated values.
    """

    def apply_user_edits(
        self,
        field_id: str,
        current_bbox: BboxValues | None,
        user_bbox: BboxValues | None,
        user_render_params: dict[str, str | int | float | bool] | None,
    ) -> tuple[BboxValues | None, dict[str, str | int | float | bool] | None]:
        """Apply user edits to a field's bbox and render params.

        User edits override automatic calculations.

        Args:
            field_id: ID of the field being edited.
            current_bbox: Current/calculated bbox (may be None).
            user_bbox: User-specified bbox (may be None).
            user_render_params: User-specified render params (may be None).

        Returns:
            Tuple of (final_bbox, final_render_params).
        """
        # User bbox takes precedence if provided
        final_bbox = user_bbox if user_bbox is not None else current_bbox

        # User render params are returned as-is if provided
        final_render_params = user_render_params

        return (final_bbox, final_render_params)


# Ensure SimpleUserEditApplier satisfies UserEditApplierPort
_user_edit_applier_check: UserEditApplierPort = SimpleUserEditApplier()


class ShapelyOverlapDetector:
    """Shapely-based overlap detector (stub).

    Uses shapely library for accurate geometric operations.
    This is a stub implementation for future enhancement.

    Production implementation will:
    - Use shapely.geometry.box for bbox creation
    - Use shapely intersection for overlap calculation
    - Provide more accurate area calculations for rotated boxes
    """

    def detect_overlaps(
        self,
        bboxes: Sequence[tuple[str, BboxValues]],
        threshold: float = 0.0,
    ) -> tuple[OverlapInfo, ...]:
        """Detect all overlapping bbox pairs using shapely.

        Args:
            bboxes: Sequence of (field_id, bbox) tuples.
            threshold: Minimum overlap ratio to report.

        Returns:
            Tuple of OverlapInfo for each overlapping pair.

        Raises:
            NotImplementedError: Shapely implementation pending.
        """
        # TODO: Implement with shapely when needed
        # For now, fall back to simple detector
        simple = SimpleOverlapDetector()
        return simple.detect_overlaps(bboxes, threshold)

    def detect_overflow(
        self,
        field_id: str,
        bbox: BboxValues,
        page_width: float,
        page_height: float,
    ) -> OverflowInfo:
        """Detect if a bbox overflows page boundaries.

        Args:
            field_id: ID of the field.
            bbox: The bounding box to check.
            page_width: Width of the page.
            page_height: Height of the page.

        Returns:
            OverflowInfo with overflow amounts.
        """
        # Shapely not needed for simple overflow check
        simple = SimpleOverlapDetector()
        return simple.detect_overflow(field_id, bbox, page_width, page_height)
