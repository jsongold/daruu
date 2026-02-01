"""Fill service domain layer.

Contains internal domain models and business rules for PDF filling.
These are not exposed through the API contract.
"""

from app.services.fill.domain.models import (
    AcroFormField,
    BoundingBox,
    FieldSpec,
    FontConfig,
    FontStyle,
    OverlaySpec,
    TextBlock,
    TextLine,
    TextMetrics,
)
from app.services.fill.domain.rules import (
    calculate_alignment_offset,
    calculate_auto_font_size,
    detect_overlap,
    layout_text_block,
    measure_text,
    split_text_for_multiline_field,
    wrap_text,
)

__all__ = [
    # Models
    "AcroFormField",
    "BoundingBox",
    "FieldSpec",
    "FontConfig",
    "FontStyle",
    "OverlaySpec",
    "TextBlock",
    "TextLine",
    "TextMetrics",
    # Rules
    "calculate_alignment_offset",
    "calculate_auto_font_size",
    "detect_overlap",
    "layout_text_block",
    "measure_text",
    "split_text_for_multiline_field",
    "wrap_text",
]
