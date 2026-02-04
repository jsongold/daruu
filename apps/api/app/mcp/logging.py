"""
MCP Logging Configuration.

Provides consistent logging across all MCP tools and server components.
Logs to stderr for visibility in Docker and Claude Desktop.
"""

import logging
import sys
from typing import Any


def setup_mcp_logger(name: str = "mcp") -> logging.Logger:
    """
    Set up a logger for MCP components.

    Logs to stderr with timestamp and level for easy debugging.
    """
    logger = logging.getLogger(name)

    # Only add handler if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # Create stderr handler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)

        # Format with timestamp and component name
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Pre-configured loggers for each component
server_logger = setup_mcp_logger("mcp.server")
tool_logger = setup_mcp_logger("mcp.tools")
session_logger = setup_mcp_logger("mcp.session")
storage_logger = setup_mcp_logger("mcp.storage")


def log_tool_call(tool_name: str, arguments: dict[str, Any]) -> None:
    """Log an incoming tool call with its arguments."""
    # Truncate large values for readability
    safe_args = {}
    for key, value in arguments.items():
        if isinstance(value, str) and len(value) > 100:
            safe_args[key] = f"{value[:100]}... ({len(value)} chars)"
        elif isinstance(value, list) and len(value) > 5:
            safe_args[key] = f"[{len(value)} items]"
        else:
            safe_args[key] = value

    tool_logger.info(f">>> {tool_name} called with: {safe_args}")


def log_tool_result(tool_name: str, success: bool, message: str = "") -> None:
    """Log the result of a tool call."""
    if success:
        tool_logger.info(f"<<< {tool_name} completed: {message}")
    else:
        tool_logger.error(f"<<< {tool_name} FAILED: {message}")


def log_session_event(event: str, session_id: str, details: str = "") -> None:
    """Log session-related events."""
    session_logger.info(f"{event} [session={session_id[:8]}...] {details}")


def log_storage_event(event: str, key: str, details: str = "") -> None:
    """Log storage operations."""
    storage_logger.debug(f"{event} [key={key}] {details}")
