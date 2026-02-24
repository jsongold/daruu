"""Rules REST endpoints.

GET    /api/v1/rules/{document_id}   - List rules for a document
GET    /api/v1/rules/search?q=...    - Semantic search across rules
DELETE /api/v1/rules/{document_id}   - Delete rules for a document
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.domain.models.rule_snippet import RuleSnippet
from app.infrastructure.gateways.embedding import MockEmbeddingGateway
from app.infrastructure.repositories import get_rule_snippet_repository
from app.models.common import ApiResponse
from app.repositories.rule_snippet_repository import RuleSnippetRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rules", tags=["rules"])


# ============================================================================
# Response DTOs
# ============================================================================


class RuleSnippetDTO(BaseModel):
    """Response DTO for a rule snippet."""

    id: str | None
    document_id: str
    rule_text: str
    applicable_fields: list[str]
    source_document: str | None
    confidence: float
    created_at: datetime

    model_config = {"frozen": True}


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


# ============================================================================
# Dependencies
# ============================================================================


def get_repo() -> RuleSnippetRepository:
    """Get the RuleSnippetRepository instance."""
    return get_rule_snippet_repository()


def get_embedding_gateway():
    """Get the EmbeddingGateway for search queries."""
    from app.infrastructure.gateways.embedding import (
        MockEmbeddingGateway,
        OpenAIEmbeddingGateway,
    )

    try:
        from app.routes.vision_autofill import get_openai_client

        client = get_openai_client()
        if client is not None:
            return OpenAIEmbeddingGateway(client=client)
    except Exception:
        pass
    return MockEmbeddingGateway()


# ============================================================================
# Route Handlers
# ============================================================================


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
    repo: RuleSnippetRepository = Depends(get_repo),
    embedding_gw=Depends(get_embedding_gateway),
) -> ApiResponse[list[RuleSnippetDTO]]:
    """Semantic search for rule snippets using vector embeddings."""
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
    repo: RuleSnippetRepository = Depends(get_repo),
) -> ApiResponse[list[RuleSnippetDTO]]:
    """List all rule snippets extracted for a document."""
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
    repo: RuleSnippetRepository = Depends(get_repo),
) -> ApiResponse[dict]:
    """Delete all rule snippets for a document."""
    deleted = repo.delete_by_document(document_id)
    return ApiResponse(
        success=True,
        data={"deleted_count": deleted},
        meta={"document_id": document_id},
    )
