"""
render_preview Tool Handler.

Renders a preview image of the filled form with field highlights and value overlays.
Returns base64-encoded PNG/JPEG image.

Features:
- Color-coded field status (filled, empty required, empty optional, active)
- Value overlay on filled fields
- Multiple highlight modes (all, empty, filled, single)
- Image compression for large files
"""

import base64
import io
from typing import Any, Literal

from mcp.types import CallToolResult, TextContent, ImageContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage


# Field status colors (RGB normalized 0-1)
COLORS = {
    "active": {
        "fill": (1.0, 1.0, 0.7),      # Light yellow fill
        "stroke": (1.0, 0.8, 0.0),     # Yellow outline
    },
    "filled": {
        "fill": None,                   # No fill
        "stroke": (0.2, 0.7, 0.2),      # Green outline
    },
    "empty_required": {
        "fill": None,                   # No fill
        "stroke": (0.8, 0.2, 0.2),      # Red outline
    },
    "empty_optional": {
        "fill": None,                   # No fill
        "stroke": (0.5, 0.5, 0.5),      # Gray outline
    },
}

# Text color for overlaid values (dark blue)
VALUE_TEXT_COLOR = (0.0, 0.0, 0.6)


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle render_preview tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - page: Page number (1-indexed, default: 1)
            - zoom: Zoom level (1.0 = 100%, default: 1.5)
            - highlight_mode: "all" | "empty" | "filled" | "single" (default: "all")
            - highlight_field_id: Field ID to highlight (when mode is "single")
            - show_values: Whether to overlay filled values (default: True)

    Returns:
        CallToolResult with rendered page image
    """
    form_id = arguments.get("form_id")
    page = arguments.get("page", 1)
    zoom = arguments.get("zoom", 1.5)
    highlight_mode = arguments.get("highlight_mode", "all")
    highlight_field_id = arguments.get("highlight_field_id")
    show_values = arguments.get("show_values", True)

    if not form_id:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Error: form_id is required"
            )]
        )

    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="Error: No active session"
            )]
        )

    storage = MCPStorage()

    try:
        form = await storage.get_form(session["id"], form_id)
        if not form:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error: Form not found: {form_id}"
                )]
            )

        # Render the page with visual enhancements
        image_bytes, mime_type = await _render_page(
            form=form,
            page=page,
            zoom=zoom,
            highlight_mode=highlight_mode,
            highlight_field_id=highlight_field_id,
            show_values=show_values,
        )

        # Encode as base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Return image with page info
        page_count = form.get("page_count", 1)
        fields = form.get("fields", {})

        # Count field status for info text
        page_fields = [f for f in fields.values() if f.get("page", 1) == page]
        filled_count = sum(1 for f in page_fields if f.get("value"))
        total_count = len(page_fields)

        info_text = (
            f"Page {page} of {page_count} | "
            f"Fields on page: {filled_count}/{total_count} filled | "
            f"Zoom: {int(zoom * 100)}%"
        )

        return CallToolResult(
            content=[
                ImageContent(
                    type="image",
                    data=image_b64,
                    mimeType=mime_type,
                ),
                TextContent(
                    type="text",
                    text=info_text
                ),
            ]
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text=f"Error rendering preview: {str(e)}"
            )]
        )


def _get_field_status(
    field_info: dict[str, Any],
    highlight_mode: str,
    highlight_field_id: str | None,
) -> str | None:
    """
    Determine the visual status of a field.

    Returns:
        Status string: "active", "filled", "empty_required", "empty_optional", or None
    """
    field_id = field_info.get("id")
    value = field_info.get("value")
    is_filled = value is not None and value != ""
    is_required = field_info.get("required", False)

    # Check if this is the active/highlighted field
    if highlight_mode == "single":
        if field_id == highlight_field_id:
            return "active"
        # In single mode, don't highlight other fields at all
        return None

    # For "empty" mode, only show empty fields
    if highlight_mode == "empty":
        if is_filled:
            return None
        return "empty_required" if is_required else "empty_optional"

    # For "filled" mode, only show filled fields
    if highlight_mode == "filled":
        return "filled" if is_filled else None

    # For "all" mode, show everything with appropriate status
    if is_filled:
        return "filled"
    return "empty_required" if is_required else "empty_optional"


async def _render_page(
    form: dict[str, Any],
    page: int,
    zoom: float,
    highlight_mode: Literal["all", "empty", "filled", "single"],
    highlight_field_id: str | None,
    show_values: bool,
) -> tuple[bytes, str]:
    """
    Render a form page with filled values and field status highlights.

    Args:
        form: Form metadata with fields and PDF path
        page: Page number (1-indexed)
        zoom: Zoom level
        highlight_mode: Which fields to highlight
        highlight_field_id: Specific field to highlight (for single mode)
        show_values: Whether to overlay filled values

    Returns:
        Tuple of (image_bytes, mime_type)
    """
    import fitz  # PyMuPDF

    pdf_path = form.get("path")
    if not pdf_path:
        raise ValueError("Form PDF path not found")

    fields = form.get("fields", {})

    # Open PDF
    doc = fitz.open(pdf_path)

    try:
        # Validate page number
        if page < 1 or page > len(doc):
            page = 1

        pdf_page = doc[page - 1]  # 0-indexed

        # Draw field highlights and overlays
        for field_id, field_info in fields.items():
            # Add field_id to field_info for status check
            field_with_id = {**field_info, "id": field_id}

            if field_with_id.get("page", 1) != page:
                continue

            bbox = field_with_id.get("bbox")
            position = field_with_id.get("position")

            # Get field status for coloring
            status = _get_field_status(
                field_with_id,
                highlight_mode,
                highlight_field_id,
            )

            if status and bbox:
                # Draw field highlight rectangle
                rect = fitz.Rect(bbox)
                colors = COLORS[status]

                # Draw filled background if specified
                if colors["fill"]:
                    shape = pdf_page.new_shape()
                    shape.draw_rect(rect)
                    shape.finish(
                        color=colors["stroke"],
                        fill=colors["fill"],
                        width=1.5,
                    )
                    shape.commit()
                else:
                    # Just draw outline
                    shape = pdf_page.new_shape()
                    shape.draw_rect(rect)
                    shape.finish(
                        color=colors["stroke"],
                        fill=None,
                        width=2,
                    )
                    shape.commit()

            # Overlay filled values
            value = field_with_id.get("value")
            if show_values and value:
                value_str = str(value)
                # Truncate long values
                if len(value_str) > 40:
                    value_str = value_str[:37] + "..."

                if bbox:
                    # Position text inside the field bbox
                    x = bbox[0] + 2
                    y = bbox[1] + 10  # Slightly below top of bbox

                    # Calculate appropriate font size based on field height
                    field_height = bbox[3] - bbox[1]
                    font_size = min(10, max(6, field_height - 4))

                    _insert_text_safe(
                        pdf_page,
                        (x, y),
                        value_str,
                        fontsize=font_size,
                        color=VALUE_TEXT_COLOR,
                    )
                elif position:
                    # Use position percentages if no bbox
                    page_rect = pdf_page.rect
                    x = page_rect.width * (position.get("x_percent", 10) / 100)
                    y = page_rect.height * (position.get("y_percent", 50) / 100)

                    _insert_text_safe(
                        pdf_page,
                        (x, y),
                        value_str,
                        fontsize=9,
                        color=VALUE_TEXT_COLOR,
                    )

        # Apply zoom and render to pixmap
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = pdf_page.get_pixmap(matrix=matrix, alpha=False)

        # Convert to PNG bytes
        png_bytes = pixmap.tobytes("png")

        # Compress if too large (>500KB)
        if len(png_bytes) > 500_000:
            jpeg_bytes, mime_type = _compress_to_jpeg(png_bytes)
            return jpeg_bytes, mime_type

        return png_bytes, "image/png"

    finally:
        doc.close()


def _insert_text_safe(
    page: Any,
    point: tuple[float, float],
    text: str,
    fontsize: float,
    color: tuple[float, float, float],
) -> None:
    """
    Insert text at a point, handling font issues gracefully.

    Args:
        page: PyMuPDF page object
        point: (x, y) coordinates
        text: Text to insert
        fontsize: Font size
        color: RGB color tuple (0-1 range)
    """
    try:
        # Try to insert with default font
        page.insert_text(
            point,
            text,
            fontsize=fontsize,
            color=color,
            fontname="helv",  # Helvetica
        )
    except Exception:
        # Fallback: try with built-in font
        try:
            page.insert_text(
                point,
                text,
                fontsize=fontsize,
                color=color,
            )
        except Exception:
            # If all else fails, skip this text
            pass


def _compress_to_jpeg(png_bytes: bytes, quality: int = 85) -> tuple[bytes, str]:
    """
    Compress PNG bytes to JPEG for smaller file size.

    Args:
        png_bytes: Original PNG image bytes
        quality: JPEG quality (0-100)

    Returns:
        Tuple of (jpeg_bytes, mime_type)
    """
    from PIL import Image

    # Open PNG from bytes
    img = Image.open(io.BytesIO(png_bytes))

    # Convert to RGB if necessary (JPEG doesn't support alpha)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Save as JPEG
    output = io.BytesIO()
    img.save(output, "JPEG", quality=quality, optimize=True)

    return output.getvalue(), "image/jpeg"
