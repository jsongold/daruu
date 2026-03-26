"""
Visual Editing Tool Handlers.

Tools for visual editing workflow inside Claude:
- visual_edit_field: Get field info + focused preview for editing
- get_form_visual_summary: Get text summary + color-coded preview image

These tools combine text and image content for an enhanced
in-Claude PDF editing experience.
"""

import base64
from typing import Any

from mcp.types import CallToolResult, ImageContent, TextContent

from app.mcp.session import get_current_session
from app.mcp.storage import MCPStorage
from app.mcp.tools.render_preview import _render_page

# Instructions for different field types
FIELD_TYPE_INSTRUCTIONS = {
    "text": "Enter the text value for this field.",
    "date": "Enter the date in MM/DD/YYYY format.",
    "checkbox": "Enter 'true' to check or 'false' to uncheck.",
    "radio": "Select one of the available options.",
    "dropdown": "Select one of the available options listed below.",
    "signature": "This field requires a signature. Enter 'signed' to mark as signed.",
    "number": "Enter a numeric value.",
    "email": "Enter a valid email address.",
    "phone": "Enter a phone number (e.g., 555-123-4567).",
    "ssn": "Enter Social Security Number (XXX-XX-XXXX format).",
    "ein": "Enter Employer Identification Number (XX-XXXXXXX format).",
}


async def handle_visual_edit_field(arguments: dict[str, Any]) -> CallToolResult:
    """
    Get a visual preview focused on a specific field for editing.

    Combines field information with a preview image showing the field
    highlighted in yellow (active state) for easy visual identification.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - field_id: ID or name of the field to edit

    Returns:
        CallToolResult with:
            - TextContent: Field info and editing instructions
            - ImageContent: Preview with field highlighted
    """
    form_id = arguments.get("form_id")
    field_id = arguments.get("field_id")

    if not form_id:
        return CallToolResult(content=[TextContent(type="text", text="Error: form_id is required")])

    if not field_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: field_id is required")]
        )

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

        # Find the field by ID or name
        target_field = None
        target_field_id = None

        for fid, finfo in fields.items():
            if fid == field_id or finfo.get("name") == field_id or finfo.get("label") == field_id:
                target_field = finfo
                target_field_id = fid
                break

        if not target_field:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: Field not found: {field_id}")]
            )

        # Get field info
        field_name = target_field.get("name", "Unknown")
        field_label = target_field.get("label") or field_name
        field_type = target_field.get("type", "text")
        current_value = target_field.get("value")
        is_required = target_field.get("required", False)
        options = target_field.get("options")
        page = target_field.get("page", 1)

        # Build field info text
        info_lines = [
            f"**Field: {field_label}**",
            "",
            f"- Type: {field_type}",
            f"- Required: {'Yes' if is_required else 'No'}",
            f"- Page: {page}",
        ]

        if current_value is not None and current_value != "":
            info_lines.append(f"- Current value: {current_value}")
        else:
            info_lines.append("- Current value: (empty)")

        if options:
            info_lines.append("")
            info_lines.append("**Available options:**")
            for opt in options:
                info_lines.append(f"  - {opt}")

        # Add instructions
        info_lines.append("")
        instructions = FIELD_TYPE_INSTRUCTIONS.get(field_type, FIELD_TYPE_INSTRUCTIONS["text"])
        info_lines.append(f"**Instructions:** {instructions}")

        # Render preview with this field highlighted
        image_bytes, mime_type = await _render_page(
            form=form,
            page=page,
            zoom=1.5,
            highlight_mode="single",
            highlight_field_id=target_field_id,
            show_values=True,
        )

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        return CallToolResult(
            content=[
                TextContent(type="text", text="\n".join(info_lines)),
                ImageContent(
                    type="image",
                    data=image_b64,
                    mimeType=mime_type,
                ),
            ]
        )

    except Exception as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {str(e)}")])


async def handle_get_form_visual_summary(arguments: dict[str, Any]) -> CallToolResult:
    """
    Get both text summary AND preview image for a form.

    Returns comprehensive form status with a color-coded visual preview
    showing which fields are filled (green), empty required (red),
    and empty optional (gray).

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - page: Page number (default: 1)

    Returns:
        CallToolResult with:
            - TextContent: Progress summary and field list
            - ImageContent: Color-coded preview of the page
    """
    form_id = arguments.get("form_id")
    page = arguments.get("page", 1)

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
        form_type = form.get("form_type", "Unknown Form")
        page_count = form.get("page_count", 1)

        # Categorize fields
        filled_fields = []
        empty_required = []
        empty_optional = []

        for fid, finfo in fields.items():
            label = finfo.get("label") or finfo.get("name", "Unknown")
            value = finfo.get("value")
            required = finfo.get("required", False)
            field_page = finfo.get("page", 1)

            if value is not None and value != "":
                filled_fields.append(
                    {
                        "label": label,
                        "value": value,
                        "page": field_page,
                    }
                )
            elif required:
                empty_required.append(
                    {
                        "label": label,
                        "page": field_page,
                    }
                )
            else:
                empty_optional.append(
                    {
                        "label": label,
                        "page": field_page,
                    }
                )

        total_fields = len(fields)
        filled_count = len(filled_fields)
        progress_pct = int((filled_count / total_fields) * 100) if total_fields > 0 else 0

        # Build summary text
        summary_lines = [
            f"**{form_type}**",
            "",
            f"**Progress: {filled_count}/{total_fields} fields filled ({progress_pct}%)**",
            "",
        ]

        # Color legend
        summary_lines.extend(
            [
                "**Legend:**",
                "- Green outline = Filled",
                "- Red outline = Empty (required)",
                "- Gray outline = Empty (optional)",
                "",
            ]
        )

        # Fields on current page
        page_fields = [f for f in fields.values() if f.get("page", 1) == page]

        if page_fields:
            summary_lines.append(f"**Fields on page {page}:**")
            for finfo in page_fields:
                label = finfo.get("label") or finfo.get("name", "Unknown")
                value = finfo.get("value")
                required = finfo.get("required", False)

                if value is not None and value != "":
                    # Truncate long values
                    val_str = str(value)
                    if len(val_str) > 30:
                        val_str = val_str[:27] + "..."
                    summary_lines.append(f"  [FILLED] {label}: {val_str}")
                elif required:
                    summary_lines.append(f"  [REQUIRED] {label}")
                else:
                    summary_lines.append(f"  [optional] {label}")
            summary_lines.append("")

        # Overall status
        if empty_required:
            summary_lines.append(f"**Required fields remaining:** {len(empty_required)}")
            # List first few required fields
            for f in empty_required[:5]:
                summary_lines.append(f"  - {f['label']} (page {f['page']})")
            if len(empty_required) > 5:
                summary_lines.append(f"  - ...and {len(empty_required) - 5} more")
        else:
            summary_lines.append("All required fields are filled!")

        if filled_count == total_fields:
            summary_lines.append("")
            summary_lines.append("All fields complete. Ready to export!")

        # Render preview with all fields color-coded
        image_bytes, mime_type = await _render_page(
            form=form,
            page=page,
            zoom=1.5,
            highlight_mode="all",
            highlight_field_id=None,
            show_values=True,
        )

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Add page navigation hint
        if page_count > 1:
            summary_lines.append("")
            summary_lines.append(f"Page {page} of {page_count}")
            summary_lines.append("Use `page` parameter to view other pages.")

        return CallToolResult(
            content=[
                TextContent(type="text", text="\n".join(summary_lines)),
                ImageContent(
                    type="image",
                    data=image_b64,
                    mimeType=mime_type,
                ),
            ]
        )

    except Exception as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {str(e)}")])


async def handle_get_next_unfilled_field(arguments: dict[str, Any]) -> CallToolResult:
    """
    Get the next unfilled field and its visual preview.

    Useful for guided form filling - returns the first empty field
    (prioritizing required fields) with instructions and a focused preview.

    Args:
        arguments: Tool arguments containing:
            - form_id: ID of the form
            - skip_optional: If true, only return required empty fields

    Returns:
        CallToolResult with field info and preview, or message if all filled
    """
    form_id = arguments.get("form_id")
    skip_optional = arguments.get("skip_optional", False)

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

        # Find empty fields, prioritizing required ones
        empty_required = []
        empty_optional = []

        for fid, finfo in fields.items():
            value = finfo.get("value")
            if value is None or value == "":
                if finfo.get("required", False):
                    empty_required.append((fid, finfo))
                else:
                    empty_optional.append((fid, finfo))

        # Sort by page number, then by field order (if available)
        empty_required.sort(key=lambda x: (x[1].get("page", 1), x[1].get("order", 0)))
        empty_optional.sort(key=lambda x: (x[1].get("page", 1), x[1].get("order", 0)))

        # Get next field
        if empty_required:
            next_field_id, next_field = empty_required[0]
        elif not skip_optional and empty_optional:
            next_field_id, next_field = empty_optional[0]
        else:
            # All fields are filled
            filled_count = len(fields)
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"All {'required ' if skip_optional else ''}fields are filled! "
                        f"({filled_count} total fields)\n\n"
                        f"Ready to export the form.",
                    )
                ]
            )

        # Build response using visual_edit_field logic
        return await handle_visual_edit_field(
            {
                "form_id": form_id,
                "field_id": next_field_id,
            }
        )

    except Exception as e:
        return CallToolResult(content=[TextContent(type="text", text=f"Error: {str(e)}")])
