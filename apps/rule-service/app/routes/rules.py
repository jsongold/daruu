"""Rules REST endpoints for the standalone Rule Service.

POST   /api/v1/rules/analyze             - Run rule analysis (sync)
GET    /api/v1/rules/search?q=...        - Semantic search across rules
GET    /api/v1/rules/{document_id}       - List rules for a document
DELETE /api/v1/rules/{document_id}       - Delete rules for a document
"""

import logging

from fastapi import APIRouter, Depends, Query, status

from app.infrastructure.embedding import MockEmbeddingGateway, OpenAIEmbeddingGateway
from app.repositories.memory_impl import MemoryRuleSnippetRepository
from app.repositories.protocol import RuleSnippetRepository
from app.schemas.api_schemas import (
    AnalyzeRulesRequest,
    ApiResponse,
    RuleSnippetDTO,
)
from app.schemas.rule_schemas import RuleSnippet
from app.services.rule_analyzer import RuleAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])

# ---------------------------------------------------------------------------
# Module-level singletons (lazy)
# ---------------------------------------------------------------------------

_repo: RuleSnippetRepository | None = None
_embedding_gw: MockEmbeddingGateway | OpenAIEmbeddingGateway | None = None


def _get_repo() -> RuleSnippetRepository:
    """Return the RuleSnippetRepository singleton.

    Uses Supabase when configured, falls back to in-memory for dev/test.
    """
    global _repo
    if _repo is not None:
        return _repo

    from app.infrastructure.supabase_client import get_supabase_client

    client = get_supabase_client()
    if client is not None:
        from app.repositories.supabase_impl import SupabaseRuleSnippetRepository

        _repo = SupabaseRuleSnippetRepository()
    else:
        _repo = MemoryRuleSnippetRepository()
    return _repo


def _get_embedding_gw() -> MockEmbeddingGateway | OpenAIEmbeddingGateway:
    """Return the embedding gateway singleton."""
    global _embedding_gw
    if _embedding_gw is not None:
        return _embedding_gw

    try:
        from app.infrastructure.llm_client import get_llm_client

        client = get_llm_client()
        if client is not None:
            _embedding_gw = OpenAIEmbeddingGateway(client=client)
            return _embedding_gw
    except Exception:
        pass
    _embedding_gw = MockEmbeddingGateway()
    return _embedding_gw


def _get_llm_client():
    """Return the LLM client or raise."""
    from app.infrastructure.llm_client import get_llm_client

    client = get_llm_client()
    if client is None:
        raise RuntimeError("LLM client not configured (missing DARU_OPENAI_API_KEY)")
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dto(snippet: RuleSnippet) -> RuleSnippetDTO:
    return RuleSnippetDTO(
        id=snippet.id,
        document_id=snippet.document_id,
        rule_text=snippet.rule_text,
        applicable_fields=list(snippet.applicable_fields),
        source_document=snippet.source_document,
        confidence=snippet.confidence,
        created_at=snippet.created_at,
    )


# ---------------------------------------------------------------------------
# Route Handlers
# ---------------------------------------------------------------------------


@router.post(
    "/analyze",
    response_model=ApiResponse[list[RuleSnippetDTO]],
    status_code=status.HTTP_200_OK,
    summary="Analyze rule documents and extract rules",
)
async def analyze_rules(
    body: AnalyzeRulesRequest,
) -> ApiResponse[list[RuleSnippetDTO]]:
    """Analyze rule documents: chunk -> LLM extract -> embed -> persist.

    Returns the extracted rule snippets.
    """
    try:
        llm_client = _get_llm_client()
    except RuntimeError as e:
        return ApiResponse(success=False, error=str(e))

    repo = _get_repo()
    embedding_gw = _get_embedding_gw()

    analyzer = RuleAnalyzer(
        llm_client=llm_client,
        snippet_repo=repo,
        embedding_gateway=embedding_gw,
    )

    field_hints = tuple((h.field_id, h.label) for h in body.field_hints)

    snippets = await analyzer.analyze(
        rule_docs=tuple(body.rule_docs),
        field_hints=field_hints,
        document_id=body.document_id,
    )

    dtos = [_to_dto(s) for s in snippets]
    return ApiResponse(
        success=True,
        data=dtos,
        meta={"document_id": body.document_id, "snippet_count": len(dtos)},
    )


@router.get(
    "/search",
    response_model=ApiResponse[list[RuleSnippetDTO]],
    status_code=status.HTTP_200_OK,
    summary="Semantic search across rules",
)
async def search_rules(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=10, ge=1, le=100, description="Max results"),
    threshold: float = Query(
        default=0.7, ge=0.0, le=1.0, description="Min similarity"
    ),
) -> ApiResponse[list[RuleSnippetDTO]]:
    """Semantic search for rule snippets using vector embeddings."""
    repo = _get_repo()
    embedding_gw = _get_embedding_gw()

    query_embedding = await embedding_gw.embed_text(q)
    snippets = repo.search_similar(
        query_embedding=query_embedding, limit=limit, threshold=threshold
    )
    dtos = [_to_dto(s) for s in snippets]
    return ApiResponse(
        success=True,
        data=dtos,
        meta={"query": q, "count": len(dtos)},
    )


@router.get(
    "/{document_id}",
    response_model=ApiResponse[list[RuleSnippetDTO]],
    status_code=status.HTTP_200_OK,
    summary="List rules for a document",
)
async def list_rules(
    document_id: str,
    limit: int = Query(default=100, ge=1, le=500, description="Max results"),
) -> ApiResponse[list[RuleSnippetDTO]]:
    """List all rule snippets extracted for a document."""
    repo = _get_repo()
    snippets = repo.list_by_document(document_id, limit=limit)
    dtos = [_to_dto(s) for s in snippets]
    return ApiResponse(
        success=True,
        data=dtos,
        meta={"document_id": document_id, "count": len(dtos)},
    )


@router.delete(
    "/{document_id}",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete rules for a document",
)
async def delete_rules(
    document_id: str,
) -> ApiResponse[dict]:
    """Delete all rule snippets for a document."""
    repo = _get_repo()
    deleted = repo.delete_by_document(document_id)
    return ApiResponse(
        success=True,
        data={"deleted_count": deleted},
        meta={"document_id": document_id},
    )
