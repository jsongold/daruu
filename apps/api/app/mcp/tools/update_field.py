"""
update_field Tool Handler.

Updates a single form field value.
Supports text, checkbox, radio, and dropdown fields.
"""

from typing import Any

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle update_field tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - field_id: ID of the field to update
            - value: New value (string, bool, number, or null)

    Returns:
        CallToolResult confirming the update
    """
    form_id = arguments.get("form_id")
    field_id = arguments.get("field_id")
    value = arguments.get("value")

    if not form_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: form_id is required")]
        )

    if not field_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: field_id is required")]
        )

    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No active session")]
        )

    storage = MCPStorage()

    try:
        form = await storage.get_form(session["id"], form_id)
        if not form:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Form not found: {form_id}")]
            )

        fields = form.get("fields", {})
        if field_id not in fields:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Field not found: {field_id}")]
            )

        field_info = fields[field_id]
        field_name = field_info.get("name", field_id)
        field_type = field_info.get("type", "text")
        old_value = field_info.get("value")

        # Validate value based on field type
        validation_result = _validate_value(value, field_type, field_info)
        if not validation_result["valid"]:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"Error: {validation_result['error']}"
                )]
            )

        # Update the field
        fields[field_id]["value"] = value
        fields[field_id]["source"] = "user"  # Mark as user-edited
        fields[field_id]["confidence"] = 1.0  # User values have full confidence

        await storage.update_form_fields(
            session_id=session["id"],
            form_id=form_id,
            fields=fields,
        )

        # Format response
        display_value = _format_value_for_display(value, field_type)
        response_text = f"✓ Updated **{field_name}**: {display_value}"

        if old_value is not None and old_value != value:
            old_display = _format_value_for_display(old_value, field_type)
            response_text += f" (was: {old_display})"

        return CallToolResult(
            content=[TextContent(type="text", text=response_text)]
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error updating field: {str(e)}")]
        )


def _validate_value(
    value: Any,
    field_type: str,
    field_info: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate a value against field type and constraints.

    Returns:
        Dict with 'valid' bool and optional 'error' message
    """
    # Allow null to clear field
    if value is None:
        return {"valid": True}

    # Type-specific validation
    if field_type == "checkbox":
        if not isinstance(value, bool):
            return {"valid": False, "error": "Checkbox value must be true or false"}

    elif field_type == "radio":
        options = field_info.get("options", [])
        if options and value not in options:
            return {
                "valid": False,
                "error": f"Value must be one of: {', '.join(options)}",
            }

    elif field_type == "dropdown" or field_type == "select":
        options = field_info.get("options", [])
        if options and value not in options:
            return {
                "valid": False,
                "error": f"Value must be one of: {', '.join(options)}",
            }

    elif field_type == "number":
        try:
            float(value)
        except (ValueError, TypeError):
            return {"valid": False, "error": "Value must be a number"}

    elif field_type == "date":
        # Basic date format validation
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
            return {"valid": False, "error": "Date must be in YYYY-MM-DD format"}

    # Check max length if specified
    max_length = field_info.get("max_length")
    if max_length and isinstance(value, str) and len(value) > max_length:
        return {"valid": False, "error": f"Value exceeds max length of {max_length}"}

    return {"valid": True}


def _format_value_for_display(value: Any, field_type: str) -> str:
    """Format a value for display in the response."""
    if value is None:
        return "(empty)"

    if field_type == "checkbox":
        return "✓ checked" if value else "☐ unchecked"

    if isinstance(value, str):
        if len(value) > 50:
            return f'"{value[:47]}..."'
        return f'"{value}"'

    return str(value)
