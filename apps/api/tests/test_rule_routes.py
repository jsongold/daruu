"""Tests for Rules REST endpoints."""

from unittest.mock import AsyncMock

import pytest
from app.domain.models.rule_snippet import RuleSnippet
from app.infrastructure.repositories.memory_rule_snippet_repository import (
    MemoryRuleSnippetRepository,
)
from app.main import app
from app.routes.rules import get_embedding_gateway, get_repo
from fastapi.testclient import TestClient


@pytest.fixture
def repo() -> MemoryRuleSnippetRepository:
    return MemoryRuleSnippetRepository()


@pytest.fixture
def mock_embedding_gw() -> AsyncMock:
    gw = AsyncMock()
    gw.embed_text = AsyncMock(return_value=[0.1] * 8)
    return gw


@pytest.fixture
def client(repo: MemoryRuleSnippetRepository, mock_embedding_gw: AsyncMock) -> TestClient:
    app.dependency_overrides[get_repo] = lambda: repo
    app.dependency_overrides[get_embedding_gateway] = lambda: mock_embedding_gw
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_snippet(
    repo: MemoryRuleSnippetRepository,
    document_id: str = "doc-1",
    rule_text: str = "Use YYYY/MM/DD",
    embedding: list[float] | None = None,
) -> RuleSnippet:
    snippet = RuleSnippet(document_id=document_id, rule_text=rule_text)
    return repo.create(snippet, embedding=embedding)


# ============================================================================
# GET /api/v1/rules/{document_id}
# ============================================================================


class TestListRules:
    def test_list_empty(self, client: TestClient):
        resp = client.get("/api/v1/rules/doc-nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"] == []

    def test_list_returns_rules(self, client: TestClient, repo: MemoryRuleSnippetRepository):
        _seed_snippet(repo, document_id="doc-1", rule_text="Rule A")
        _seed_snippet(repo, document_id="doc-1", rule_text="Rule B")
        _seed_snippet(repo, document_id="doc-2", rule_text="Rule C")

        resp = client.get("/api/v1/rules/doc-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) == 2
        texts = {r["rule_text"] for r in body["data"]}
        assert texts == {"Rule A", "Rule B"}

    def test_list_respects_limit(self, client: TestClient, repo: MemoryRuleSnippetRepository):
        for i in range(5):
            _seed_snippet(repo, rule_text=f"Rule {i}")

        resp = client.get("/api/v1/rules/doc-1?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2


# ============================================================================
# DELETE /api/v1/rules/{document_id}
# ============================================================================


class TestDeleteRules:
    def test_delete_existing(self, client: TestClient, repo: MemoryRuleSnippetRepository):
        _seed_snippet(repo, document_id="doc-1", rule_text="Rule A")
        _seed_snippet(repo, document_id="doc-1", rule_text="Rule B")

        resp = client.delete("/api/v1/rules/doc-1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["deleted_count"] == 2

        # Verify actually deleted
        assert repo.list_by_document("doc-1") == []

    def test_delete_nonexistent(self, client: TestClient):
        resp = client.delete("/api/v1/rules/doc-nonexistent")
        assert resp.status_code == 200
        assert resp.json()["data"]["deleted_count"] == 0


# ============================================================================
# GET /api/v1/rules/search?q=...
# ============================================================================


class TestSearchRules:
    def test_search_returns_matches(
        self,
        client: TestClient,
        repo: MemoryRuleSnippetRepository,
        mock_embedding_gw: AsyncMock,
    ):
        _seed_snippet(repo, rule_text="Date format rule", embedding=[0.1] * 8)
        _seed_snippet(repo, rule_text="Name format rule", embedding=[0.1] * 8)

        resp = client.get("/api/v1/rules/search?q=date+format")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert len(body["data"]) >= 1

    def test_search_requires_query(self, client: TestClient):
        resp = client.get("/api/v1/rules/search")
        assert resp.status_code in (400, 422)

    def test_search_empty_results(
        self,
        client: TestClient,
        repo: MemoryRuleSnippetRepository,
    ):
        # No snippets stored
        resp = client.get("/api/v1/rules/search?q=anything")
        assert resp.status_code == 200
        assert resp.json()["data"] == []
