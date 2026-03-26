"""
upload_form Tool Handler.

Provides upload URLs for PDF forms (Y Pattern).
Files are uploaded via web UI, not through MCP.
"""

import json
import os
from typing import Any
from uuid import uuid4

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session


# Redis for tracking pending uploads
def _get_redis_client() -> Any:
    """Get Redis client."""
    try:
        import redis

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/2")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception:
        return None


UPLOAD_PREFIX = "mcp:upload:"
UPLOAD_TTL = 600  # 10 minutes for upload to complete


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle upload_form tool call.

    Returns an upload URL where user can upload their PDF via web UI.
    This avoids sending large base64 data through Claude's context.

    Args:
        arguments: Tool arguments (optional description)

    Returns:
        CallToolResult with upload URL
    """
    description = arguments.get("description", "PDF form")

    # Get current MCP session
    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[
                TextContent(
                    type="text", text="Error: No active session. Please start a new conversation."
                )
            ]
        )

    # Create upload token
    upload_id = str(uuid4())
    session_id = session["id"]

    # Store pending upload in Redis
    client = _get_redis_client()
    upload_data = {
        "id": upload_id,
        "session_id": session_id,
        "description": description,
        "status": "pending",
        "form_id": None,
    }

    if client:
        client.setex(
            f"{UPLOAD_PREFIX}{upload_id}",
            UPLOAD_TTL,
            json.dumps(upload_data),
        )

    # Generate upload URL
    app_url = os.environ.get("DARU_APP_URL", "http://localhost:5173")
    upload_url = f"{app_url}/upload/{upload_id}"

    response_text = (
        f"📄 **Upload your {description}**\n\n"
        f"Please upload your PDF using this link:\n"
        f"👉 {upload_url}\n\n"
        f"After uploading, I'll be able to:\n"
        f"- Detect form fields\n"
        f"- Auto-fill from your documents\n"
        f"- Help you complete the form\n\n"
        f"_Upload ID: `{upload_id}`_"
    )

    return CallToolResult(content=[TextContent(type="text", text=response_text)])


async def check_upload_status(arguments: dict[str, Any]) -> CallToolResult:
    """
    Check if a pending upload has been completed.

    Args:
        arguments: Tool arguments containing upload_id

    Returns:
        CallToolResult with upload status and form_id if complete
    """
    upload_id = arguments.get("upload_id")

    if not upload_id:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: upload_id is required")]
        )

    client = _get_redis_client()
    if not client:
        return CallToolResult(content=[TextContent(type="text", text="Error: Storage unavailable")])

    data = client.get(f"{UPLOAD_PREFIX}{upload_id}")
    if not data:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: Upload not found or expired")]
        )

    upload_data = json.loads(data)
    status = upload_data.get("status")
    form_id = upload_data.get("form_id")

    if status == "completed" and form_id:
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"✓ Upload complete!\n\n"
                        f"Form ID: `{form_id}`\n\n"
                        f"You can now use `get_fields`, `autofill_form`, "
                        f"or other tools with this form."
                    ),
                )
            ]
        )
    elif status == "pending":
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        "⏳ Waiting for upload...\n\n"
                        "The user hasn't uploaded a file yet. "
                        "Please wait for them to complete the upload."
                    ),
                )
            ]
        )
    else:
        return CallToolResult(content=[TextContent(type="text", text=f"Upload status: {status}")])


async def handle_source_docs(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle upload_source_docs tool call.

    Returns an upload URL for source documents.
    """
    session = await get_current_session()
    if not session:
        return CallToolResult(content=[TextContent(type="text", text="Error: No active session")])

    upload_id = str(uuid4())
    session_id = session["id"]

    client = _get_redis_client()
    upload_data = {
        "id": upload_id,
        "session_id": session_id,
        "type": "source_docs",
        "status": "pending",
        "doc_ids": [],
    }

    if client:
        client.setex(
            f"{UPLOAD_PREFIX}{upload_id}",
            UPLOAD_TTL,
            json.dumps(upload_data),
        )

    app_url = os.environ.get("DARU_APP_URL", "http://localhost:5173")
    upload_url = f"{app_url}/upload/{upload_id}?type=source"

    response_text = (
        f"📎 **Upload source documents**\n\n"
        f"Upload documents containing data to extract:\n"
        f"👉 {upload_url}\n\n"
        f"Supported formats: PDF, images, text files\n\n"
        f"_Upload ID: `{upload_id}`_"
    )

    return CallToolResult(content=[TextContent(type="text", text=response_text)])
