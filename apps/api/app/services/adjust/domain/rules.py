"""Pure domain logic for bbox calculations and adjustment rules.

This module contains deterministic, pure functions for:
- Overflow detection and correction
- Overlap detection and resolution
- Bbox adjustment calculations

These functions have no external dependencies and are easy to test.
All functions follow immutability principles - they return new objects
rather than modifying inputs.
"""

from app.services.adjust.domain.models import (
    AdjustmentDirection,
    AdjustmentResult,
    BboxAdjustment,
    BboxValues,
    OverflowInfo,
    OverlapInfo,
)


def bbox_from_dict(
    x: float,
    y: float,
    width: float,
    height: float,
    page: int,
) -> BboxValues:
    """Create a BboxValues from individual values.

    Args:
        x: X coordinate (left edge).
        y: Y coordinate (top edge).
        width: Width of bbox.
        height: Height of bbox.
        page: Page number.

    Returns:
        Immutable BboxValues instance.
    """
    return BboxValues(x=x, y=y, width=width, height=height, page=page)


def check_bbox_within_bounds(
    bbox: BboxValues,
    page_width: float,
    page_height: float,
) -> OverflowInfo:
    """Check if a bbox overflows beyond page boundaries.

    Calculates how much (if any) the bbox extends past each edge.

    Args:
        bbox: The bounding box to check.
        page_width: Width of the page in points.
        page_height: Height of the page in points.

    Returns:
        OverflowInfo with overflow amounts for each edge.
    """
    overflow_left = max(0.0, -bbox.x)
    overflow_top = max(0.0, -bbox.y)
    overflow_right = max(0.0, bbox.right - page_width)
    overflow_bottom = max(0.0, bbox.bottom - page_height)

    return OverflowInfo(
        field_id="",  # Caller should set this
        overflow_left=overflow_left,
        overflow_right=overflow_right,
        overflow_top=overflow_top,
        overflow_bottom=overflow_bottom,
    )


def calculate_overlap(
    bbox_a: BboxValues,
    bbox_b: BboxValues,
    field_id_a: str = "",
    field_id_b: str = "",
) -> OverlapInfo | None:
    """Calculate overlap between two bounding boxes.

    Returns None if bboxes do not overlap or are on different pages.

    Args:
        bbox_a: First bounding box.
        bbox_b: Second bounding box.
        field_id_a: ID of field A (for result).
        field_id_b: ID of field B (for result).

    Returns:
        OverlapInfo if overlapping, None otherwise.
    """
    # Must be on same page
    if bbox_a.page != bbox_b.page:
        return None

    # Calculate intersection
    intersect_left = max(bbox_a.x, bbox_b.x)
    intersect_top = max(bbox_a.y, bbox_b.y)
    intersect_right = min(bbox_a.right, bbox_b.right)
    intersect_bottom = min(bbox_a.bottom, bbox_b.bottom)

    # Check if there is actual overlap
    intersect_width = intersect_right - intersect_left
    intersect_height = intersect_bottom - intersect_top

    if intersect_width <= 0 or intersect_height <= 0:
        return None

    overlap_area = intersect_width * intersect_height
    area_a = bbox_a.area
    area_b = bbox_b.area

    # Calculate overlap ratios (avoid division by zero)
    ratio_a = overlap_area / area_a if area_a > 0 else 0.0
    ratio_b = overlap_area / area_b if area_b > 0 else 0.0

    intersection_bbox = BboxValues(
        x=intersect_left,
        y=intersect_top,
        width=intersect_width,
        height=intersect_height,
        page=bbox_a.page,
    )

    return OverlapInfo(
        field_id_a=field_id_a,
        field_id_b=field_id_b,
        overlap_area=overlap_area,
        overlap_ratio_a=ratio_a,
        overlap_ratio_b=ratio_b,
        intersection_bbox=intersection_bbox,
    )


def calculate_bbox_adjustment_for_overflow(
    bbox: BboxValues,
    overflow: OverflowInfo,
    preserve_size: bool = True,
) -> BboxAdjustment:
    """Calculate bbox adjustment to fix overflow.

    Determines how to move/resize a bbox to fit within page bounds.

    Args:
        bbox: The bounding box to adjust.
        overflow: The overflow information.
        preserve_size: If True, prefer moving over resizing.

    Returns:
        BboxAdjustment to apply.
    """
    if not overflow.has_overflow:
        return BboxAdjustment(reason="No overflow to correct")

    delta_x = 0.0
    delta_y = 0.0
    delta_width = 0.0
    delta_height = 0.0
    direction = None
    reasons = []

    if preserve_size:
        # Try to move the bbox to fit
        if overflow.overflow_left > 0:
            delta_x = overflow.overflow_left
            direction = AdjustmentDirection.MOVE_RIGHT
            reasons.append(f"Move right by {overflow.overflow_left:.1f} to fix left overflow")
        elif overflow.overflow_right > 0:
            delta_x = -overflow.overflow_right
            direction = AdjustmentDirection.MOVE_LEFT
            reasons.append(f"Move left by {overflow.overflow_right:.1f} to fix right overflow")

        if overflow.overflow_top > 0:
            delta_y = overflow.overflow_top
            direction = AdjustmentDirection.MOVE_DOWN
            reasons.append(f"Move down by {overflow.overflow_top:.1f} to fix top overflow")
        elif overflow.overflow_bottom > 0:
            delta_y = -overflow.overflow_bottom
            direction = AdjustmentDirection.MOVE_UP
            reasons.append(f"Move up by {overflow.overflow_bottom:.1f} to fix bottom overflow")
    else:
        # Shrink the bbox to fit
        if overflow.overflow_left > 0:
            delta_x = overflow.overflow_left
            delta_width = -overflow.overflow_left
            direction = AdjustmentDirection.SHRINK_WIDTH
            reasons.append(f"Shrink from left by {overflow.overflow_left:.1f}")
        elif overflow.overflow_right > 0:
            delta_width = -overflow.overflow_right
            direction = AdjustmentDirection.SHRINK_WIDTH
            reasons.append(f"Shrink width by {overflow.overflow_right:.1f}")

        if overflow.overflow_top > 0:
            delta_y = overflow.overflow_top
            delta_height = -overflow.overflow_top
            direction = AdjustmentDirection.SHRINK_HEIGHT
            reasons.append(f"Shrink from top by {overflow.overflow_top:.1f}")
        elif overflow.overflow_bottom > 0:
            delta_height = -overflow.overflow_bottom
            direction = AdjustmentDirection.SHRINK_HEIGHT
            reasons.append(f"Shrink height by {overflow.overflow_bottom:.1f}")

    return BboxAdjustment(
        delta_x=delta_x,
        delta_y=delta_y,
        delta_width=delta_width,
        delta_height=delta_height,
        direction=direction,
        reason="; ".join(reasons) if reasons else "No adjustment needed",
    )


def calculate_bbox_adjustment_for_overlap(
    bbox_to_move: BboxValues,
    bbox_stationary: BboxValues,
    overlap: OverlapInfo,
    page_width: float,
    page_height: float,
) -> BboxAdjustment:
    """Calculate adjustment to resolve overlap between two bboxes.

    Determines the smallest move to separate the two boxes.
    Prefers the direction with more available space.

    Args:
        bbox_to_move: The bbox that will be adjusted.
        bbox_stationary: The bbox that stays in place.
        overlap: Information about the overlap.
        page_width: Page width for boundary checking.
        page_height: Page height for boundary checking.

    Returns:
        BboxAdjustment to resolve the overlap.
    """
    if overlap.intersection_bbox is None:
        return BboxAdjustment(reason="No overlap to resolve")

    # Calculate separation distances for each direction
    # Moving bbox_to_move to avoid bbox_stationary
    move_left = bbox_to_move.right - bbox_stationary.x
    move_right = bbox_stationary.right - bbox_to_move.x
    move_up = bbox_to_move.bottom - bbox_stationary.y
    move_down = bbox_stationary.bottom - bbox_to_move.y

    # Calculate available space in each direction
    space_left = bbox_to_move.x
    space_right = page_width - bbox_to_move.right
    space_up = bbox_to_move.y
    space_down = page_height - bbox_to_move.bottom

    # Find the best direction (smallest move that fits within page)
    candidates = []

    if space_left >= move_left and move_left > 0:
        candidates.append(("left", move_left, -move_left, 0.0))
    if space_right >= move_right and move_right > 0:
        candidates.append(("right", move_right, move_right, 0.0))
    if space_up >= move_up and move_up > 0:
        candidates.append(("up", move_up, 0.0, -move_up))
    if space_down >= move_down and move_down > 0:
        candidates.append(("down", move_down, 0.0, move_down))

    if not candidates:
        # No single direction works; try diagonal or shrink
        # For now, return a partial move in the best direction
        min_move = min(move_left, move_right, move_up, move_down)
        if min_move == move_left:
            return BboxAdjustment(
                delta_x=-min(move_left, space_left),
                reason=f"Partial move left by {min(move_left, space_left):.1f}",
                direction=AdjustmentDirection.MOVE_LEFT,
            )
        elif min_move == move_right:
            return BboxAdjustment(
                delta_x=min(move_right, space_right),
                reason=f"Partial move right by {min(move_right, space_right):.1f}",
                direction=AdjustmentDirection.MOVE_RIGHT,
            )
        elif min_move == move_up:
            return BboxAdjustment(
                delta_y=-min(move_up, space_up),
                reason=f"Partial move up by {min(move_up, space_up):.1f}",
                direction=AdjustmentDirection.MOVE_UP,
            )
        else:
            return BboxAdjustment(
                delta_y=min(move_down, space_down),
                reason=f"Partial move down by {min(move_down, space_down):.1f}",
                direction=AdjustmentDirection.MOVE_DOWN,
            )

    # Choose the smallest move
    best = min(candidates, key=lambda c: c[1])
    direction_name, _, delta_x, delta_y = best

    direction_map = {
        "left": AdjustmentDirection.MOVE_LEFT,
        "right": AdjustmentDirection.MOVE_RIGHT,
        "up": AdjustmentDirection.MOVE_UP,
        "down": AdjustmentDirection.MOVE_DOWN,
    }

    return BboxAdjustment(
        delta_x=delta_x,
        delta_y=delta_y,
        direction=direction_map[direction_name],
        reason=f"Move {direction_name} by {abs(delta_x or delta_y):.1f} to resolve overlap",
    )


def compute_adjusted_bbox(
    bbox: BboxValues,
    adjustment: BboxAdjustment,
) -> BboxValues:
    """Apply an adjustment to create a new bbox.

    Does NOT modify the original bbox; returns a new one.

    Args:
        bbox: Original bounding box.
        adjustment: Adjustment to apply.

    Returns:
        New BboxValues with adjustment applied.
    """
    new_width = max(0.0, bbox.width + adjustment.delta_width)
    new_height = max(0.0, bbox.height + adjustment.delta_height)

    return BboxValues(
        x=bbox.x + adjustment.delta_x,
        y=bbox.y + adjustment.delta_y,
        width=new_width,
        height=new_height,
        page=bbox.page,
    )


def merge_bbox_adjustments(
    adjustments: tuple[BboxAdjustment, ...],
) -> BboxAdjustment:
    """Merge multiple adjustments into a single adjustment.

    Combines deltas and concatenates reasons.

    Args:
        adjustments: Tuple of adjustments to merge.

    Returns:
        Single merged BboxAdjustment.
    """
    if not adjustments:
        return BboxAdjustment(reason="No adjustments to merge")

    total_delta_x = sum(adj.delta_x for adj in adjustments)
    total_delta_y = sum(adj.delta_y for adj in adjustments)
    total_delta_width = sum(adj.delta_width for adj in adjustments)
    total_delta_height = sum(adj.delta_height for adj in adjustments)

    reasons = [adj.reason for adj in adjustments if adj.reason]
    combined_reason = "; ".join(reasons) if reasons else "Merged adjustments"

    # Direction is ambiguous when merging, set to None
    return BboxAdjustment(
        delta_x=total_delta_x,
        delta_y=total_delta_y,
        delta_width=total_delta_width,
        delta_height=total_delta_height,
        direction=None,
        reason=combined_reason,
    )


def calculate_adjustment_confidence_impact(
    adjustment: BboxAdjustment,
    original_bbox: BboxValues,
) -> float:
    """Calculate the confidence impact of an adjustment.

    Larger adjustments have more negative impact on confidence.
    Small adjustments have minimal impact.

    Args:
        adjustment: The adjustment being applied.
        original_bbox: The original bbox before adjustment.

    Returns:
        Confidence delta (negative for large changes, near zero for small).
    """
    if adjustment.is_identity:
        return 0.0

    # Calculate relative change magnitude
    position_change = abs(adjustment.delta_x) + abs(adjustment.delta_y)
    size_change = abs(adjustment.delta_width) + abs(adjustment.delta_height)

    # Normalize by original bbox size
    original_size = max(original_bbox.width, original_bbox.height, 1.0)
    relative_position_change = position_change / original_size
    relative_size_change = size_change / original_size

    # Confidence impact: small changes have minimal impact
    # Large changes (> 50% of original size) have significant impact
    total_relative_change = relative_position_change + relative_size_change

    if total_relative_change < 0.1:
        # Very small adjustment, no confidence impact
        return 0.0
    elif total_relative_change < 0.25:
        # Small adjustment, slight positive impact (fixing an issue)
        return 0.02
    elif total_relative_change < 0.5:
        # Moderate adjustment, neutral
        return 0.0
    else:
        # Large adjustment, negative impact
        return -0.05 * min(total_relative_change, 2.0)


def create_adjustment_result(
    field_id: str,
    adjustment: BboxAdjustment,
    original_bbox: BboxValues,
    resolved_issue: bool = False,
) -> AdjustmentResult:
    """Create an AdjustmentResult with calculated confidence impact.

    Args:
        field_id: ID of the field being adjusted.
        adjustment: The adjustment to apply.
        original_bbox: Original bbox for confidence calculation.
        resolved_issue: Whether this adjustment resolves an issue.

    Returns:
        Complete AdjustmentResult.
    """
    confidence_impact = calculate_adjustment_confidence_impact(adjustment, original_bbox)

    # Resolving an issue gives a confidence boost
    if resolved_issue and confidence_impact <= 0:
        confidence_impact = max(confidence_impact + 0.05, 0.02)

    return AdjustmentResult(
        field_id=field_id,
        adjustment=adjustment,
        success=True,
        issue_resolved=resolved_issue,
        new_issues_created=False,
        confidence_impact=confidence_impact,
    )
