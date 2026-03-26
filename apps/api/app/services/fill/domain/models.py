"""Internal domain models for the Fill service.

These models are used within the service layer and are not
exposed through the API contract. They represent internal
concepts needed for PDF manipulation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class FontStyle(str, Enum):
    """Font style for text rendering."""

    NORMAL = "normal"
    BOLD = "bold"
    ITALIC = "italic"
    BOLD_ITALIC = "bold_italic"


@dataclass(frozen=True)
class FontConfig:
    """Configuration for a font used in rendering.

    Encapsulates font information needed for text rendering
    including fallback options for character coverage.
    """

    family: str
    size: float
    style: FontStyle = FontStyle.NORMAL
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    fallback_family: str | None = None
    embed: bool = True

    def with_size(self, new_size: float) -> "FontConfig":
        """Create a new FontConfig with a different size."""
        return FontConfig(
            family=self.family,
            size=new_size,
            style=self.style,
            color=self.color,
            fallback_family=self.fallback_family,
            embed=self.embed,
        )

    def with_color(self, new_color: tuple[float, float, float]) -> "FontConfig":
        """Create a new FontConfig with a different color."""
        return FontConfig(
            family=self.family,
            size=self.size,
            style=self.style,
            color=new_color,
            fallback_family=self.fallback_family,
            embed=self.embed,
        )


@dataclass(frozen=True)
class TextMetrics:
    """Metrics for a rendered text block.

    Contains measurements needed to determine if text
    fits within its bounding box and detect overflow.
    """

    width: float
    height: float
    line_count: int
    char_count: int
    ascent: float
    descent: float

    @property
    def total_height(self) -> float:
        """Total height including ascent and descent."""
        return self.height + self.ascent + self.descent


@dataclass(frozen=True)
class TextLine:
    """A single line of text to be rendered.

    Represents a line after word wrapping has been applied,
    ready to be drawn at a specific position.
    """

    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class TextBlock:
    """A block of text to be rendered in a bounding box.

    Contains all lines after layout calculation,
    ready to be drawn to the PDF.
    """

    lines: tuple[TextLine, ...]
    total_width: float
    total_height: float
    overflow: bool
    truncated: bool
    original_text: str

    @property
    def line_count(self) -> int:
        """Number of lines in the block."""
        return len(self.lines)


@dataclass(frozen=True)
class BoundingBox:
    """Internal representation of a bounding box.

    Uses PDF coordinate system (origin at bottom-left).
    """

    x: float
    y: float
    width: float
    height: float
    page: int

    @property
    def x2(self) -> float:
        """Right edge x coordinate."""
        return self.x + self.width

    @property
    def y2(self) -> float:
        """Top edge y coordinate."""
        return self.y + self.height

    def contains_point(self, px: float, py: float) -> bool:
        """Check if a point is within this bounding box."""
        return self.x <= px <= self.x2 and self.y <= py <= self.y2

    def overlaps(self, other: "BoundingBox") -> bool:
        """Check if this bounding box overlaps with another."""
        if self.page != other.page:
            return False
        return not (
            self.x2 < other.x or other.x2 < self.x or self.y2 < other.y or other.y2 < self.y
        )

    def with_padding(self, padding: float) -> "BoundingBox":
        """Create a new bounding box with padding applied."""
        return BoundingBox(
            x=self.x + padding,
            y=self.y + padding,
            width=max(0, self.width - 2 * padding),
            height=max(0, self.height - 2 * padding),
            page=self.page,
        )


@dataclass(frozen=True)
class FieldSpec:
    """Specification for a field to be filled.

    Contains all information needed to render a value
    into a specific location on the PDF.
    """

    field_id: str
    value: str
    bbox: BoundingBox
    font: FontConfig
    alignment: str
    line_height: float
    word_wrap: bool
    overflow_handling: str
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class AcroFormField:
    """Specification for an AcroForm field.

    Represents a native PDF form field that can be
    filled programmatically using PDF libraries.
    """

    field_name: str
    field_type: str
    value: str
    appearance_stream: bool = False
    readonly: bool = False


@dataclass(frozen=True)
class OverlaySpec:
    """Specification for an overlay to be rendered.

    Groups all text blocks for a single page into
    an overlay that will be merged with the original PDF.
    """

    page_number: int
    fields: tuple[FieldSpec, ...]
    background_opacity: float = 0.0

    @property
    def field_count(self) -> int:
        """Number of fields on this overlay."""
        return len(self.fields)
