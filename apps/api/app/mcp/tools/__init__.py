"""
MCP Tool Handlers.

Vision-First Architecture:
- register_form: Register form from Claude's visual analysis
- form_operations: Update fields, get summary, list forms
- export_pdf: Export with source file

Each tool module provides handler functions that process arguments
and return CallToolResult.
"""

from app.mcp.tools import (
    register_form,
    form_operations,
    export_pdf,
)

__all__ = [
    "register_form",
    "form_operations",
    "export_pdf",
]
