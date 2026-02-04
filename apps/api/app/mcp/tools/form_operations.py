"""
Form Operations Tool Handlers.

Handles field updates and form status queries.
Works with metadata only - no actual PDF manipulation until export.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any

from mcp.types import CallToolResult, TextContent

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
STORAGE_TTL = 3600


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


async def _save_form(session_id: str, form_data: dict[str, Any]) -> None:
    """Save form data to Redis."""
    client = _get_redis_client()
    if client:
        key = f"{FORM_PREFIX}{session_id}:{form_data['id']}"
        client.setex(key, STORAGE_TTL, json.dumps(form_data))


async def handle_update_fields(arguments: dict[str, Any]) -> CallToolResult:
    """
    Update field values in a registered form.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the registered form
            - values: Dict of field_name/field_id -> value

    Returns:
        CallToolResult with update confirmation
    """
    form_id = arguments.get("form_id")
    values = arguments.get("values", {})

    if not form_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: form_id is required")]
        )

    if not values:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: values dict is required")]
        )

    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No active session")]
        )

    form_data = await _get_form(session["id"], form_id)
    if not form_data:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Form not found")]
        )

    fields = form_data.get("fields", {})
    updated = []
    not_found = []

    for key, value in values.items():
        # Try to find field by ID or name
        field = None
        for f in fields.values():
            if f["id"] == key or f["name"] == key or f["label"] == key:
                field = f
                break

        if field:
            field["value"] = value
            field["updated_at"] = datetime.now(timezone.utc).isoformat()
            updated.append(field["label"] or field["name"])
        else:
            not_found.append(key)

    form_data["fields"] = fields
    form_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _save_form(session["id"], form_data)

    # Build response
    response_text = f"✓ Updated {len(updated)} field(s):\n"
    for name in updated:
        response_text += f"- {name}\n"

    if not_found:
        response_text += f"\n⚠️ Fields not found: {', '.join(not_found)}"

    # Show progress
    filled_count = sum(1 for f in fields.values() if f.get("value") is not None)
    total_count = len(fields)
    response_text += f"\n\nProgress: {filled_count}/{total_count} fields filled"

    return CallToolResult(
        content=[TextContent(type="text", text=response_text)]
    )


async def handle_get_form_summary(arguments: dict[str, Any]) -> CallToolResult:
    """
    Get current form status and field values.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the registered form
            - show_empty_only: If true, only show unfilled fields

    Returns:
        CallToolResult with form summary
    """
    form_id = arguments.get("form_id")
    show_empty_only = arguments.get("show_empty_only", False)

    if not form_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: form_id is required")]
        )

    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No active session")]
        )

    form_data = await _get_form(session["id"], form_id)
    if not form_data:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Form not found")]
        )

    fields = form_data.get("fields", {})
    form_type = form_data.get("form_type", "Unknown")

    filled = []
    empty = []
    required_empty = []

    for field in fields.values():
        value = field.get("value")
        label = field.get("label") or field.get("name")
        required = field.get("required", False)

        if value is not None and value != "":
            filled.append({"label": label, "value": value})
        else:
            empty.append({"label": label, "required": required})
            if required:
                required_empty.append(label)

    # Build response
    response_text = f"📋 **{form_type}** (Form ID: `{form_id}`)\n\n"

    if not show_empty_only and filled:
        response_text += "**Filled fields:**\n"
        for f in filled:
            val = f["value"]
            # Truncate long values
            if isinstance(val, str) and len(val) > 50:
                val = val[:47] + "..."
            response_text += f"✓ {f['label']}: {val}\n"
        response_text += "\n"

    if empty:
        response_text += "**Empty fields:**\n"
        for f in empty:
            marker = "* " if f["required"] else ""
            response_text += f"○ {marker}{f['label']}\n"
        response_text += "\n"

    # Summary
    total = len(fields)
    filled_count = len(filled)
    progress_pct = int(filled_count / total * 100) if total > 0 else 0

    response_text += f"**Progress:** {filled_count}/{total} ({progress_pct}%)\n"

    if required_empty:
        response_text += f"⚠️ **Required fields remaining:** {len(required_empty)}\n"

    if filled_count == total:
        response_text += "\n✅ All fields filled! Ready to export."

    return CallToolResult(
        content=[TextContent(type="text", text=response_text)]
    )


async def handle_list_forms(arguments: dict[str, Any]) -> CallToolResult:
    """
    List all registered forms in the current session.

    Returns:
        CallToolResult with list of forms
    """
    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No active session")]
        )

    client = _get_redis_client()
    if not client:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Storage unavailable")]
        )

    # Find all forms for this session
    pattern = f"{FORM_PREFIX}{session['id']}:*"
    forms = []

    cursor = 0
    while True:
        cursor, keys = client.scan(cursor, match=pattern, count=100)
        for key in keys:
            data = client.get(key)
            if data:
                form = json.loads(data)
                fields = form.get("fields", {})
                filled = sum(1 for f in fields.values() if f.get("value") is not None)
                forms.append({
                    "id": form["id"],
                    "type": form.get("form_type", "Unknown"),
                    "filled": filled,
                    "total": len(fields),
                })
        if cursor == 0:
            break

    if not forms:
        return CallToolResult(
            content=[TextContent(
                type="text",
                text="No forms registered yet. Attach a PDF and I'll analyze it."
            )]
        )

    response_text = "**Registered forms:**\n\n"
    for form in forms:
        pct = int(form["filled"] / form["total"] * 100) if form["total"] > 0 else 0
        response_text += (
            f"- **{form['type']}** (`{form['id'][:8]}...`)\n"
            f"  Progress: {form['filled']}/{form['total']} ({pct}%)\n"
        )

    return CallToolResult(
        content=[TextContent(type="text", text=response_text)]
    )
