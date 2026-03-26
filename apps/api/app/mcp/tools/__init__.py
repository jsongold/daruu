"""
MCP Tool Handlers.

Vision-First Architecture:
- register_form: Register form from Claude's visual analysis
- form_operations: Update fields, get summary, list forms
- export_pdf: Export with source file
- render_preview: Render PDF with field highlights and value overlays
- visual_editing: Visual edit field, form summary with preview

Each tool module provides handler functions that process arguments
and return CallToolResult.
"""

from app.mcp.tools import (
    export_pdf,
    form_operations,
    register_form,
    render_preview,
    visual_editing,
)

__all__ = [
    "register_form",
    "form_operations",
    "export_pdf",
    "render_preview",
    "visual_editing",
]
