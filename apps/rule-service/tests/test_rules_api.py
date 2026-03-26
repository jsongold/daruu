"""Tests for the rules API endpoints."""

from unittest.mock import patch

import pytest
from app.main import app
from app.repositories.memory_impl import MemoryRuleSnippetRepository
from app.schemas.rule_schemas import RuleSnippet
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset module-level singletons between tests."""
    import app.routes.rules as rules_mod

    rules_mod._repo = None
    rules_mod._embedding_gw = None
    yield
    rules_mod._repo = None
    rules_mod._embedding_gw = None


@pytest.fixture
def memory_repo():
    """Create an in-memory repo and inject it."""
    import app.routes.rules as rules_mod

    repo = MemoryRuleSnippetRepository()
    rules_mod._repo = repo
    return repo


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestListRules:
    def test_list_rules_empty(self, client, memory_repo):
        resp = client.get("/api/v1/rules/doc-123")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []

    def test_list_rules_with_data(self, client, memory_repo):
        snippet = RuleSnippet(
            document_id="doc-1",
            rule_text="Always use blue ink",
            confidence=0.95,
        )
        memory_repo.create(snippet)

        resp = client.get("/api/v1/rules/doc-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["rule_text"] == "Always use blue ink"


class TestDeleteRules:
    def test_delete_rules(self, client, memory_repo):
        snippet = RuleSnippet(
            document_id="doc-del",
            rule_text="To be deleted",
        )
        memory_repo.create(snippet)
        assert len(memory_repo.list_by_document("doc-del")) == 1

        resp = client.delete("/api/v1/rules/doc-del")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["deleted_count"] == 1

        assert len(memory_repo.list_by_document("doc-del")) == 0


class TestAnalyzeRules:
    def test_analyze_returns_error_when_no_llm(self, client, memory_repo):
        """Without LLM configured, analyze should return an error."""
        with patch(
            "app.routes.rules._get_llm_client",
            side_effect=RuntimeError("LLM client not configured"),
        ):
            resp = client.post(
                "/api/v1/rules/analyze",
                json={
                    "document_id": "doc-test",
                    "rule_docs": ["Some rule text"],
                },
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is False

    def test_analyze_validates_empty_rule_docs(self, client, memory_repo):
        resp = client.post(
            "/api/v1/rules/analyze",
            json={
                "document_id": "doc-test",
                "rule_docs": [],
            },
        )
        assert resp.status_code == 422
