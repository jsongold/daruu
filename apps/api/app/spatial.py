"""Spatial utilities for field-label matching in PDF forms."""

import math
import re


def direction_score(
    field_bbox: tuple[float, float, float, float],
    label_bbox: tuple[float, float, float, float],
) -> tuple[float, str]:
    """Compute spatial distance score and direction from label to field.

    Args:
        field_bbox: (x, y, width, height) normalized 0-1
        label_bbox: (x, y, width, height) normalized 0-1

    Returns:
        (score, direction) where lower score = better match.
        Direction is one of: "left", "right", "above", "below", "overlap".
    """
    fx, fy, fw, fh = field_bbox
    lx, ly, lw, lh = label_bbox

    fcx, fcy = fx + fw / 2, fy + fh / 2
    lcx, lcy = lx + lw / 2, ly + lh / 2

    overlap = (lx < fx + fw and lx + lw > fx and ly < fy + fh and ly + lh > fy)
    if overlap:
        return 0.0, "overlap"

    base_dist = math.sqrt((fcx - lcx) ** 2 + (fcy - lcy) ** 2)
    dx = fcx - lcx  # positive = label is to the left of field
    dy = fcy - lcy  # positive = label is above field

    if abs(dx) >= abs(dy):
        direction = "left" if dx > 0 else "right"
    else:
        direction = "above" if dy > 0 else "below"

    multipliers = {"left": 0.8, "above": 0.9, "right": 2.0, "below": 1.5, "overlap": 0.5}
    score = base_dist * multipliers[direction]

    # Vertical alignment bonus: same row -> x0.7
    avg_height = (fh + lh) / 2
    if avg_height > 0 and abs(fcy - lcy) < avg_height * 0.5:
        score *= 0.7

    return score, direction


_DECORATION_RE = re.compile(
    r"^[\s\W_]{0,3}$"
    r"|^\.{2,}$"
    r"|^-{2,}$"
    r"|^_{2,}$"
    r"|^\d{1,2}$"
)


def is_decoration(text: str) -> bool:
    """Return True if text is decorative (not a meaningful label)."""
    t = text.strip()
    if not t:
        return True
    if _DECORATION_RE.match(t):
        return True
    if len(t) == 1 and not t.isalnum():
        return True
    return False


def score_to_confidence(score: float, scale: float = 0.15) -> int:
    """Convert a direction_score (lower=better) to confidence 0-100."""
    if score <= 0.0:
        return 95
    raw = 100.0 * math.exp(-score / scale)
    return max(0, min(100, int(raw)))
