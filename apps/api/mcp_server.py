#!/usr/bin/env python3
"""
MCP Server Entry Point.

This script runs the Daru PDF MCP server for Claude integration.
The server communicates over stdio using the MCP protocol.

Usage:
    python mcp_server.py

Or configure in Claude Desktop config:
    {
        "mcpServers": {
            "daru-pdf": {
                "command": "python",
                "args": ["/path/to/apps/api/mcp_server.py"],
                "env": {
                    "SUPABASE_URL": "your-supabase-url",
                    "SUPABASE_SERVICE_KEY": "your-service-key"
                }
            }
        }
    }
"""

import sys
from pathlib import Path

# Add the app directory to the path
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

from app.mcp import run_mcp_server

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_mcp_server())
