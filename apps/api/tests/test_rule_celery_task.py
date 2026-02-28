"""Tests for RuleAnalyzer task logic and rule-service proxy endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.repositories.memory_rule_snippet_repository import (
    MemoryRuleSnippetRepository,
)
from app.services.rule_analyzer.schemas import ChunkAnalysisResult, ExtractedRule


# ============================================================================
# Helpers
# ============================================================================


def _make_llm_client(rules: list[dict] | None = None) -> AsyncMock:
    """Create a mock LLM client that returns the given rules."""
    if rules is None:
        rules = []
    client = AsyncMock()
    chunk_result = ChunkAnalysisResult(
        rules=[ExtractedRule(**r) for r in rules]
    )
    client.create = AsyncMock(return_value=chunk_result)
    client.complete = AsyncMock(
        return_value=MagicMock(content=json.dumps({"rules": rules}))
    )
    return client


def _sample_rules() -> list[dict]:
    return [
        {
            "rule_text": "Date must be YYYY/MM/DD",
            "applicable_fields": ["date"],
            "confidence": 0.9,
        },
    ]


# ============================================================================
# Task Logic Tests (direct function call, no Celery broker needed)
# ============================================================================


class TestAnalyzeRulesTaskLogic:
    """Tests for the core logic invoked by RuleAnalyzer.analyze().

    We test by calling RuleAnalyzer.analyze() directly with the same setup
    the pipeline uses (skip_embedding=True for inline path).
    """

    @pytest.mark.asyncio
    async def test_analyzer_returns_serializable_snippets(self):
        """Snippets should be serializable to dicts."""
        from app.services.rule_analyzer.analyzer import RuleAnalyzer

        repo = MemoryRuleSnippetRepository()
        llm = _make_llm_client(_sample_rules())
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        snippets = await analyzer.analyze(
            rule_docs=("Short rule doc",),
            document_id="doc-123",
            skip_embedding=True,
        )

        serialized = [s.model_dump(mode="json") for s in snippets]
        assert len(serialized) == 1
        assert serialized[0]["rule_text"] == "Date must be YYYY/MM/DD"
        assert serialized[0]["document_id"] == "doc-123"
        assert serialized[0]["confidence"] == 0.9
        assert "created_at" in serialized[0]

    @pytest.mark.asyncio
    async def test_analyzer_with_field_hints(self):
        """Analyzer should accept field hints from dicts."""
        from app.domain.models.form_context import FormFieldSpec
        from app.services.rule_analyzer.analyzer import RuleAnalyzer

        repo = MemoryRuleSnippetRepository()
        llm = _make_llm_client(_sample_rules())
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        hints = tuple(
            FormFieldSpec(
                field_id=h["field_id"],
                label=h["label"],
                field_type=h.get("field_type", "text"),
            )
            for h in [
                {"field_id": "name", "label": "Full Name"},
                {"field_id": "date", "label": "Date", "field_type": "date"},
            ]
        )

        snippets = await analyzer.analyze(
            rule_docs=("Rule doc with hints",),
            field_hints=hints,
            document_id="doc-hints",
            skip_embedding=True,
        )

        assert len(snippets) >= 1

    @pytest.mark.asyncio
    async def test_empty_docs_returns_empty(self):
        """Whitespace-only docs should return empty list."""
        from app.services.rule_analyzer.analyzer import RuleAnalyzer

        repo = MemoryRuleSnippetRepository()
        llm = _make_llm_client([])
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        snippets = await analyzer.analyze(
            rule_docs=("  ",),
            document_id="doc-empty",
            skip_embedding=True,
        )

        serialized = [s.model_dump(mode="json") for s in snippets]
        assert serialized == []

    @pytest.mark.asyncio
    async def test_task_result_dict_format(self):
        """Verify the dict format matches what the task returns."""
        from app.services.rule_analyzer.analyzer import RuleAnalyzer

        repo = MemoryRuleSnippetRepository()
        llm = _make_llm_client(_sample_rules())
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        snippets = await analyzer.analyze(
            rule_docs=("A rule doc",),
            document_id="doc-result",
            skip_embedding=True,
        )

        result = {
            "success": True,
            "document_id": "doc-result",
            "snippet_count": len(snippets),
            "snippets": [s.model_dump(mode="json") for s in snippets],
        }

        assert result["success"] is True
        assert result["snippet_count"] >= 1
        assert isinstance(result["snippets"], list)
        assert result["snippets"][0]["rule_text"] == "Date must be YYYY/MM/DD"


# ============================================================================
# POST /rules/analyze Endpoint Tests (rule-service proxy)
# ============================================================================


class TestAnalyzeRulesEndpoint:
    """Tests for POST /rules/analyze endpoint (proxied to rule-service)."""

    def test_dispatch_proxies_to_rule_service(self, client: TestClient):
        """POST /rules/analyze should proxy to the rule-service."""
        mock_result = {
            "success": True,
            "data": {"snippet_count": 1},
        }

        with patch(
            "app.infrastructure.gateways.rule_service_client.dispatch_analyze",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/rules/analyze",
                json={
                    "document_id": "doc-1",
                    "rule_docs": ["Some rule document"],
                },
            )

        assert response.status_code == 202
        body = response.json()
        assert body["success"] is True
        assert body["meta"]["source"] == "rule-service"

    def test_dispatch_returns_error_on_failure(self, client: TestClient):
        """POST /rules/analyze should return error when rule-service fails."""
        mock_result = {
            "success": False,
            "error": "rule-service unreachable: Connection refused",
        }

        with patch(
            "app.infrastructure.gateways.rule_service_client.dispatch_analyze",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            response = client.post(
                "/api/v1/rules/analyze",
                json={
                    "document_id": "doc-1",
                    "rule_docs": ["Some rule document"],
                },
            )

        assert response.status_code == 202
        body = response.json()
        assert body["success"] is False
        assert "unreachable" in body["error"]

    def test_dispatch_validation_error_too_many_docs(self, client: TestClient):
        """POST /rules/analyze should reject more than 20 rule_docs."""
        response = client.post(
            "/api/v1/rules/analyze",
            json={
                "document_id": "doc-1",
                "rule_docs": [f"doc-{i}" for i in range(25)],
            },
        )
        assert response.status_code in (400, 422)

    def test_dispatch_validation_error_no_docs(self, client: TestClient):
        """POST /rules/analyze should reject empty rule_docs."""
        response = client.post(
            "/api/v1/rules/analyze",
            json={
                "document_id": "doc-1",
                "rule_docs": [],
            },
        )
        assert response.status_code in (400, 422)
