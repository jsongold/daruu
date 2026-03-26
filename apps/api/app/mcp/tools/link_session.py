"""
link_session Tool Handler.

Links a Claude MCP session to a Daru PDF SaaS user account.
Implements the Y Pattern where:
- If user is logged in (has valid Supabase session), auto-link
- If not logged in, return login URL
"""

from typing import Any

from mcp.types import CallToolResult, TextContent

from app.mcp.session import MCPSessionManager


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle link_session tool call.

    Args:
        arguments: Tool arguments containing:
            - session_token: The MCP session token from initial handshake

    Returns:
        CallToolResult with either:
            - Success message if auto-linked
            - Login URL if not logged in
            - Error message if token invalid
    """
    session_token = arguments.get("session_token")

    if not session_token:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: session_token is required")]
        )

    session_manager = MCPSessionManager()

    try:
        # Check if session token is valid and not expired
        session = await session_manager.get_session(session_token)

        if not session:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="Error: Invalid or expired session token. Please start a new session.",
                    )
                ]
            )

        # Check if already linked to a user
        if session.get("user_id"):
            user_id = session["user_id"]
            entitlements = await session_manager.get_user_entitlements(user_id)

            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=(
                            f"✓ Session linked to your account.\n"
                            f"Plan: {entitlements.get('plan', 'free')}\n"
                            f"Exports remaining: {entitlements.get('exports_remaining', 0)}"
                        ),
                    )
                ]
            )

        # Session exists but not linked - check for existing auth cookie
        # In Y Pattern, the MCP App UI would have the auth cookie
        # For now, return login URL
        login_url = await session_manager.get_login_url(session_token)

        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=(
                        f"🔒 Login required to save and export forms.\n\n"
                        f"You can continue filling the form, but to download "
                        f"the completed PDF, please log in:\n\n"
                        f"[Login to Daru PDF]({login_url})\n\n"
                        f"Once logged in, your session will be automatically linked."
                    ),
                )
            ]
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error linking session: {str(e)}")]
        )
