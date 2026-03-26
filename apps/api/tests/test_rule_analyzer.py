"""Tests for RuleAnalyzer — LLM-based rule extraction with DB persistence."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.domain.models.form_context import FormFieldSpec
from app.domain.models.rule_snippet import RuleSnippet
from app.domain.protocols.rule_analyzer import RuleAnalyzerProtocol
from app.infrastructure.repositories.memory_rule_snippet_repository import (
    MemoryRuleSnippetRepository,
)
from app.services.rule_analyzer.analyzer import (
    RuleAnalyzer,
    RuleAnalyzerStub,
)
from app.services.rule_analyzer.schemas import ChunkAnalysisResult, ExtractedRule

# ============================================================================
# Helpers
# ============================================================================


def _make_llm_response(rules: list[dict]) -> MagicMock:
    """Create a mock LLM response with the given rules."""
    response = MagicMock()
    response.content = json.dumps({"rules": rules})
    return response


def _make_llm_client(rules: list[dict] | None = None) -> AsyncMock:
    """Create a mock LLM client that returns the given rules.

    Sets up both ``complete()`` (raw path) and ``create()`` (Instructor path)
    so that ``_has_instructor()`` picks the structured output route.
    """
    if rules is None:
        rules = []
    client = AsyncMock()
    client.complete = AsyncMock(return_value=_make_llm_response(rules))
    # Instructor path — _has_instructor() checks for `create` attribute
    chunk_result = ChunkAnalysisResult(rules=[ExtractedRule(**r) for r in rules])
    client.create = AsyncMock(return_value=chunk_result)
    return client


def _make_field_hints(*field_ids: str) -> tuple[FormFieldSpec, ...]:
    """Create FormFieldSpec tuples for testing."""
    return tuple(FormFieldSpec(field_id=fid, label=fid, field_type="text") for fid in field_ids)


def _make_embedding_gateway() -> AsyncMock:
    """Create a mock embedding gateway that returns deterministic vectors."""
    gw = AsyncMock()
    # Return a simple deterministic vector based on text hash
    gw.embed_text = AsyncMock(return_value=[0.1] * 8)
    return gw


# ============================================================================
# Protocol Compliance
# ============================================================================


class TestProtocolCompliance:
    def test_stub_satisfies_protocol(self):
        stub = RuleAnalyzerStub()
        assert isinstance(stub, RuleAnalyzerProtocol)

    def test_analyzer_satisfies_protocol(self):
        analyzer = RuleAnalyzer(
            llm_client=AsyncMock(),
            snippet_repo=MemoryRuleSnippetRepository(),
        )
        assert isinstance(analyzer, RuleAnalyzerProtocol)


# ============================================================================
# RuleAnalyzerStub
# ============================================================================


class TestRuleAnalyzerStub:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        stub = RuleAnalyzerStub()
        result = await stub.analyze(rule_docs=("some doc",))
        assert result == []


# ============================================================================
# RuleAnalyzer — Empty / Whitespace Docs
# ============================================================================


class TestRuleAnalyzerEmptyDocs:
    @pytest.mark.asyncio
    async def test_empty_tuple_returns_empty(self):
        llm = _make_llm_client()
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=MemoryRuleSnippetRepository())
        result = await analyzer.analyze(rule_docs=())
        assert result == []
        llm.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_whitespace_only_docs_returns_empty(self):
        llm = _make_llm_client()
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=MemoryRuleSnippetRepository())
        result = await analyzer.analyze(rule_docs=("  ", "\n\n"))
        assert result == []
        llm.create.assert_not_called()


# ============================================================================
# RuleAnalyzer — LLM Analysis + DB Persistence
# ============================================================================


class TestRuleAnalyzerAnalysis:
    @pytest.mark.asyncio
    async def test_analyzes_and_persists(self):
        repo = MemoryRuleSnippetRepository()
        rules = [
            {
                "rule_text": "Date must be YYYY/MM/DD",
                "applicable_fields": ["date"],
                "confidence": 0.9,
            }
        ]
        llm = _make_llm_client(rules)
        emb = _make_embedding_gateway()
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo, embedding_gateway=emb)

        result = await analyzer.analyze(rule_docs=("Short rule doc",), document_id="doc-123")

        assert len(result) == 1
        assert result[0].rule_text == "Date must be YYYY/MM/DD"
        assert result[0].applicable_fields == ("date",)
        assert result[0].confidence == 0.9
        assert result[0].document_id == "doc-123"
        assert result[0].id is not None
        llm.create.assert_called_once()

        # Verify persisted to repo
        stored = repo.list_by_document("doc-123")
        assert len(stored) == 1
        assert stored[0].rule_text == "Date must be YYYY/MM/DD"

    @pytest.mark.asyncio
    async def test_multiple_docs_analyzed(self):
        repo = MemoryRuleSnippetRepository()
        rules = [
            {
                "rule_text": "Rule from chunk",
                "applicable_fields": [],
                "confidence": 0.8,
            }
        ]
        llm = _make_llm_client(rules)
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        result = await analyzer.analyze(rule_docs=("Doc one", "Doc two"))

        # Each doc produces 1 chunk -> 2 LLM calls -> 2 rules
        assert len(result) == 2
        assert llm.create.call_count == 2

    @pytest.mark.asyncio
    async def test_embeds_each_rule(self):
        repo = MemoryRuleSnippetRepository()
        rules = [
            {"rule_text": "Rule A", "applicable_fields": [], "confidence": 1.0},
            {"rule_text": "Rule B", "applicable_fields": [], "confidence": 1.0},
        ]
        llm = _make_llm_client(rules)
        emb = _make_embedding_gateway()
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo, embedding_gateway=emb)

        await analyzer.analyze(rule_docs=("Doc with two rules",))

        # embed_text called once per rule
        assert emb.embed_text.call_count == 2


# ============================================================================
# RuleAnalyzer — LLM Failure
# ============================================================================


class TestRuleAnalyzerLLMFailure:
    @pytest.mark.asyncio
    async def test_llm_failure_skips_chunk(self):
        repo = MemoryRuleSnippetRepository()
        llm = AsyncMock()
        llm.complete = AsyncMock(side_effect=Exception("LLM down"))
        llm.create = AsyncMock(side_effect=Exception("LLM down"))
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        result = await analyzer.analyze(rule_docs=("Some doc",))

        # Chunk failed but overall returns empty (no crash)
        assert result == []


# ============================================================================
# RuleAnalyzer — Persist Failure
# ============================================================================


class TestRuleAnalyzerPersistFailure:
    @pytest.mark.asyncio
    async def test_persist_failure_non_fatal(self):
        repo = MagicMock()
        repo.create = MagicMock(side_effect=Exception("DB down"))

        rules = [{"rule_text": "A rule", "applicable_fields": [], "confidence": 1.0}]
        llm = _make_llm_client(rules)
        # _has_instructor() checks hasattr(client, "create"), but repo.create
        # is the one that should fail, not llm.create. The llm mock from
        # _make_llm_client already has create set up properly.
        analyzer = RuleAnalyzer(llm_client=llm, snippet_repo=repo)

        result = await analyzer.analyze(rule_docs=("Doc",))
        # Returns the snippet even if persist fails
        assert len(result) == 1


# ============================================================================
# RuleAnalyzer — search_rules
# ============================================================================


class TestRuleAnalyzerSearch:
    @pytest.mark.asyncio
    async def test_search_rules_uses_embedding(self):
        repo = MemoryRuleSnippetRepository()
        emb = _make_embedding_gateway()
        analyzer = RuleAnalyzer(llm_client=AsyncMock(), snippet_repo=repo, embedding_gateway=emb)

        # Pre-populate with a rule that has an embedding
        snippet = RuleSnippet(
            document_id="doc-1",
            rule_text="Use YYYY/MM/DD for dates",
        )
        repo.create(snippet, embedding=[0.1] * 8)

        results = await analyzer.search_rules("date format")

        assert len(results) == 1
        assert results[0].rule_text == "Use YYYY/MM/DD for dates"
        emb.embed_text.assert_called_once_with("date format")

    @pytest.mark.asyncio
    async def test_search_rules_no_embedding_gateway(self):
        repo = MemoryRuleSnippetRepository()
        analyzer = RuleAnalyzer(llm_client=AsyncMock(), snippet_repo=repo, embedding_gateway=None)

        results = await analyzer.search_rules("date format")

        assert results == []
