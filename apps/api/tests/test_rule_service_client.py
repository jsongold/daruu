"""Tests for RuleServiceClient — HTTP client for standalone rule-service."""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


class TestDispatchAnalyze:
    @pytest.mark.asyncio
    async def test_dispatch_success(self):
        """dispatch_analyze returns rule-service JSON on success."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "data": [{"rule_text": "Use blue ink", "confidence": 0.9}],
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.infrastructure.gateways.rule_service_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from app.infrastructure.gateways.rule_service_client import dispatch_analyze

            result = await dispatch_analyze(
                document_id="doc-1",
                rule_docs=["Some rule text"],
            )

        assert result["success"] is True
        assert len(result["data"]) == 1

    @pytest.mark.asyncio
    async def test_dispatch_connection_error(self):
        """dispatch_analyze returns error dict on connection failure."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.infrastructure.gateways.rule_service_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from app.infrastructure.gateways.rule_service_client import dispatch_analyze

            result = await dispatch_analyze(
                document_id="doc-1",
                rule_docs=["Some rule text"],
            )

        assert result["success"] is False
        assert "unreachable" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_with_field_hints(self):
        """dispatch_analyze includes field_hints in the payload."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.infrastructure.gateways.rule_service_client.httpx.AsyncClient",
            return_value=mock_client,
        ):
            from app.infrastructure.gateways.rule_service_client import dispatch_analyze

            await dispatch_analyze(
                document_id="doc-1",
                rule_docs=["Rule text"],
                field_hints=[{"field_id": "name", "label": "Name"}],
            )

        # Verify the POST payload included field_hints
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["field_hints"] == [{"field_id": "name", "label": "Name"}]
