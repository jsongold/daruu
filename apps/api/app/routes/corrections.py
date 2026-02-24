"""Corrections REST endpoints.

POST /api/v1/corrections - Record a user correction
GET  /api/v1/corrections/{document_id} - List corrections for a document
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.domain.models.correction_record import CorrectionCategory, CorrectionRecord
from app.models.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/corrections", tags=["corrections"])


# ============================================================================
# Request/Response DTOs
# ============================================================================


class CreateCorrectionDTO(BaseModel):
    """Request body for recording a correction."""

    document_id: str = Field(..., min_length=1, description="Document ID")
    field_id: str = Field(..., min_length=1, description="Field that was corrected")
    original_value: str | None = Field(None, description="Auto-filled value")
    corrected_value: str = Field(..., min_length=1, description="User's corrected value")
    category: CorrectionCategory = Field(
        default=CorrectionCategory.OTHER, description="Correction category"
    )
    conversation_id: str | None = Field(None, description="Conversation context")

    model_config = {"frozen": True}


class CorrectionDTO(BaseModel):
    """Response DTO for a correction record."""

    document_id: str
    field_id: str
    original_value: str | None
    corrected_value: str
    category: str
    timestamp: datetime
    conversation_id: str | None

    model_config = {"frozen": True}


# ============================================================================
# Dependencies
# ============================================================================


def get_correction_tracker():
    """Get the CorrectionTracker instance."""
    from app.infrastructure.repositories import get_correction_repository
    from app.services.correction_tracker import CorrectionTracker

    repo = get_correction_repository()
    return CorrectionTracker(repository=repo)


# ============================================================================
# Route Handlers
# ============================================================================


@router.post(
    "",
    response_model=ApiResponse[CorrectionDTO],
    status_code=status.HTTP_201_CREATED,
    summary="Record a user correction",
)
async def create_correction(
    request: CreateCorrectionDTO,
    tracker=Depends(get_correction_tracker),
) -> ApiResponse[CorrectionDTO]:
    """Record a user correction to an auto-filled field."""
    record = CorrectionRecord(
        document_id=request.document_id,
        field_id=request.field_id,
        original_value=request.original_value,
        corrected_value=request.corrected_value,
        category=request.category,
        conversation_id=request.conversation_id,
    )

    await tracker.record(record)

    dto = CorrectionDTO(
        document_id=record.document_id,
        field_id=record.field_id,
        original_value=record.original_value,
        corrected_value=record.corrected_value,
        category=str(record.category),
        timestamp=record.timestamp,
        conversation_id=record.conversation_id,
    )

    return ApiResponse(success=True, data=dto)


@router.get(
    "/{document_id}",
    response_model=ApiResponse[list[CorrectionDTO]],
    status_code=status.HTTP_200_OK,
    summary="List corrections for a document",
)
async def list_corrections(
    document_id: str,
    tracker=Depends(get_correction_tracker),
) -> ApiResponse[list[CorrectionDTO]]:
    """List all corrections recorded for a document."""
    records = await tracker.list_corrections(document_id)

    dtos = [
        CorrectionDTO(
            document_id=r.document_id,
            field_id=r.field_id,
            original_value=r.original_value,
            corrected_value=r.corrected_value,
            category=str(r.category),
            timestamp=r.timestamp,
            conversation_id=r.conversation_id,
        )
        for r in records
    ]

    return ApiResponse(
        success=True,
        data=dtos,
        meta={"document_id": document_id, "count": len(dtos)},
    )
