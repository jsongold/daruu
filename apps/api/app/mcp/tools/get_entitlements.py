"""
get_entitlements Tool Handler.

Returns the current user's entitlements (feature access)
based on their subscription plan.
"""

from typing import Any

from mcp.types import CallToolResult, TextContent

from app.mcp.session import get_current_session, MCPSessionManager


async def handle(arguments: dict[str, Any]) -> CallToolResult:
    """
    Handle get_entitlements tool call.

    Args:
        arguments: Tool arguments (none required)

    Returns:
        CallToolResult with entitlements info
    """
    session = await get_current_session()
    if not session:
        return CallToolResult(
            content=[TextContent(type="text", text="Error: No active session")]
        )

    session_manager = MCPSessionManager()

    try:
        user_id = session.get("user_id")

        if not user_id:
            # Not logged in - show free tier info
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=(
                        "**Current Status: Not Logged In**\n\n"
                        "You can:\n"
                        "- ✓ Upload and auto-fill forms\n"
                        "- ✓ Preview filled forms\n"
                        "- ✓ Edit field values\n\n"
                        "To download PDFs, please log in.\n\n"
                        "---\n"
                        "**Free Plan** (after login):\n"
                        "- 5 exports per month\n"
                        "- Basic form filling\n"
                        "- Standard support\n\n"
                        "**Pro Plan** ($9/month):\n"
                        "- Unlimited exports\n"
                        "- Priority processing\n"
                        "- User profile auto-fill\n"
                        "- Template library\n"
                        "- Priority support"
                    )
                )]
            )

        # Get user's entitlements
        entitlements = await session_manager.get_user_entitlements(user_id)

        plan = entitlements.get("plan", "free")
        exports_remaining = entitlements.get("exports_remaining", 0)
        exports_total = entitlements.get("exports_total", 5)
        features = entitlements.get("features", [])

        # Format plan name
        plan_display = {
            "free": "Free",
            "pro": "Pro",
            "enterprise": "Enterprise",
        }.get(plan, plan.title())

        lines = [f"**Your Plan: {plan_display}**\n"]

        # Show usage
        if plan == "free":
            lines.append(f"📊 Exports: {exports_remaining}/{exports_total} remaining this month")
        else:
            lines.append("📊 Exports: Unlimited")

        lines.append("")

        # Show features
        lines.append("**Features:**")

        feature_list = {
            "free": [
                ("✓", "Upload and auto-fill forms"),
                ("✓", "Preview filled forms"),
                ("✓", "Edit field values"),
                ("✓", "Basic form filling"),
                ("✗", "User profile auto-fill"),
                ("✗", "Template library"),
                ("✗", "Priority processing"),
            ],
            "pro": [
                ("✓", "Upload and auto-fill forms"),
                ("✓", "Preview filled forms"),
                ("✓", "Edit field values"),
                ("✓", "Unlimited exports"),
                ("✓", "User profile auto-fill"),
                ("✓", "Template library"),
                ("✓", "Priority processing"),
                ("✓", "Priority support"),
            ],
            "enterprise": [
                ("✓", "All Pro features"),
                ("✓", "Custom integrations"),
                ("✓", "SSO / SAML"),
                ("✓", "Dedicated support"),
                ("✓", "SLA guarantee"),
            ],
        }

        for status, feature in feature_list.get(plan, feature_list["free"]):
            lines.append(f"- {status} {feature}")

        # Add upgrade prompt for free users
        if plan == "free":
            lines.extend([
                "",
                "---",
                "[Upgrade to Pro](https://daru-pdf.io/pricing) for unlimited exports and more features.",
            ])

        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(lines))]
        )

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error getting entitlements: {str(e)}")]
        )
