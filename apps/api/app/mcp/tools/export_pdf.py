"""
export_pdf Tool Handler.

Exports the filled form as a PDF.
Requires the source PDF (via URL, path, or re-attachment).
Returns a download URL.
"""

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session

FORM_PREFIX = "mcp:form:"
STORAGE_TTL = 3600


def _get_redis_client() -> Any:
    """Get Redis client."""
    try:
        import redis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/2")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


async def _get_form(session_id: str, form_id: str) -> dict[str, Any] | None:
    """Get form data from Redis."""
    client = _get_redis_client()
    if not client:
        return None

    key = f"{FORM_PREFIX}{session_id}:{form_id}"
    data = client.get(key)
    if data:
        return json.loads(data)
    return None


async def _fetch_pdf_from_url(url: str) -> bytes:
    """Fetch PDF from a URL."""
    import httpx

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            raise ValueError("URL does not point to a PDF file")

        return response.content


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle export_pdf tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form to export
            - source_url: URL to fetch the original PDF (Google Drive, Dropbox, etc.)
            - source_data: Base64-encoded PDF (if user re-attaches)
            - flatten: Whether to flatten form fields (default: False)

    Returns:
        CallToolResult with download URL or instructions
    """
    form_id = arguments.get("form_id")
    source_url = arguments.get("source_url")
    source_data = arguments.get("source_data")
    flatten = arguments.get("flatten", False)

    if not form_id:
        return CallToolResult(content=[TextContent(type="text", text="Error: form_id is required")])

    session = await get_current_session()
    if not session:
        return CallToolResult(content=[TextContent(type="text", text="Error: No active session")])

    # Get form metadata
    form = await _get_form(session["id"], form_id)
    if not form:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: Form not found: {form_id}")]
        )

    # Need source PDF - check what we have
    pdf_bytes = None

    if source_data:
        # User re-attached the PDF
        try:
            pdf_bytes = base64.b64decode(source_data)
            if not pdf_bytes.startswith(b"%PDF"):
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="Error: Invalid PDF data. Please attach a valid PDF file.",
                        )
                    ]
                )
        except Exception:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: Invalid base64 data")]
            )

    elif source_url:
        # Fetch from URL
        try:
            pdf_bytes = await _fetch_pdf_from_url(source_url)
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error fetching PDF from URL: {str(e)}")]
            )

    else:
        # No source provided - ask user
        form_type = form.get("form_type", "form")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"📄 **Source PDF needed for export**\n\n"
                        f"To generate your filled {form_type}, I need the original PDF.\n\n"
                        f"Please either:\n"
                        f"1. **Share a link** to the PDF (Google Drive, Dropbox, etc.)\n"
                        f"2. **Attach the PDF again** to this conversation\n\n"
                        f"Then tell me to export again."
                    ),
                )
            ]
        )

    # Now we have the PDF - fill it
    try:
        filled_pdf_bytes = await _generate_filled_pdf(
            pdf_bytes=pdf_bytes,
            form=form,
            flatten=flatten,
        )

        # Save and create download URL
        temp_dir = Path(tempfile.gettempdir()) / "daru-mcp-exports"
        temp_dir.mkdir(parents=True, exist_ok=True)

        export_id = str(uuid4())
        form_type = form.get("form_type", "form")
        filename = f"{form_type}_{export_id[:8]}_filled.pdf"
        output_path = temp_dir / filename

        output_path.write_bytes(filled_pdf_bytes)

        # For now, return local path (in production, upload to cloud storage)
        app_url = os.environ.get("DARU_APP_URL", "http://localhost:5173")
        download_url = f"{app_url}/api/mcp/download/{export_id}"

        # Store download info in Redis
        client = _get_redis_client()
        if client:
            download_data = {
                "path": str(output_path),
                "filename": filename,
                "created_at": str(os.path.getmtime(output_path)),
            }
            client.setex(f"mcp:download:{export_id}", 600, json.dumps(download_data))

        # Build response
        fields = form.get("fields", {})
        filled_count = sum(1 for f in fields.values() if f.get("value") is not None)
        total_count = len(fields)

        response_text = (
            f"✅ **PDF Generated Successfully!**\n\n"
            f"- Form: {form_type}\n"
            f"- Fields filled: {filled_count}/{total_count}\n"
            f"- Flattened: {'Yes' if flatten else 'No'}\n\n"
            f"📥 [Download {filename}]({download_url})\n\n"
            f"_Link expires in 10 minutes_"
        )

        return CallToolResult(content=[TextContent(type="text", text=response_text)])

    except Exception as e:
        import traceback

        traceback.print_exc()
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error generating PDF: {str(e)}")]
        )


async def _generate_filled_pdf(
    pdf_bytes: bytes,
    form: dict[str, Any],
    flatten: bool,
) -> bytes:
    """
    Generate a PDF with filled field values.

    Args:
        pdf_bytes: Original PDF as bytes
        form: Form metadata with field values
        flatten: Whether to flatten (make non-editable)

    Returns:
        Filled PDF as bytes
    """
    import io

    import fitz  # PyMuPDF

    fields = form.get("fields", {})

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        has_widgets = any(page.widgets() for page in doc)

        if has_widgets:
            # Fill AcroForm fields by matching names
            for page in doc:
                for widget in page.widgets():
                    widget_name = widget.field_name
                    if not widget_name:
                        continue

                    # Find matching field by name or label
                    for field_info in fields.values():
                        field_name = field_info.get("name", "")
                        field_label = field_info.get("label", "")
                        value = field_info.get("value")

                        if value is None:
                            continue

                        # Match by name (case-insensitive, partial match)
                        if (
                            widget_name.lower() in field_name.lower()
                            or field_name.lower() in widget_name.lower()
                            or widget_name.lower() in field_label.lower()
                            or field_label.lower() in widget_name.lower()
                        ):
                            if field_info.get("type") == "checkbox":
                                widget.field_value = bool(value)
                            else:
                                widget.field_value = str(value)
                            widget.update()
                            break
        else:
            # No AcroForm - use text overlay
            for field_info in fields.values():
                value = field_info.get("value")
                if value is None:
                    continue

                position = field_info.get("position", {})
                page_num = field_info.get("page", 1) - 1

                if 0 <= page_num < len(doc):
                    page = doc[page_num]

                    # Try to determine position
                    # This is approximate - based on Claude's visual analysis
                    y_percent = position.get("y_percent", 50)
                    x_percent = position.get("x_percent", 10)

                    rect = page.rect
                    x = rect.width * (x_percent / 100)
                    y = rect.height * (y_percent / 100)

                    page.insert_text(
                        (x, y),
                        str(value),
                        fontsize=11,
                        fontname="helv",
                    )

        # Convert to bytes
        output = io.BytesIO()
        doc.save(output)
        return output.getvalue()

    finally:
        doc.close()
