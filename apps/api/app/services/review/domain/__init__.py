"""Domain layer for the Review service.

This module contains:
- Domain models (immutable value objects)
- Issue detection rules (pure functions)
"""

from app.services.review.domain.models import (
    ChangeRegion,
    DiffResult,
    OverflowCheckResult,
    OverlapCheckResult,
    RenderResult,
)
from app.services.review.domain.rules import (
    calculate_text_bounds,
    check_boxes_overlap,
    check_text_overflow,
    detect_missing_value,
)

__all__ = [
    # Models
    "ChangeRegion",
    "DiffResult",
    "OverflowCheckResult",
    "OverlapCheckResult",
    "RenderResult",
    # Rules
    "calculate_text_bounds",
    "check_boxes_overlap",
    "check_text_overflow",
    "detect_missing_value",
]
