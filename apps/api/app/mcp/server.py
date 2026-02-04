"""
MCP Server Implementation.

Vision-First Architecture:
- Claude reads PDFs visually (native multimodal)
- MCP receives only metadata (small tokens)
- No large file data through MCP

Tools:
- register_form: Register form Claude analyzed visually
- update_fields: Set field values
- get_form_summary: Get current form status
- list_forms: List all registered forms
- export_pdf: Export with source file (URL or re-attachment)
- render_preview: Render PDF page with field highlights
- visual_edit_field: Get field info + focused preview
- get_form_visual_summary: Get text summary + color-coded preview
- get_next_unfilled_field: Get next empty field for guided filling
"""

import asyncio
import sys
from typing import Any
from uuid import uuid4

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolResult,
)

from app.mcp.tools import register_form, form_operations, export_pdf, render_preview
from app.mcp.tools import visual_editing
from app.mcp.session import set_current_session
from app.mcp.logging import server_logger, log_tool_call, log_tool_result


def create_mcp_server() -> Server:
    """Create and configure the MCP server with all tools."""
    server = Server("daru-pdf-mcp")

    # Create a persistent session for this MCP server instance
    session_id = str(uuid4())
    session = {
        "id": session_id,
        "user_id": None,
        "linked": False,
    }
    set_current_session(session)
    server_logger.info(f"MCP Server started - Session: {session_id}")
    server_logger.info("Available tools: register_form, add_fields, update_fields, get_form_summary, list_forms, export_pdf, render_preview, visual_edit_field, get_form_visual_summary, get_next_unfilled_field")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available MCP tools."""
        return [
            Tool(
                name="register_form",
                description=(
                    "Register a PDF form. If the form has MANY fields (>20), "
                    "call this multiple times - first with form_type and first batch of fields, "
                    "then use add_fields to add more. Do NOT send file data."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_type": {
                            "type": "string",
                            "description": "Type of form (e.g., 'W-9', '1040', 'Application')",
                        },
                        "fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Field identifier"},
                                    "label": {"type": "string", "description": "Human-readable label"},
                                    "type": {
                                        "type": "string",
                                        "enum": ["text", "checkbox", "radio", "dropdown", "date", "signature"],
                                    },
                                    "page": {"type": "integer", "description": "Page number (1-indexed)"},
                                    "required": {"type": "boolean"},
                                    "options": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "description": "Options for dropdown/radio fields",
                                    },
                                    "position": {
                                        "type": "object",
                                        "properties": {
                                            "description": {"type": "string"},
                                            "y_percent": {"type": "number"},
                                            "x_percent": {"type": "number"},
                                        },
                                    },
                                },
                                "required": ["name", "type"],
                            },
                            "description": "List of fields extracted from visual analysis",
                        },
                        "page_count": {
                            "type": "integer",
                            "description": "Number of pages in the form",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Optional additional metadata",
                        },
                    },
                    "required": ["form_type", "fields"],
                },
            ),
            Tool(
                name="add_fields",
                description=(
                    "Add more fields to an existing registered form. "
                    "Use this when a form has many fields - register first batch with register_form, "
                    "then add remaining fields in batches of 15-20 using this tool."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the registered form",
                        },
                        "fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "label": {"type": "string"},
                                    "type": {"type": "string"},
                                    "page": {"type": "integer"},
                                },
                                "required": ["name", "type"],
                            },
                            "description": "Additional fields to add",
                        },
                    },
                    "required": ["form_id", "fields"],
                },
            ),
            Tool(
                name="update_fields",
                description=(
                    "Update field values in a registered form. "
                    "Pass a dictionary of field names to values."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the registered form",
                        },
                        "values": {
                            "type": "object",
                            "description": "Dictionary of field_name -> value",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["form_id", "values"],
                },
            ),
            Tool(
                name="get_form_summary",
                description=(
                    "Get the current status of a form - which fields are filled, "
                    "which are empty, and overall progress. Text only."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the registered form",
                        },
                        "show_empty_only": {
                            "type": "boolean",
                            "description": "Only show unfilled fields",
                            "default": False,
                        },
                    },
                    "required": ["form_id"],
                },
            ),
            Tool(
                name="list_forms",
                description="List all forms registered in this session.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="export_pdf",
                description=(
                    "Export the filled form as a PDF. You'll need the original PDF - "
                    "either provide a URL to it or ask the user to re-attach it."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the form to export",
                        },
                        "source_url": {
                            "type": "string",
                            "description": "URL to the original PDF (Google Drive, Dropbox, etc.)",
                        },
                        "source_data": {
                            "type": "string",
                            "description": "Base64-encoded PDF if user re-attached it",
                        },
                        "flatten": {
                            "type": "boolean",
                            "description": "Flatten form fields (make non-editable)",
                            "default": False,
                        },
                    },
                    "required": ["form_id"],
                },
            ),
            # Visual editing tools
            Tool(
                name="render_preview",
                description=(
                    "Render a PDF page as an image with field highlights and filled values. "
                    "Returns an image showing fields color-coded by status: "
                    "yellow=active, green=filled, red=empty required, gray=empty optional."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the form to preview",
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number (1-indexed)",
                            "default": 1,
                        },
                        "zoom": {
                            "type": "number",
                            "description": "Zoom level (1.0 = 100%, 1.5 = 150%)",
                            "default": 1.5,
                        },
                        "highlight_mode": {
                            "type": "string",
                            "enum": ["all", "empty", "filled", "single"],
                            "description": (
                                "Which fields to highlight: "
                                "'all' = all fields, 'empty' = only empty, "
                                "'filled' = only filled, 'single' = specific field"
                            ),
                            "default": "all",
                        },
                        "highlight_field_id": {
                            "type": "string",
                            "description": "Field ID to highlight (when mode is 'single')",
                        },
                        "show_values": {
                            "type": "boolean",
                            "description": "Overlay filled values on the image",
                            "default": True,
                        },
                    },
                    "required": ["form_id"],
                },
            ),
            Tool(
                name="visual_edit_field",
                description=(
                    "Get a visual preview focused on a specific field for editing. "
                    "Returns field info (name, type, current value, options) plus "
                    "a preview image with that field highlighted in yellow."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the form",
                        },
                        "field_id": {
                            "type": "string",
                            "description": "Field ID or name to edit",
                        },
                    },
                    "required": ["form_id", "field_id"],
                },
            ),
            Tool(
                name="get_form_visual_summary",
                description=(
                    "Get both text summary AND preview image for a form. "
                    "Shows progress, field status list, and a color-coded preview "
                    "showing filled (green), empty required (red), and optional (gray) fields."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the form",
                        },
                        "page": {
                            "type": "integer",
                            "description": "Page number to preview (1-indexed)",
                            "default": 1,
                        },
                    },
                    "required": ["form_id"],
                },
            ),
            Tool(
                name="get_next_unfilled_field",
                description=(
                    "Get the next unfilled field and its visual preview. "
                    "Useful for guided form filling - returns the first empty field "
                    "(prioritizing required fields) with instructions and a focused preview."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "form_id": {
                            "type": "string",
                            "description": "ID of the form",
                        },
                        "skip_optional": {
                            "type": "boolean",
                            "description": "If true, only return required empty fields",
                            "default": False,
                        },
                    },
                    "required": ["form_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Handle tool calls."""
        log_tool_call(name, arguments)

        # Ensure session is set for this tool call
        set_current_session(session)

        handlers: dict[str, Any] = {
            "register_form": register_form.handle,
            "add_fields": form_operations.handle_add_fields,
            "update_fields": form_operations.handle_update_fields,
            "get_form_summary": form_operations.handle_get_form_summary,
            "list_forms": form_operations.handle_list_forms,
            "export_pdf": export_pdf.handle,
            # Visual editing tools
            "render_preview": render_preview.handle,
            "visual_edit_field": visual_editing.handle_visual_edit_field,
            "get_form_visual_summary": visual_editing.handle_get_form_visual_summary,
            "get_next_unfilled_field": visual_editing.handle_get_next_unfilled_field,
        }

        handler = handlers.get(name)
        if not handler:
            log_tool_result(name, False, f"Unknown tool")
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")]
            )

        try:
            result = await handler(arguments)
            # Extract result summary for logging
            result_summary = ""
            if result.content:
                first_content = result.content[0]
                if hasattr(first_content, "text"):
                    text = first_content.text
                    result_summary = text[:100] + "..." if len(text) > 100 else text
                elif hasattr(first_content, "type") and first_content.type == "image":
                    result_summary = "[Image returned]"
            log_tool_result(name, True, result_summary)
            return result
        except Exception as e:
            import traceback
            log_tool_result(name, False, str(e))
            server_logger.error(traceback.format_exc())
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")]
            )

    return server


async def run_mcp_server() -> None:
    """Run the MCP server over stdio."""
    server = create_mcp_server()
    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)


def main() -> None:
    """Entry point for MCP server."""
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
