"""
validate_document Tool Handler.

Validates a form for completeness and correctness.
Returns list of validation errors and warnings.
"""

from typing import Any

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle validate_document tool call.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form to validate

    Returns:
        CallToolResult with validation results
    """
    form_id = arguments.get("form_id")

    if not form_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: form_id is required")]
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

        validation_result = await _validate_form(form)

        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])
        is_valid = validation_result.get("is_valid", False)

        # Build response
        lines = []

        if is_valid:
            lines.append("✓ **Form is valid and ready for export**\n")

            if warnings:
                lines.append(f"⚠️ {len(warnings)} warning(s):\n")
                for warning in warnings:
                    lines.append(f"- {warning['message']}")
        else:
            lines.append(f"✗ **Form has {len(errors)} validation error(s)**\n")

            for error in errors:
                field_name = error.get("field_name", "Unknown field")
                message = error.get("message", "Invalid value")
                lines.append(f"- **{field_name}**: {message}")

            if warnings:
                lines.append(f"\n⚠️ Additionally, {len(warnings)} warning(s):\n")
                for warning in warnings:
                    lines.append(f"- {warning['message']}")

        # Summary
        total_fields = form.get("field_count", 0)
        filled_fields = validation_result.get("filled_count", 0)
        lines.append(f"\n---\n**Summary**: {filled_fields}/{total_fields} fields filled")

        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(lines))]
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error validating form: {str(e)}")]
        )


async def _validate_form(form: dict[str, Any]) -> dict[str, Any]:
    """
    Perform form validation.

    Checks:
    - Required fields are filled
    - Field values match expected types
    - Field values pass any defined rules
    - Low-confidence values are flagged

    Returns:
        Dict with:
            - is_valid: bool
            - errors: list of error objects
            - warnings: list of warning objects
            - filled_count: number of filled fields
    """
    fields = form.get("fields", {})
    errors = []
    warnings = []
    filled_count = 0

    for field_id, field_info in fields.items():
        field_name = field_info.get("name", field_id)
        field_type = field_info.get("type", "text")
        value = field_info.get("value")
        is_required = field_info.get("required", False)
        confidence = field_info.get("confidence", 1.0)

        # Track filled fields
        if value is not None and value != "":
            filled_count += 1

        # Check required fields
        if is_required and (value is None or value == ""):
            errors.append({
                "field_id": field_id,
                "field_name": field_name,
                "message": "This field is required",
                "type": "required",
            })
            continue

        # Skip further validation if empty
        if value is None or value == "":
            continue

        # Type-specific validation
        if field_type == "checkbox":
            if not isinstance(value, bool):
                errors.append({
                    "field_id": field_id,
                    "field_name": field_name,
                    "message": "Expected checkbox value (true/false)",
                    "type": "type_mismatch",
                })

        elif field_type == "number":
            try:
                float(value)
            except (ValueError, TypeError):
                errors.append({
                    "field_id": field_id,
                    "field_name": field_name,
                    "message": "Expected numeric value",
                    "type": "type_mismatch",
                })

        elif field_type == "date":
            import re
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(value)):
                errors.append({
                    "field_id": field_id,
                    "field_name": field_name,
                    "message": "Expected date in YYYY-MM-DD format",
                    "type": "format",
                })

        elif field_type in ("radio", "dropdown", "select"):
            options = field_info.get("options", [])
            if options and value not in options:
                errors.append({
                    "field_id": field_id,
                    "field_name": field_name,
                    "message": f"Value must be one of: {', '.join(options)}",
                    "type": "invalid_option",
                })

        # Check for low confidence values
        if confidence < 0.7:
            warnings.append({
                "field_id": field_id,
                "field_name": field_name,
                "message": f"'{field_name}' has low extraction confidence - please verify",
                "type": "low_confidence",
            })

        # Check max length
        max_length = field_info.get("max_length")
        if max_length and isinstance(value, str) and len(value) > max_length:
            errors.append({
                "field_id": field_id,
                "field_name": field_name,
                "message": f"Value exceeds maximum length of {max_length} characters",
                "type": "max_length",
            })

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "filled_count": filled_count,
    }
