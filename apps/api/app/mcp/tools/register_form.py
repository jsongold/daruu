"""
register_form Tool Handler.

Registers a form that Claude has analyzed visually.
No file data needed - Claude extracts field info using its vision.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from mcp.types import CallToolResult, TextContent

from app.mcp.logging import tool_logger
from app.mcp.session import get_current_session


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


FORM_PREFIX = "mcp:form:"
STORAGE_TTL = 3600  # 1 hour


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle register_form tool call.

    Claude has already read the PDF visually and extracted field info.
    We just store the metadata - no actual PDF needed yet.

    Args:
        arguments: Tool arguments containing:
            - form_type: Type of form (e.g., "W-9", "1040")
            - fields: List of field definitions Claude extracted
            - page_count: Number of pages
            - metadata: Optional additional info

    Returns:
        CallToolResult with form_id for subsequent operations
    """
    form_type = arguments.get("form_type", "unknown")
    fields = arguments.get("fields", [])
    page_count = arguments.get("page_count", 1)
    metadata = arguments.get("metadata", {})

    tool_logger.debug(f"register_form: type={form_type}, fields={len(fields)}, pages={page_count}")

    if not fields:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        "Error: No fields provided. Please analyze the PDF visually "
                        "and extract the field names, types, and positions."
                    ),
                )
            ]
        )

    # Get current MCP session
    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[
                TextContent(
                    type="text", text="Error: No active session. Please start a new conversation."
                )
            ]
        )

    session_id = session["id"]
    form_id = str(uuid4())

    # Normalize fields to consistent format
    normalized_fields = {}
    for i, field in enumerate(fields):
        field_id = field.get("id") or str(uuid4())
        normalized_fields[field_id] = {
            "id": field_id,
            "name": field.get("name") or f"field_{i + 1}",
            "label": field.get("label") or field.get("name") or f"Field {i + 1}",
            "type": field.get("type", "text"),
            "page": field.get("page", 1),
            "position": field.get("position"),
            "required": field.get("required", False),
            "options": field.get("options"),  # For dropdowns/checkboxes
            "value": None,  # To be filled later
            "validation": field.get("validation"),
        }

    # Store form metadata
    form_data = {
        "id": form_id,
        "session_id": session_id,
        "form_type": form_type,
        "page_count": page_count,
        "field_count": len(normalized_fields),
        "fields": normalized_fields,
        "metadata": metadata,
        "status": "registered",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_file": None,  # Will be set at export time
    }

    client = _get_redis_client()
    if client:
        key = f"{FORM_PREFIX}{session_id}:{form_id}"
        client.setex(key, STORAGE_TTL, json.dumps(form_data))
        tool_logger.info(f"Form saved to Redis: {form_id[:8]}... ({len(normalized_fields)} fields)")
    else:
        tool_logger.warning(f"Form {form_id[:8]}... not saved - Redis unavailable")

    # Build response
    field_summary = {}
    for field in normalized_fields.values():
        ftype = field["type"]
        field_summary[ftype] = field_summary.get(ftype, 0) + 1

    type_parts = [f"{count} {ftype}" for ftype, count in field_summary.items()]
    type_str = ", ".join(type_parts) if type_parts else "no fields"

    response_text = (
        f"✓ Form registered: **{form_type}**\n\n"
        f"- Form ID: `{form_id}`\n"
        f"- Pages: {page_count}\n"
        f"- Fields: {len(normalized_fields)} ({type_str})\n\n"
        f"**Fields detected:**\n"
    )

    for field in list(normalized_fields.values())[:10]:  # Show first 10
        required = " *" if field["required"] else ""
        response_text += f"- {field['label']}{required} ({field['type']})\n"

    if len(normalized_fields) > 10:
        response_text += f"- ... and {len(normalized_fields) - 10} more\n"

    response_text += (
        "\nReady to fill! You can:\n"
        "- Tell me the values for each field\n"
        "- Use `update_fields` to set multiple values\n"
        "- Use `get_form_summary` to see current status"
    )

    return CallToolResult(content=[TextContent(type="text", text=response_text)])
