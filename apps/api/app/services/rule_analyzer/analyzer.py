"""RuleAnalyzer — LLM-based rule extraction with persistent DB + vector search.

Analyzes rule documents by chunking text and sending each chunk to an LLM
for structured rule extraction. Results are persisted to the rule_snippets
table with vector embeddings for semantic search.
"""

import json
import logging
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

    async def analyze(
        self,
        rule_docs: tuple[str, ...],
        field_hints: tuple[FormFieldSpec, ...] = (),
        document_id: str = "",
    ) -> list[RuleSnippet]:
        """Analyze rule documents and extract rule snippets.

        Flow:
        1. Empty docs -> return []
        2. Chunk each doc -> LLM analyze each chunk
        3. Embed each rule (if embedding gateway available)
        4. Persist to DB -> return all snippets
        """
        if not rule_docs:
            return []

        non_empty_docs = tuple(d for d in rule_docs if d and d.strip())
        if not non_empty_docs:
            return []

        field_ids = sorted(f.field_id for f in field_hints)

        logger.info(
            f"Analyzing {len(non_empty_docs)} doc(s) for document_id={document_id}"
        )
        all_snippets: list[RuleSnippet] = []

        for doc_idx, doc_text in enumerate(non_empty_docs):
            chunks = chunk_document(doc_text)
            for chunk_idx, chunk in enumerate(chunks):
                try:
                    chunk_snippets = await self._analyze_chunk(
                        chunk, field_ids, doc_idx, document_id
                    )
                    all_snippets.extend(chunk_snippets)
                except Exception as e:
                    logger.warning(
                        f"Chunk analysis failed (doc={doc_idx}, chunk={chunk_idx}): {e}"
                    )

        # Embed and persist each snippet (non-fatal)
        persisted: list[RuleSnippet] = []
        for snippet in all_snippets:
            try:
                embedding = await self._embed_rule(snippet.rule_text)
                stored = self._snippet_repo.create(snippet, embedding)
                persisted.append(stored)
            except Exception as e:
                logger.warning(f"Failed to persist rule snippet: {e}")
                persisted.append(snippet)

        logger.info(f"Persisted {len(persisted)} rule snippets for document_id={document_id}")
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

    async def _analyze_chunk(
        self,
        chunk: str,
        field_ids: list[str],
        doc_index: int,
        document_id: str,
    ) -> list[RuleSnippet]:
        """Analyze a single chunk with the LLM."""
        user_prompt = _build_user_prompt(chunk, field_ids)

        response = await self._llm_client.complete(
            messages=[
                {"role": "system", "content": RULE_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
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
