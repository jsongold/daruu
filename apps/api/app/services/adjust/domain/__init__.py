"""Domain layer for the Adjust service.

Contains pure domain logic for bbox calculations and adjustment rules.
"""

from app.services.adjust.domain.models import (
    AdjustmentResult,
    BboxAdjustment,
    OverflowInfo,
    OverlapInfo,
)
from app.services.adjust.domain.rules import (
    calculate_bbox_adjustment_for_overflow,
    calculate_bbox_adjustment_for_overlap,
    calculate_overlap,
    check_bbox_within_bounds,
    compute_adjusted_bbox,
    merge_bbox_adjustments,
)

__all__ = [
    # Models
    "AdjustmentResult",
    "BboxAdjustment",
    "OverlapInfo",
    "OverflowInfo",
    # Rules
    "calculate_bbox_adjustment_for_overflow",
    "calculate_bbox_adjustment_for_overlap",
    "calculate_overlap",
    "check_bbox_within_bounds",
    "compute_adjusted_bbox",
    "merge_bbox_adjustments",
]
