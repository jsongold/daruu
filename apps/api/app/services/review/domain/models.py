"""Domain models for the Review service.

All models use frozen=True for immutability, following project conventions.
These are internal domain models, distinct from the API contract models.
"""

from dataclasses import dataclass
from enum import Enum


class OverflowDirection(str, Enum):
    """Direction of text overflow."""

    NONE = "none"
    RIGHT = "right"
    BOTTOM = "bottom"
    BOTH = "both"


class OverlapType(str, Enum):
    """Type of bounding box overlap."""

    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"


@dataclass(frozen=True)
class RenderResult:
    """Result of rendering a PDF page.

    Contains the rendered image bytes and metadata about the rendering.
    """

    page_number: int
    image_data: bytes
    width: int
    height: int
    dpi: int

    def __post_init__(self) -> None:
        """Validate render result data."""
        if self.page_number < 1:
            raise ValueError("page_number must be >= 1")
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be > 0")
        if self.dpi <= 0:
            raise ValueError("dpi must be > 0")


@dataclass(frozen=True)
class ChangeRegion:
    """A region where changes were detected between images.

    Represents a rectangular area where the filled PDF differs
    from the original template.
    """

    x: float
    y: float
    width: float
    height: float
    page: int
    change_percentage: float  # 0.0 to 1.0

    def __post_init__(self) -> None:
        """Validate change region data."""
        if self.width < 0 or self.height < 0:
            raise ValueError("width and height must be >= 0")
        if not 0.0 <= self.change_percentage <= 1.0:
            raise ValueError("change_percentage must be between 0.0 and 1.0")


@dataclass(frozen=True)
class DiffResult:
    """Result of generating a visual diff between two images.

    Contains the diff image and metadata about detected changes.
    """

    diff_image: bytes
    change_regions: tuple[ChangeRegion, ...]
    total_change_percentage: float  # 0.0 to 1.0
    has_significant_changes: bool

    def __post_init__(self) -> None:
        """Validate diff result data."""
        if not 0.0 <= self.total_change_percentage <= 1.0:
            raise ValueError("total_change_percentage must be between 0.0 and 1.0")


@dataclass(frozen=True)
class OverflowCheckResult:
    """Result of checking for text overflow.

    Contains details about whether text exceeds its bounding box.
    """

    has_overflow: bool
    direction: OverflowDirection
    overflow_pixels_x: float  # Pixels exceeding in X direction
    overflow_pixels_y: float  # Pixels exceeding in Y direction
    estimated_text_width: float
    estimated_text_height: float
    confidence: float  # Confidence in the detection (0.0 to 1.0)

    def __post_init__(self) -> None:
        """Validate overflow check result data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class OverlapCheckResult:
    """Result of checking for bounding box overlap.

    Contains details about whether two boxes overlap.
    """

    has_overlap: bool
    overlap_type: OverlapType
    overlap_area: float  # Area of overlap in square pixels
    overlap_percentage: float  # Percentage of smaller box that overlaps
    confidence: float  # Confidence in the detection (0.0 to 1.0)

    def __post_init__(self) -> None:
        """Validate overlap check result data."""
        if self.overlap_area < 0:
            raise ValueError("overlap_area must be >= 0")
        if not 0.0 <= self.overlap_percentage <= 1.0:
            raise ValueError("overlap_percentage must be between 0.0 and 1.0")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class TextBounds:
    """Estimated bounds of rendered text.

    Used for calculating whether text will fit within a bounding box.
    """

    width: float
    height: float
    baseline_offset: float

    def __post_init__(self) -> None:
        """Validate text bounds data."""
        if self.width < 0 or self.height < 0:
            raise ValueError("width and height must be >= 0")
