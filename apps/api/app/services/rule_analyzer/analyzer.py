"""RuleAnalyzer — LLM-based rule extraction with persistent DB + vector search.

Analyzes rule documents by chunking text and sending each chunk to an LLM
for structured rule extraction using Instructor (Pydantic-validated output).
Results are persisted to the rule_snippets table with vector embeddings
for semantic search.

Chunk analysis and embedding are parallelized with asyncio.gather().
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from app.domain.models.form_context import FormFieldSpec
from app.domain.models.rule_snippet import RuleSnippet
from app.repositories.rule_snippet_repository import RuleSnippetRepository
from app.services.rule_analyzer.chunker import chunk_document
from app.services.rule_analyzer.schemas import ChunkAnalysisResult

logger = logging.getLogger(__name__)

RULE_EXTRACTION_SYSTEM_PROMPT = """\
You are a document analysis assistant. Your task is to extract filling rules \
and constraints from the provided document text.

For each rule you find, extract:
- rule_text: The rule or instruction in clear language
- applicable_fields: List of field IDs this rule applies to (empty list if it applies to all fields)
- confidence: How confident you are this is a real rule (0.0 to 1.0)

Return your response as JSON with a "rules" array.

Example response:
{
  "rules": [
    {
      "rule_text": "Date fields must use YYYY/MM/DD format",
      "applicable_fields": ["date_of_birth", "issue_date"],
      "confidence": 0.95
    }
  ]
}

If no rules are found, return: {"rules": []}
"""


def _build_user_prompt(chunk: str, field_ids: list[str]) -> str:
    """Build the user prompt for chunk analysis."""
    parts = ["Analyze the following document text and extract any filling rules or constraints."]
    if field_ids:
        parts.append(f"\nAvailable field IDs: {json.dumps(field_ids)}")
    parts.append(f"\n\nDocument text:\n---\n{chunk}\n---")
    return "\n".join(parts)


class RuleAnalyzerStub:
    """Stub implementation of RuleAnalyzerProtocol.

    Returns an empty list of rule snippets. Kept for backward compatibility
    and as a fallback when LLM is unavailable.
    """

    async def analyze(
        self,
        rule_docs: tuple[str, ...],
        field_hints: tuple[FormFieldSpec, ...] = (),
        skip_embedding: bool = False,
    ) -> list[RuleSnippet]:
        return []


class RuleAnalyzer:
    """LLM-based rule analyzer with persistent DB storage and vector search.

    Chunks rule documents, sends each chunk to an LLM for structured
    rule extraction, embeds each rule, and persists to the database.
    """

    def __init__(
        self,
        llm_client: Any,
        snippet_repo: RuleSnippetRepository,
        embedding_gateway: Any | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._snippet_repo = snippet_repo
        self._embedding_gateway = embedding_gateway
        self._analysis_cache: dict[str, list[RuleSnippet]] = {}

    @staticmethod
    def _content_hash(rule_docs: tuple[str, ...]) -> str:
        """Compute a SHA-256 hash of rule document contents for caching."""
        h = hashlib.sha256()
        for doc in rule_docs:
            h.update(doc.encode("utf-8"))
        return h.hexdigest()

    async def analyze(
        self,
        rule_docs: tuple[str, ...],
        field_hints: tuple[FormFieldSpec, ...] = (),
        document_id: str = "",
        skip_embedding: bool = False,
    ) -> list[RuleSnippet]:
        """Analyze rule documents and extract rule snippets.

        Flow:
        1. Empty docs -> return []
        2. Check content-hash cache -> return cached on hit
        3. Chunk each doc -> LLM analyze each chunk
        4. (Unless skip_embedding) Embed each rule + persist to DB
        5. Cache and return all snippets

        Args:
            rule_docs: Tuple of rule document text strings.
            field_hints: Form field specs for context.
            document_id: Optional document ID for DB persistence.
            skip_embedding: When True, skip embedding and DB persist
                (used for real-time pipeline to avoid slow API calls).
        """
        if not rule_docs:
            return []

        non_empty_docs = tuple(d for d in rule_docs if d and d.strip())
        if not non_empty_docs:
            return []

        # Check content-hash cache
        cache_key = self._content_hash(non_empty_docs)
        cached = self._analysis_cache.get(cache_key)
        if cached is not None:
            logger.info(f"Cache hit for rule analysis (hash={cache_key[:12]}...)")
            return cached

        t_start = time.time()
        field_ids = sorted(f.field_id for f in field_hints)

        # Collect all (doc_idx, chunk) pairs, then analyze in parallel
        chunk_tasks: list[tuple[int, int, str]] = []
        for doc_idx, doc_text in enumerate(non_empty_docs):
            for chunk_idx, chunk in enumerate(chunk_document(doc_text)):
                chunk_tasks.append((doc_idx, chunk_idx, chunk))

        t_chunk = int((time.time() - t_start) * 1000)

        logger.info(
            f"Analyzing {len(non_empty_docs)} doc(s), "
            f"{len(chunk_tasks)} chunk(s) for document_id={document_id}"
        )

        # Parallel LLM calls for all chunks
        t_llm_start = time.time()

        async def _safe_analyze(doc_idx: int, chunk_idx: int, chunk: str) -> list[RuleSnippet]:
            try:
                return await self._analyze_chunk(chunk, field_ids, doc_idx, document_id)
            except Exception as e:
                logger.warning(f"Chunk analysis failed (doc={doc_idx}, chunk={chunk_idx}): {e}")
                return []

        chunk_results = await asyncio.gather(
            *(_safe_analyze(di, ci, c) for di, ci, c in chunk_tasks)
        )
        all_snippets: list[RuleSnippet] = [s for batch in chunk_results for s in batch]
        t_llm = int((time.time() - t_llm_start) * 1000)

        if skip_embedding:
            total_ms = int((time.time() - t_start) * 1000)
            logger.info(
                f"RuleAnalyzer.analyze profiling: total={total_ms}ms, "
                f"chunk={t_chunk}ms, llm={t_llm}ms, "
                f"skip_embedding=True, snippets={len(all_snippets)}, "
                f"document_id={document_id}"
            )
            self._analysis_cache[cache_key] = all_snippets
            return all_snippets

        # Parallel embed + persist
        t_persist_start = time.time()

        async def _safe_persist(snippet: RuleSnippet) -> RuleSnippet:
            try:
                embedding = await self._embed_rule(snippet.rule_text)
                return self._snippet_repo.create(snippet, embedding)
            except Exception as e:
                logger.warning(f"Failed to persist rule snippet: {e}")
                return snippet

        persisted = list(await asyncio.gather(*(_safe_persist(s) for s in all_snippets)))
        t_persist = int((time.time() - t_persist_start) * 1000)

        total_ms = int((time.time() - t_start) * 1000)
        logger.info(
            f"RuleAnalyzer.analyze profiling: total={total_ms}ms, "
            f"chunk={t_chunk}ms, llm={t_llm}ms, persist={t_persist}ms, "
            f"snippets={len(persisted)}, document_id={document_id}"
        )
        self._analysis_cache[cache_key] = persisted
        return persisted

    async def search_rules(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[RuleSnippet]:
        """Search rules by semantic similarity.

        Args:
            query: Natural language search query.
            limit: Maximum number of results.
            threshold: Minimum similarity score.

        Returns:
            List of matching rule snippets.
        """
        embedding = await self._embed_rule(query)
        if embedding is None:
            return []
        return self._snippet_repo.search_similar(
            query_embedding=embedding, limit=limit, threshold=threshold
        )

    def _has_instructor(self) -> bool:
        """Check if the client supports Instructor's create() method."""
        return hasattr(self._llm_client, "create")

    async def _analyze_chunk(
        self,
        chunk: str,
        field_ids: list[str],
        doc_index: int,
        document_id: str,
    ) -> list[RuleSnippet]:
        """Analyze a single chunk with the LLM.

        Uses Instructor for validated structured output when available,
        falls back to raw JSON parsing.
        """
        user_prompt = _build_user_prompt(chunk, field_ids)
        messages = [
            {"role": "system", "content": RULE_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        if self._has_instructor():
            result = await self._llm_client.create(
                response_model=ChunkAnalysisResult,
                messages=messages,
                max_retries=2,
            )
        else:
            response = await self._llm_client.complete(
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw = response.content
            parsed = json.loads(raw)
            result = ChunkAnalysisResult(**parsed)

        return [
            RuleSnippet(
                document_id=document_id,
                rule_text=r.rule_text,
                applicable_fields=tuple(r.applicable_fields),
                source_document=f"doc_{doc_index}",
                confidence=r.confidence,
            )
            for r in result.rules
        ]

    async def _embed_rule(self, text: str) -> list[float] | None:
        """Embed a rule text using the embedding gateway."""
        if self._embedding_gateway is None:
            return None
        try:
            return await self._embedding_gateway.embed_text(text)
        except Exception as e:
            logger.warning(f"Embedding failed: {e}")
            return None
