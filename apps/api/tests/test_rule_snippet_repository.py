"""Tests for MemoryRuleSnippetRepository — CRUD + vector search."""

import pytest
from app.domain.models.rule_snippet import RuleSnippet
from app.infrastructure.repositories.memory_rule_snippet_repository import (
    MemoryRuleSnippetRepository,
    _cosine_similarity,
)


@pytest.fixture
def repo() -> MemoryRuleSnippetRepository:
    return MemoryRuleSnippetRepository()


def _snippet(
    document_id: str = "doc-1",
    rule_text: str = "Some rule",
    **kwargs,
) -> RuleSnippet:
    return RuleSnippet(document_id=document_id, rule_text=rule_text, **kwargs)


# ============================================================================
# Create
# ============================================================================


class TestCreate:
    def test_assigns_id(self, repo: MemoryRuleSnippetRepository):
        snippet = _snippet()
        result = repo.create(snippet)
        assert result.id is not None
        assert len(result.id) > 0

    def test_preserves_fields(self, repo: MemoryRuleSnippetRepository):
        snippet = _snippet(
            document_id="doc-X",
            rule_text="Use YYYY/MM/DD",
            applicable_fields=("date",),
            source_document="doc_0",
            confidence=0.9,
        )
        result = repo.create(snippet)
        assert result.document_id == "doc-X"
        assert result.rule_text == "Use YYYY/MM/DD"
        assert result.applicable_fields == ("date",)
        assert result.source_document == "doc_0"
        assert result.confidence == 0.9


# ============================================================================
# List by Document
# ============================================================================


class TestListByDocument:
    def test_empty_returns_empty(self, repo: MemoryRuleSnippetRepository):
        assert repo.list_by_document("nonexistent") == []

    def test_filters_by_document(self, repo: MemoryRuleSnippetRepository):
        repo.create(_snippet(document_id="doc-1", rule_text="Rule A"))
        repo.create(_snippet(document_id="doc-2", rule_text="Rule B"))
        repo.create(_snippet(document_id="doc-1", rule_text="Rule C"))

        results = repo.list_by_document("doc-1")
        assert len(results) == 2
        texts = {r.rule_text for r in results}
        assert texts == {"Rule A", "Rule C"}

    def test_respects_limit(self, repo: MemoryRuleSnippetRepository):
        for i in range(5):
            repo.create(_snippet(rule_text=f"Rule {i}"))
        results = repo.list_by_document("doc-1", limit=3)
        assert len(results) == 3


# ============================================================================
# Search Similar
# ============================================================================


class TestSearchSimilar:
    def test_finds_similar(self, repo: MemoryRuleSnippetRepository):
        repo.create(_snippet(rule_text="Rule A"), embedding=[1.0, 0.0, 0.0])
        repo.create(_snippet(rule_text="Rule B"), embedding=[0.0, 1.0, 0.0])

        # Query close to Rule A
        results = repo.search_similar(query_embedding=[0.9, 0.1, 0.0], limit=10, threshold=0.5)
        assert len(results) >= 1
        assert results[0].rule_text == "Rule A"

    def test_threshold_filters(self, repo: MemoryRuleSnippetRepository):
        repo.create(_snippet(rule_text="Rule A"), embedding=[1.0, 0.0, 0.0])
        repo.create(_snippet(rule_text="Rule B"), embedding=[0.0, 1.0, 0.0])

        # Very high threshold: only exact match
        results = repo.search_similar(query_embedding=[1.0, 0.0, 0.0], limit=10, threshold=0.99)
        assert len(results) == 1
        assert results[0].rule_text == "Rule A"

    def test_limit_respected(self, repo: MemoryRuleSnippetRepository):
        for i in range(10):
            repo.create(
                _snippet(rule_text=f"Rule {i}"),
                embedding=[1.0, 0.0, 0.0],
            )
        results = repo.search_similar(query_embedding=[1.0, 0.0, 0.0], limit=3, threshold=0.5)
        assert len(results) == 3

    def test_skips_no_embedding(self, repo: MemoryRuleSnippetRepository):
        repo.create(_snippet(rule_text="No Embedding"), embedding=None)
        repo.create(
            _snippet(rule_text="Has Embedding"),
            embedding=[1.0, 0.0, 0.0],
        )

        results = repo.search_similar(query_embedding=[1.0, 0.0, 0.0], limit=10, threshold=0.5)
        assert len(results) == 1
        assert results[0].rule_text == "Has Embedding"


# ============================================================================
# Delete by Document
# ============================================================================


class TestDeleteByDocument:
    def test_deletes_matching(self, repo: MemoryRuleSnippetRepository):
        repo.create(_snippet(document_id="doc-1", rule_text="Rule A"))
        repo.create(_snippet(document_id="doc-2", rule_text="Rule B"))
        repo.create(_snippet(document_id="doc-1", rule_text="Rule C"))

        deleted = repo.delete_by_document("doc-1")
        assert deleted == 2

        assert repo.list_by_document("doc-1") == []
        assert len(repo.list_by_document("doc-2")) == 1

    def test_delete_nonexistent_returns_zero(self, repo: MemoryRuleSnippetRepository):
        assert repo.delete_by_document("nonexistent") == 0


# ============================================================================
# Cosine Similarity
# ============================================================================


class TestCosineSimilarity:
    def test_identical_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors(self):
        assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_different_lengths_returns_zero(self):
        assert _cosine_similarity([1.0, 0.0], [1.0]) == 0.0

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0
