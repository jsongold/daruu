"""Rules REST endpoints.

GET    /api/v1/rules/{document_id}   - List rules for a document
GET    /api/v1/rules/search?q=...    - Semantic search across rules
DELETE /api/v1/rules/{document_id}   - Delete rules for a document
POST   /api/v1/rules/analyze         - Proxy to standalone rule-service
"""

import logging

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, field_validator

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
    created_at: str | None = None

    model_config = {"frozen": True}


class FieldHintInput(BaseModel):
    """A single field hint for rule analysis context."""

    field_id: str = Field(..., min_length=1, description="Field identifier")
    label: str = Field(..., min_length=1, description="Field label")
    field_type: str = Field(default="text", description="Field type")

    model_config = {"frozen": True}


class AnalyzeRulesRequest(BaseModel):
    """Request body for rule analysis (proxied to rule-service)."""

    document_id: str = Field(
        ..., min_length=1, max_length=255, description="Document ID for DB persistence"
    )
    rule_docs: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Rule document text strings (max 20 documents)",
    )
    field_hints: list[FieldHintInput] = Field(
        default_factory=list,
        description="Field hints with field_id, label, field_type",
    )

    model_config = {"frozen": True}

    @field_validator("rule_docs")
    @classmethod
    def validate_rule_doc_size(cls, v: list[str]) -> list[str]:
        max_chars = 500_000
        for i, doc in enumerate(v):
            if len(doc) > max_chars:
                raise ValueError(
                    f"rule_docs[{i}] exceeds maximum length of {max_chars} characters"
                )
        return v


def _to_dto(snippet: RuleSnippet) -> RuleSnippetDTO:
    return RuleSnippetDTO(
        id=snippet.id,
        document_id=snippet.document_id,
        rule_text=snippet.rule_text,
        applicable_fields=list(snippet.applicable_fields),
        source_document=snippet.source_document,
        confidence=snippet.confidence,
        created_at=snippet.created_at.isoformat() if snippet.created_at else None,
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
        from app.services.llm import get_llm_client

        client = get_llm_client()
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


# ============================================================================
# Analyze — proxy to standalone rule-service
# ============================================================================


@router.post(
    "/analyze",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Dispatch rule analysis to rule-service",
)
async def analyze_rules(
    body: AnalyzeRulesRequest,
) -> ApiResponse[dict]:
    """Proxy rule analysis to the standalone rule-service.

    The rule-service handles chunking, LLM extraction, embedding, and
    DB persistence independently.
    """
    from app.infrastructure.gateways.rule_service_client import dispatch_analyze

    field_hints = [{"field_id": h.field_id, "label": h.label} for h in body.field_hints]

    result = await dispatch_analyze(
        document_id=body.document_id,
        rule_docs=body.rule_docs,
        field_hints=field_hints if field_hints else None,
    )

    if result.get("success"):
        return ApiResponse(
            success=True,
            data=result.get("data"),
            meta={"document_id": body.document_id, "source": "rule-service"},
        )

    return ApiResponse(
        success=False,
        error=result.get("error", "Unknown error from rule-service"),
        meta={"document_id": body.document_id},
    )
