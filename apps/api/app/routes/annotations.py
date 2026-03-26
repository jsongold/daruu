"""Annotation pair routes."""

from fastapi import APIRouter, HTTPException, status

from app.infrastructure.observability import get_logger
from app.models import ApiResponse
from app.models.annotation import (
    AnnotationPairCreate,
    AnnotationPairModel,
    AnnotationPairsResponse,
)
from app.repositories.supabase.annotation_pair_repository import (
    SupabaseAnnotationPairRepository,
)

router = APIRouter(prefix="/documents/{document_id}/annotations", tags=["annotations"])
logger = get_logger("annotations")


def get_repo() -> SupabaseAnnotationPairRepository:
    return SupabaseAnnotationPairRepository()


@router.get("", response_model=ApiResponse[AnnotationPairsResponse])
async def list_annotations(document_id: str) -> ApiResponse[AnnotationPairsResponse]:
    """List all annotation pairs for a document."""
    repo = get_repo()
    pairs = repo.list_by_document(document_id)
    return ApiResponse(success=True, data=AnnotationPairsResponse(pairs=pairs))


@router.post(
    "",
    response_model=ApiResponse[AnnotationPairModel],
    status_code=status.HTTP_201_CREATED,
)
async def create_annotation(
    document_id: str,
    body: AnnotationPairCreate,
) -> ApiResponse[AnnotationPairModel]:
    """Create an annotation pair."""
    repo = get_repo()
    try:
        pair = repo.create(document_id, body)
        return ApiResponse(success=True, data=pair)
    except Exception as e:
        logger.error(f"Failed to create annotation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create annotation pair",
        )


@router.delete("/{pair_id}", response_model=ApiResponse[dict])
async def delete_annotation(document_id: str, pair_id: str) -> ApiResponse[dict]:
    """Delete an annotation pair."""
    repo = get_repo()
    deleted = repo.delete(pair_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotation pair not found",
        )
    return ApiResponse(success=True, data={"deleted": True})


@router.delete("", response_model=ApiResponse[dict])
async def clear_annotations(document_id: str) -> ApiResponse[dict]:
    """Clear all annotation pairs for a document."""
    repo = get_repo()
    count = repo.delete_by_document(document_id)
    return ApiResponse(success=True, data={"deleted_count": count})
