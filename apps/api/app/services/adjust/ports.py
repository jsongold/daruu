"""Port interfaces for the Adjust service (Clean Architecture).

These protocols define the boundaries between the domain layer
and external adapters. Following dependency inversion principle,
the domain depends on abstractions, not concrete implementations.
"""

from typing import Protocol, Sequence

from app.services.adjust.domain.models import BboxValues, OverlapInfo, OverflowInfo


class BboxCalculatorPort(Protocol):
    """Port for bbox calculations and transformations.

    Implementations should handle:
    - Coordinate transformations (PDF to pixel, etc.)
    - Anchor-relative calculations
    - Scale/rotation adjustments

    Example implementations:
    - SimpleBboxCalculator: Basic arithmetic calculations
    - AnchorAwareBboxCalculator: Uses anchor points for relative positioning
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
        ...

    def calculate_relative_position(
        self,
        bbox: BboxValues,
        anchor_bbox: BboxValues,
    ) -> tuple[float, float]:
        """Calculate relative position from an anchor point.

        Args:
            bbox: The bounding box to calculate position for.
            anchor_bbox: The anchor/reference bounding box.

        Returns:
            Tuple of (relative_x, relative_y) offsets from anchor.
        """
        ...

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
        ...


class OverlapDetectorPort(Protocol):
    """Port for detecting overlaps between bounding boxes.

    Implementations may use different algorithms:
    - Simple pairwise comparison
    - R-tree spatial indexing for large sets
    - Shapely library for geometric operations

    Example implementations:
    - SimpleOverlapDetector: O(n^2) pairwise comparison
    - ShapelyOverlapDetector: Uses shapely for accurate geometry
    - RTreeOverlapDetector: Spatial indexing for efficiency
    """

    def detect_overlaps(
        self,
        bboxes: Sequence[tuple[str, BboxValues]],
        threshold: float = 0.0,
    ) -> tuple[OverlapInfo, ...]:
        """Detect all overlapping bbox pairs.

        Args:
            bboxes: Sequence of (field_id, bbox) tuples.
            threshold: Minimum overlap ratio to report (0.0 = any overlap).

        Returns:
            Tuple of OverlapInfo for each overlapping pair.
        """
        ...

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
        ...


class UserEditApplierPort(Protocol):
    """Port for applying user edits to fields.

    User edits take precedence over automatic adjustments.
    Implementations handle merging user preferences with
    system-generated patches.
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
        ...
