"""
render_preview Tool Handler.

Renders a preview image of the filled form with optional field highlights.
Returns base64-encoded PNG image.
"""

import base64
from typing import Any

from mcp.types import CallToolResult, TextContent, ImageContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle render_preview tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - page: Page number (1-indexed, default: 1)
            - zoom: Zoom level (1.0 = 100%, default: 1.0)
            - highlight_fields: Optional list of field IDs to highlight

    Returns:
        CallToolResult with rendered page image
    """
    form_id = arguments.get("form_id")
    page = arguments.get("page", 1)
    zoom = arguments.get("zoom", 1.0)
    highlight_fields = arguments.get("highlight_fields", [])

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

        # Render the page with current field values
        image_bytes = await _render_page(
            form=form,
            page=page,
            zoom=zoom,
            highlight_fields=highlight_fields,
        )

        # Encode as base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Return image with page info
        page_count = form.get("page_count", 1)

        return CallToolResult(
            content=[
                ImageContent(
                    type="image",
                    data=image_b64,
                    mimeType="image/png",
                ),
                TextContent(
                    type="text",
                    text=f"Page {page} of {page_count} (zoom: {int(zoom * 100)}%)"
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


async def _render_page(
    form: dict[str, Any],
    page: int,
    zoom: float,
    highlight_fields: list[str],
) -> bytes:
    """
    Render a form page with filled values and highlights.

    Args:
        form: Form metadata with fields and PDF path
        page: Page number (1-indexed)
        zoom: Zoom level
        highlight_fields: Field IDs to highlight

    Returns:
        PNG image bytes
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

        # Apply zoom
        matrix = fitz.Matrix(zoom, zoom)

        # Render to pixmap
        pixmap = pdf_page.get_pixmap(matrix=matrix, alpha=False)

        # Add field overlays if needed
        # This draws filled values on top of the PDF
        for field_id, field_info in fields.items():
            if field_info.get("page", 1) != page:
                continue

            value = field_info.get("value")
            if not value:
                continue

            bbox = field_info.get("bbox")
            if not bbox:
                continue

            # Scale bbox by zoom
            x0, y0, x1, y1 = bbox
            x0, y0 = int(x0 * zoom), int(y0 * zoom)
            x1, y1 = int(x1 * zoom), int(y1 * zoom)

            # Highlight if requested
            if field_id in highlight_fields:
                # Draw highlight rectangle
                shape = pdf_page.new_shape()
                rect = fitz.Rect(bbox)
                shape.draw_rect(rect)
                shape.finish(
                    color=(1, 0.9, 0),  # Yellow
                    fill=(1, 1, 0.7),
                    width=2,
                )
                shape.commit()

        # Re-render with overlays
        pixmap = pdf_page.get_pixmap(matrix=matrix, alpha=False)

        # Convert to PNG bytes
        png_bytes = pixmap.tobytes("png")

        return png_bytes

    finally:
        doc.close()
