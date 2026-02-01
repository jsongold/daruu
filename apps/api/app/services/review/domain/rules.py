"""Domain rules for issue detection in the Review service.

This module contains pure domain logic for:
- Text overflow detection (text exceeding bounding box)
- Bounding box overlap detection
- Missing value detection
- Text bounds estimation

These functions are pure and have no external dependencies,
making them easy to test and reason about.
"""

from app.models.common import BBox
from app.services.review.domain.models import (
    OverflowCheckResult,
    OverflowDirection,
    OverlapCheckResult,
    OverlapType,
    TextBounds,
)


# Font metrics constants (approximate for standard fonts)
# These are used for text bounds estimation when visual detection is not available
AVERAGE_CHAR_WIDTH_RATIO = 0.5  # Average character width as ratio of font size
LINE_HEIGHT_RATIO = 1.2  # Line height as ratio of font size


def calculate_text_bounds(
    text: str,
    font_size: float,
    char_width_ratio: float = AVERAGE_CHAR_WIDTH_RATIO,
    line_height_ratio: float = LINE_HEIGHT_RATIO,
) -> TextBounds:
    """Calculate estimated bounds for rendered text.

    This provides a geometric approximation of text dimensions.
    For more accurate results, use the IssueDetectorPort with
    actual rendered images.

    Args:
        text: The text content to measure
        font_size: Font size in points
        char_width_ratio: Character width as ratio of font size
        line_height_ratio: Line height as ratio of font size

    Returns:
        TextBounds with estimated width, height, and baseline offset
    """
    if not text:
        return TextBounds(width=0.0, height=0.0, baseline_offset=0.0)

    lines = text.split("\n")
    max_line_length = max(len(line) for line in lines)
    num_lines = len(lines)

    # Estimate width based on longest line
    char_width = font_size * char_width_ratio
    estimated_width = max_line_length * char_width

    # Estimate height based on number of lines
    line_height = font_size * line_height_ratio
    estimated_height = num_lines * line_height

    # Baseline is typically about 80% down from the top of the text
    baseline_offset = font_size * 0.8

    return TextBounds(
        width=estimated_width,
        height=estimated_height,
        baseline_offset=baseline_offset,
    )


def check_text_overflow(
    text: str,
    bbox: BBox,
    font_size: float,
    padding: float = 2.0,
) -> OverflowCheckResult:
    """Check if text will overflow its bounding box.

    Uses geometric estimation to determine if text exceeds
    the available space. For visual confirmation, use the
    IssueDetectorPort with rendered images.

    Args:
        text: The text content to check
        bbox: The bounding box constraint
        font_size: Font size in points
        padding: Internal padding in pixels (default 2.0)

    Returns:
        OverflowCheckResult with detection details
    """
    if not text:
        return OverflowCheckResult(
            has_overflow=False,
            direction=OverflowDirection.NONE,
            overflow_pixels_x=0.0,
            overflow_pixels_y=0.0,
            estimated_text_width=0.0,
            estimated_text_height=0.0,
            confidence=1.0,
        )

    # Calculate text bounds
    text_bounds = calculate_text_bounds(text, font_size)

    # Available space (accounting for padding)
    available_width = bbox.width - (2 * padding)
    available_height = bbox.height - (2 * padding)

    # Calculate overflow
    overflow_x = max(0.0, text_bounds.width - available_width)
    overflow_y = max(0.0, text_bounds.height - available_height)

    # Determine overflow direction
    has_x_overflow = overflow_x > 0
    has_y_overflow = overflow_y > 0

    if has_x_overflow and has_y_overflow:
        direction = OverflowDirection.BOTH
    elif has_x_overflow:
        direction = OverflowDirection.RIGHT
    elif has_y_overflow:
        direction = OverflowDirection.BOTTOM
    else:
        direction = OverflowDirection.NONE

    has_overflow = has_x_overflow or has_y_overflow

    # Confidence is lower for estimation (higher with visual verification)
    # Estimation confidence decreases with text length due to font variations
    base_confidence = 0.7
    length_penalty = min(0.2, len(text) * 0.002)
    confidence = base_confidence - length_penalty

    return OverflowCheckResult(
        has_overflow=has_overflow,
        direction=direction,
        overflow_pixels_x=overflow_x,
        overflow_pixels_y=overflow_y,
        estimated_text_width=text_bounds.width,
        estimated_text_height=text_bounds.height,
        confidence=confidence,
    )


def check_boxes_overlap(
    bbox1: BBox,
    bbox2: BBox,
    tolerance: float = 1.0,
) -> OverlapCheckResult:
    """Check if two bounding boxes overlap.

    Uses geometric calculation to determine overlap.
    A small tolerance allows for rendering imprecisions.

    Args:
        bbox1: First bounding box
        bbox2: Second bounding box
        tolerance: Pixel tolerance for edge cases (default 1.0)

    Returns:
        OverlapCheckResult with detection details
    """
    # Ensure boxes are on the same page
    if bbox1.page != bbox2.page:
        return OverlapCheckResult(
            has_overlap=False,
            overlap_type=OverlapType.NONE,
            overlap_area=0.0,
            overlap_percentage=0.0,
            confidence=1.0,
        )

    # Calculate box coordinates
    x1_min, x1_max = bbox1.x, bbox1.x + bbox1.width
    y1_min, y1_max = bbox1.y, bbox1.y + bbox1.height
    x2_min, x2_max = bbox2.x, bbox2.x + bbox2.width
    y2_min, y2_max = bbox2.y, bbox2.y + bbox2.height

    # Calculate overlap region
    overlap_x_min = max(x1_min, x2_min)
    overlap_x_max = min(x1_max, x2_max)
    overlap_y_min = max(y1_min, y2_min)
    overlap_y_max = min(y1_max, y2_max)

    # Check if there is overlap (with tolerance)
    overlap_width = overlap_x_max - overlap_x_min + tolerance
    overlap_height = overlap_y_max - overlap_y_min + tolerance

    if overlap_width <= 0 or overlap_height <= 0:
        return OverlapCheckResult(
            has_overlap=False,
            overlap_type=OverlapType.NONE,
            overlap_area=0.0,
            overlap_percentage=0.0,
            confidence=1.0,
        )

    # Calculate overlap area
    overlap_area = max(0.0, overlap_width - tolerance) * max(0.0, overlap_height - tolerance)

    # Calculate areas of both boxes
    area1 = bbox1.width * bbox1.height
    area2 = bbox2.width * bbox2.height
    smaller_area = min(area1, area2)

    # Calculate overlap percentage relative to smaller box
    overlap_percentage = overlap_area / smaller_area if smaller_area > 0 else 0.0

    # Determine overlap type
    if overlap_percentage >= 0.95:
        overlap_type = OverlapType.FULL
    elif overlap_percentage > 0:
        overlap_type = OverlapType.PARTIAL
    else:
        overlap_type = OverlapType.NONE

    return OverlapCheckResult(
        has_overlap=overlap_percentage > 0,
        overlap_type=overlap_type,
        overlap_area=overlap_area,
        overlap_percentage=min(1.0, overlap_percentage),
        confidence=1.0,  # Geometric calculation is deterministic
    )


def detect_missing_value(
    value: str | None,
    is_required: bool,
) -> tuple[bool, str]:
    """Detect if a required field is missing a value.

    Args:
        value: The field value (None or empty string = missing)
        is_required: Whether the field is required

    Returns:
        Tuple of (is_missing, message)
        - is_missing: True if required field has no value
        - message: Human-readable description
    """
    is_empty = value is None or value.strip() == ""

    if is_required and is_empty:
        return (True, "Required field is missing a value")

    if not is_required and is_empty:
        return (False, "Optional field has no value")

    return (False, "Field has a value")


def calculate_confidence_update(
    original_confidence: float,
    has_overflow: bool,
    has_overlap: bool,
    overflow_severity: float = 0.3,
    overlap_severity: float = 0.2,
) -> float:
    """Calculate updated confidence based on detected issues.

    Issues reduce confidence in the field extraction.

    Args:
        original_confidence: Original extraction confidence (0.0 to 1.0)
        has_overflow: Whether overflow was detected
        has_overlap: Whether overlap was detected
        overflow_severity: Confidence reduction for overflow (default 0.3)
        overlap_severity: Confidence reduction for overlap (default 0.2)

    Returns:
        Updated confidence score (0.0 to 1.0)
    """
    penalty = 0.0

    if has_overflow:
        penalty += overflow_severity

    if has_overlap:
        penalty += overlap_severity

    updated_confidence = max(0.0, original_confidence - penalty)
    return updated_confidence
