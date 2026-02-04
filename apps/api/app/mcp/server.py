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

from app.mcp.tools import register_form, form_operations, export_pdf
from app.mcp.session import set_current_session


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
    print(f"MCP Session created: {session_id}", file=sys.stderr)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available MCP tools."""
        return [
            Tool(
                name="register_form",
                description=(
                    "Register a PDF form that you've analyzed visually. "
                    "Extract field names, types, and positions from the attached PDF, "
                    "then call this to register them. Do NOT send file data - just the metadata."
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
                    "which are empty, and overall progress."
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
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        """Handle tool calls."""
        print(f"Tool called: {name}", file=sys.stderr)

        # Ensure session is set for this tool call
        set_current_session(session)

        handlers: dict[str, Any] = {
            "register_form": register_form.handle,
            "update_fields": form_operations.handle_update_fields,
            "get_form_summary": form_operations.handle_get_form_summary,
            "list_forms": form_operations.handle_list_forms,
            "export_pdf": export_pdf.handle,
        }

        handler = handlers.get(name)
        if not handler:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")]
            )

        try:
            result = await handler(arguments)
            print(f"Tool {name} completed successfully", file=sys.stderr)
            return result
        except Exception as e:
            import traceback
            print(f"Tool {name} error: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
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
