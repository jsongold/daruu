"""Domain models for the Adjust service.

These are internal domain models used for bbox calculations and
adjustment logic. They are separate from the API contract models.
All use frozen dataclasses for immutability.
"""

from dataclasses import dataclass
from enum import Enum


class AdjustmentDirection(str, Enum):
    """Direction of bbox adjustment."""

    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
    SHRINK_WIDTH = "shrink_width"
    SHRINK_HEIGHT = "shrink_height"
    EXPAND_WIDTH = "expand_width"
    EXPAND_HEIGHT = "expand_height"


@dataclass(frozen=True)
class BboxValues:
    """Immutable bounding box values for calculations.

    This is a lightweight domain model for internal bbox operations.
    """

    x: float
    y: float
    width: float
    height: float
    page: int

    @property
    def right(self) -> float:
        """Right edge coordinate (x + width)."""
        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Bottom edge coordinate (y + height)."""
        return self.y + self.height

    @property
    def area(self) -> float:
        """Area of the bounding box."""
        return self.width * self.height

    @property
    def center_x(self) -> float:
        """X coordinate of center."""
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        """Y coordinate of center."""
        return self.y + self.height / 2


@dataclass(frozen=True)
class BboxAdjustment:
    """Represents an adjustment to be applied to a bbox.

    Immutable representation of how a bbox should change.
    """

    delta_x: float = 0.0
    delta_y: float = 0.0
    delta_width: float = 0.0
    delta_height: float = 0.0
    direction: AdjustmentDirection | None = None
    reason: str = ""

    @property
    def is_identity(self) -> bool:
        """Check if this adjustment makes no changes."""
        return (
            self.delta_x == 0.0
            and self.delta_y == 0.0
            and self.delta_width == 0.0
            and self.delta_height == 0.0
        )


@dataclass(frozen=True)
class OverlapInfo:
    """Information about overlap between two bboxes."""

    field_id_a: str
    field_id_b: str
    overlap_area: float
    overlap_ratio_a: float  # Overlap area / area of bbox A
    overlap_ratio_b: float  # Overlap area / area of bbox B
    intersection_bbox: BboxValues | None = None


@dataclass(frozen=True)
class OverflowInfo:
    """Information about bbox overflow beyond page bounds."""

    field_id: str
    overflow_left: float = 0.0  # Amount past left edge (x < 0)
    overflow_right: float = 0.0  # Amount past right edge
    overflow_top: float = 0.0  # Amount past top edge (y < 0)
    overflow_bottom: float = 0.0  # Amount past bottom edge

    @property
    def has_overflow(self) -> bool:
        """Check if there is any overflow."""
        return (
            self.overflow_left > 0
            or self.overflow_right > 0
            or self.overflow_top > 0
            or self.overflow_bottom > 0
        )

    @property
    def total_overflow(self) -> float:
        """Total overflow amount in all directions."""
        return (
            self.overflow_left
            + self.overflow_right
            + self.overflow_top
            + self.overflow_bottom
        )


@dataclass(frozen=True)
class AdjustmentResult:
    """Result of attempting an adjustment.

    Contains the adjustment to apply and metadata about success.
    """

    field_id: str
    adjustment: BboxAdjustment
    success: bool
    issue_resolved: bool = False
    new_issues_created: bool = False
    confidence_impact: float = 0.0  # Positive = confidence increase
