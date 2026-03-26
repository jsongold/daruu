"""
get_fields Tool Handler.

Returns all fields from a form with their current values,
types, and validation status.
"""

from typing import Any

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle get_fields tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - filter_empty: Only return empty fields (default: False)
            - filter_page: Only return fields from this page

    Returns:
        CallToolResult with field list
    """
    form_id = arguments.get("form_id")
    filter_empty = arguments.get("filter_empty", False)
    filter_page = arguments.get("filter_page")

    if not form_id:
        return CallToolResult(content=[TextContent(type="text", text="Error: form_id is required")])

    session = await get_current_session()
    if not session:
        return CallToolResult(content=[TextContent(type="text", text="Error: No active session")])

    storage = MCPStorage()

    try:
        form = await storage.get_form(session["id"], form_id)
        if not form:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Form not found: {form_id}")]
            )

        fields = form.get("fields", {})
        result_fields = []

        for field_id, field_info in fields.items():
            # Apply filters
            if filter_empty and field_info.get("value") is not None:
                continue

            if filter_page is not None and field_info.get("page", 1) != filter_page:
                continue

            result_fields.append(
                {
                    "id": field_id,
                    **field_info,
                }
            )

        # Sort by page, then by position
        result_fields.sort(
            key=lambda f: (
                f.get("page", 1),
                f.get("bbox", [0, 0, 0, 0])[1] if f.get("bbox") else 0,
            )
        )

        # Format output
        if not result_fields:
            if filter_empty:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="All fields are filled! Ready to export.")
                    ]
                )
            return CallToolResult(
                content=[TextContent(type="text", text="No fields found in this form.")]
            )

        # Build response text
        lines = []

        if filter_empty:
            lines.append(f"**{len(result_fields)} empty fields:**\n")
        elif filter_page:
            lines.append(f"**{len(result_fields)} fields on page {filter_page}:**\n")
        else:
            filled = sum(1 for f in result_fields if f.get("value") is not None)
            lines.append(f"**{len(result_fields)} fields** ({filled} filled):\n")

        # Group by page if showing all
        current_page = None

        for field in result_fields:
            page = field.get("page", 1)
            if current_page != page and filter_page is None:
                current_page = page
                lines.append(f"\n**Page {page}:**")

            field_id = field["id"]
            name = field.get("name", field_id)
            ftype = field.get("type", "text")
            value = field.get("value")
            confidence = field.get("confidence", 1.0)
            source = field.get("source", "")

            # Format value
            if value is None:
                value_str = "_(empty)_"
            elif ftype == "checkbox":
                value_str = "✓" if value else "☐"
            elif isinstance(value, str) and len(value) > 30:
                value_str = f'"{value[:27]}..."'
            else:
                value_str = f'"{value}"' if isinstance(value, str) else str(value)

            # Add confidence indicator for extracted values
            conf_str = ""
            if source == "extracted" and confidence < 0.7:
                conf_str = " ⚠️"
            elif source == "user":
                conf_str = " ✓"

            lines.append(f"- **{name}** [{ftype}]: {value_str}{conf_str}")

        return CallToolResult(content=[TextContent(type="text", text="\n".join(lines))])

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error getting fields: {str(e)}")]
        )
