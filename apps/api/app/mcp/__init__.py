"""
MCP (Model Context Protocol) Server Module.

This module provides MCP server functionality for Claude host integration,
implementing the two-frontend strategy where Claude acts as the conversation
host while our SaaS handles auth, billing, and data operations.

Reference: https://modelcontextprotocol.io/
"""

from app.mcp.server import create_mcp_server, run_mcp_server

__all__ = ["create_mcp_server", "run_mcp_server"]
