"""HTTP client for the standalone Rule Service.

Provides fire-and-forget dispatch for async rule analysis,
and proxy methods for list/delete/search that the main API
delegates to the rule-service.
"""

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10.0  # seconds for fire-and-forget dispatch
_PROXY_TIMEOUT = 30.0  # seconds for proxied GET/DELETE


def _base_url() -> str:
    """Resolve the rule-service base URL from settings."""
    settings = get_settings()
    return getattr(settings, "rule_service_url", "http://rule-service:8002")


async def dispatch_analyze(
    document_id: str,
    rule_docs: list[str],
    field_hints: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Fire-and-forget POST to rule-service /api/v1/rules/analyze.

    Returns the JSON response body on success, or an error dict on failure.
    The caller does not need to poll — the rule-service processes synchronously
    and persists to the shared DB.
    """
    url = f"{_base_url()}/api/v1/rules/analyze"
    payload: dict[str, Any] = {
        "document_id": document_id,
        "rule_docs": rule_docs,
    }
    if field_hints:
        payload["field_hints"] = field_hints

    try:
        async with httpx.AsyncClient(timeout=_PROXY_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error(
            "Rule-service returned %s for POST /analyze: %s",
            e.response.status_code,
            e.response.text[:200],
        )
        return {"success": False, "error": f"rule-service error: {e.response.status_code}"}
    except Exception as e:
        logger.error("Failed to reach rule-service: %s", e)
        return {"success": False, "error": f"rule-service unreachable: {e}"}
