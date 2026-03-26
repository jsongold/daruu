"""Text rendering rules for the Fill service.

Implements deterministic text layout algorithms including
word wrapping, font sizing, and alignment calculations.
All functions are pure and produce consistent output.
"""

from typing import Callable

from app.services.fill.domain.models import (
    BoundingBox,
    FontConfig,
    TextBlock,
    TextLine,
    TextMetrics,
)


def measure_text(
    text: str,
    font: FontConfig,
    measure_fn: Callable[[str, str, float], tuple[float, float]],
) -> TextMetrics:
    """Measure the dimensions of text with the given font.

    Args:
        text: Text to measure
        font: Font configuration to use
        measure_fn: Function that measures text (text, font_family, font_size) -> (width, height)

    Returns:
        TextMetrics with measured dimensions
    """
    if not text:
        return TextMetrics(
            width=0.0,
            height=0.0,
            line_count=0,
            char_count=0,
            ascent=0.0,
            descent=0.0,
        )

    lines = text.split("\n")
    max_width = 0.0
    total_height = 0.0

    for line in lines:
        width, height = measure_fn(line, font.family, font.size)
        max_width = max(max_width, width)
        total_height += height

    # Estimate ascent and descent from font size
    ascent = font.size * 0.8
    descent = font.size * 0.2

    return TextMetrics(
        width=max_width,
        height=total_height,
        line_count=len(lines),
        char_count=len(text),
        ascent=ascent,
        descent=descent,
    )


def wrap_text(
    text: str,
    max_width: float,
    font: FontConfig,
    measure_fn: Callable[[str, str, float], tuple[float, float]],
) -> tuple[str, ...]:
    """Wrap text to fit within the specified width.

    Uses a simple word-based wrapping algorithm that
    breaks lines at word boundaries.

    Args:
        text: Text to wrap
        max_width: Maximum width for each line
        font: Font configuration for measurement
        measure_fn: Function to measure text dimensions

    Returns:
        Tuple of wrapped lines
    """
    if not text:
        return ()

    if max_width <= 0:
        return (text,)

    # Handle existing line breaks first
    paragraphs = text.split("\n")
    result_lines: list[str] = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            result_lines.append("")
            continue

        words = paragraph.split()
        if not words:
            result_lines.append("")
            continue

        current_line = words[0]

        for word in words[1:]:
            test_line = current_line + " " + word
            width, _ = measure_fn(test_line, font.family, font.size)

            if width <= max_width:
                current_line = test_line
            else:
                result_lines.append(current_line)
                current_line = word

        result_lines.append(current_line)

    return tuple(result_lines)


def calculate_alignment_offset(
    text_width: float,
    box_width: float,
    alignment: str,
) -> float:
    """Calculate the x offset for text alignment.

    Args:
        text_width: Width of the text to align
        box_width: Width of the containing box
        alignment: Alignment type (left, center, right)

    Returns:
        X offset for the text position
    """
    if alignment == "center":
        return (box_width - text_width) / 2
    elif alignment == "right":
        return box_width - text_width
    else:
        return 0.0


def layout_text_block(
    text: str,
    bbox: BoundingBox,
    font: FontConfig,
    alignment: str,
    line_height: float,
    word_wrap: bool,
    overflow_handling: str,
    measure_fn: Callable[[str, str, float], tuple[float, float]],
) -> TextBlock:
    """Layout text within a bounding box.

    Performs word wrapping (if enabled), alignment calculation,
    and overflow detection to produce a renderable text block.

    Args:
        text: Text to layout
        bbox: Bounding box to fill
        font: Font configuration
        alignment: Text alignment (left, center, right)
        line_height: Line height multiplier
        word_wrap: Whether to enable word wrapping
        overflow_handling: How to handle overflow (truncate, shrink, error)
        measure_fn: Function to measure text

    Returns:
        TextBlock ready for rendering
    """
    if not text:
        return TextBlock(
            lines=(),
            total_width=0.0,
            total_height=0.0,
            overflow=False,
            truncated=False,
            original_text=text,
        )

    # Wrap text if enabled
    if word_wrap:
        wrapped_lines = wrap_text(text, bbox.width, font, measure_fn)
    else:
        wrapped_lines = tuple(text.split("\n"))

    # Calculate line dimensions
    _, single_line_height = measure_fn("X", font.family, font.size)
    actual_line_height = single_line_height * line_height

    # Check for vertical overflow
    total_height = len(wrapped_lines) * actual_line_height
    overflow = total_height > bbox.height
    truncated = False

    # Handle overflow
    rendered_lines: list[str] = list(wrapped_lines)
    if overflow:
        if overflow_handling == "truncate":
            max_lines = max(1, int(bbox.height / actual_line_height))
            rendered_lines = list(wrapped_lines[:max_lines])
            truncated = len(wrapped_lines) > max_lines
        elif overflow_handling == "shrink":
            # Calculate scale factor to fit
            scale = bbox.height / total_height
            new_size = max(4.0, font.size * scale)  # Minimum 4pt font
            font = font.with_size(new_size)
            _, single_line_height = measure_fn("X", font.family, font.size)
            actual_line_height = single_line_height * line_height
            total_height = len(wrapped_lines) * actual_line_height

    # Build positioned lines
    text_lines: list[TextLine] = []
    current_y = bbox.y + bbox.height - actual_line_height  # Start from top

    max_width = 0.0
    for line_text in rendered_lines:
        if current_y < bbox.y:
            break

        line_width, _ = measure_fn(line_text, font.family, font.size)
        max_width = max(max_width, line_width)

        x_offset = calculate_alignment_offset(line_width, bbox.width, alignment)

        text_lines.append(
            TextLine(
                text=line_text,
                x=bbox.x + x_offset,
                y=current_y,
                width=line_width,
                height=actual_line_height,
            )
        )

        current_y -= actual_line_height

    return TextBlock(
        lines=tuple(text_lines),
        total_width=max_width,
        total_height=len(text_lines) * actual_line_height,
        overflow=overflow,
        truncated=truncated,
        original_text=text,
    )


def detect_overlap(
    blocks: tuple[BoundingBox, ...],
) -> list[tuple[int, int]]:
    """Detect overlapping bounding boxes.

    Returns pairs of indices for boxes that overlap.
    Uses a simple O(n^2) algorithm suitable for typical
    form field counts.

    Args:
        blocks: Tuple of bounding boxes to check

    Returns:
        List of (index1, index2) pairs that overlap
    """
    overlaps: list[tuple[int, int]] = []

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if blocks[i].overlaps(blocks[j]):
                overlaps.append((i, j))

    return overlaps


def calculate_auto_font_size(
    text: str,
    bbox: BoundingBox,
    font: FontConfig,
    min_size: float,
    max_size: float,
    measure_fn: Callable[[str, str, float], tuple[float, float]],
) -> float:
    """Calculate font size to fit text in bounding box.

    Uses binary search to find the largest font size
    that allows the text to fit within the box.

    Args:
        text: Text to fit
        bbox: Bounding box constraint
        font: Base font configuration
        min_size: Minimum allowed font size
        max_size: Maximum allowed font size
        measure_fn: Function to measure text

    Returns:
        Optimal font size
    """
    low = min_size
    high = max_size
    result = min_size

    while high - low > 0.5:  # 0.5pt precision
        mid = (low + high) / 2
        test_font = font.with_size(mid)

        # Check if text fits
        wrapped = wrap_text(text, bbox.width, test_font, measure_fn)
        _, line_height = measure_fn("X", test_font.family, test_font.size)
        total_height = len(wrapped) * line_height * 1.2  # Default line height

        if total_height <= bbox.height:
            result = mid
            low = mid
        else:
            high = mid

    return result


def split_text_for_multiline_field(
    text: str,
    line_count: int,
    max_chars_per_line: int | None = None,
) -> tuple[str, ...]:
    """Split text across multiple fixed lines.

    Used for forms with multiple single-line fields
    that should contain parts of a longer text.

    Args:
        text: Text to split
        line_count: Number of lines to split into
        max_chars_per_line: Maximum characters per line

    Returns:
        Tuple of text parts
    """
    if not text or line_count <= 0:
        return ()

    # Split by existing newlines first
    lines = text.split("\n")

    # If we have more lines than needed, join them back
    if len(lines) > line_count:
        # Try to fit into available lines
        result: list[str] = []
        remaining = lines

        while remaining and len(result) < line_count:
            if len(result) == line_count - 1:
                # Last line gets everything remaining
                result.append(" ".join(remaining))
                break
            else:
                result.append(remaining[0])
                remaining = remaining[1:]

        return tuple(result)

    # Pad with empty strings if needed
    while len(lines) < line_count:
        lines.append("")

    # Truncate if max_chars_per_line is specified
    if max_chars_per_line is not None:
        lines = [line[:max_chars_per_line] for line in lines]

    return tuple(lines[:line_count])
