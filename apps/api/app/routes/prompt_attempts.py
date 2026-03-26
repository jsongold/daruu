"""Prompt Attempts routes (prompt tuning feature).

POST /api/v1/prompt-attempts/run   - Run autofill and store the attempt
GET  /api/v1/prompt-attempts       - List attempts for a conversation
GET  /api/v1/prompt-attempts/{id}  - Get a single attempt
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from app.infrastructure.repositories import (
    get_data_source_repository,
    get_document_repository,
    get_file_repository,
    get_prompt_attempt_repository,
)
from app.models.common import ApiResponse
from app.models.prompt_attempt import PromptAttempt
from app.repositories import DataSourceRepository, DocumentRepository, FileRepository
from app.repositories.prompt_attempt_repository import PromptAttemptRepository
from app.routes.vision_autofill import (
    FilledFieldDTO,
    VisionAutofillRequestDTO,
    VisionAutofillResponseDTO,
    get_openai_client,
)
from app.services.document_service import DocumentService
from app.services.text_extraction_service import TextExtractionService
from app.services.vision_autofill import (
    FieldInfo,
    VisionAutofillRequest,
    VisionAutofillService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompt-attempts", tags=["prompt-attempts"])


# ============================================================================
# DTOs
# ============================================================================


class PromptAttemptDTO(BaseModel):
    """Response for a single prompt attempt."""

    id: str = Field(..., description="Unique attempt ID")
    conversation_id: str = Field(..., description="Conversation ID")
    document_id: str = Field(..., description="Document ID")
    system_prompt: str = Field(..., description="System prompt sent to LLM")
    user_prompt: str = Field(..., description="User prompt sent to LLM")
    custom_rules: list[str] = Field(default_factory=list, description="Custom rules")
    raw_response: str = Field(default="", description="Raw LLM response text")
    parsed_result: dict[str, Any] | None = Field(None, description="Parsed result JSON")
    success: bool = Field(..., description="Whether attempt succeeded")
    error: str | None = Field(None, description="Error message")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"frozen": True}

    @classmethod
    def from_model(cls, attempt: PromptAttempt) -> "PromptAttemptDTO":
        """Create DTO from domain model."""
        return cls(
            id=attempt.id,
            conversation_id=attempt.conversation_id,
            document_id=attempt.document_id,
            system_prompt=attempt.system_prompt,
            user_prompt=attempt.user_prompt,
            custom_rules=attempt.custom_rules,
            raw_response=attempt.raw_response,
            parsed_result=attempt.parsed_result,
            success=attempt.success,
            error=attempt.error,
            metadata=attempt.metadata,
            created_at=attempt.created_at,
        )


class PromptAttemptListDTO(BaseModel):
    """Response for list of prompt attempts."""

    items: list[PromptAttemptDTO] = Field(..., description="List of attempts")
    total: int = Field(..., ge=0, description="Total count")

    model_config = {"frozen": True}


class RunAttemptResponseDTO(BaseModel):
    """Response from running a prompt attempt."""

    attempt_id: str = Field(..., description="ID of the stored attempt")
    autofill: VisionAutofillResponseDTO = Field(..., description="Autofill result")

    model_config = {"frozen": True}


# ============================================================================
# Dependencies
# ============================================================================


def get_data_source_repo() -> DataSourceRepository:
    """Get the data source repository."""
    return get_data_source_repository()


def get_document_repo() -> DocumentRepository:
    """Get the document repository."""
    return get_document_repository()


def get_file_repo() -> FileRepository:
    """Get the file repository."""
    return get_file_repository()


def get_document_service(
    doc_repo: DocumentRepository = Depends(get_document_repo),
    file_repo: FileRepository = Depends(get_file_repo),
) -> DocumentService:
    """Get the document service."""
    return DocumentService(document_repository=doc_repo, file_repository=file_repo)


def get_text_extraction_service(
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    document_service: DocumentService = Depends(get_document_service),
) -> TextExtractionService:
    """Get the text extraction service."""
    return TextExtractionService(
        data_source_repo=data_source_repo,
        document_service=document_service,
    )


def get_prompt_attempt_repo() -> PromptAttemptRepository:
    """Get the prompt attempt repository."""
    return get_prompt_attempt_repository()


def get_vision_autofill_service(
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
) -> VisionAutofillService:
    """Get the vision autofill service."""
    llm_client = get_openai_client()
    if llm_client:
        logger.info("Using OpenAI for prompt attempt autofill")
    else:
        logger.warning("OpenAI not configured, using rule-based autofill")

    return VisionAutofillService(
        data_source_repo=data_source_repo,
        extraction_service=extraction_service,
        llm_client=llm_client,
    )


# ============================================================================
# Route Handlers
# ============================================================================


@router.post(
    "/run",
    response_model=ApiResponse[RunAttemptResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Run autofill and store the attempt",
    description="Runs autofill using the production service, then stores the "
    "prompt/response pair as a prompt attempt for the tuning history.",
)
async def run_prompt_attempt(
    request: VisionAutofillRequestDTO,
    service: VisionAutofillService = Depends(get_vision_autofill_service),
    repo: PromptAttemptRepository = Depends(get_prompt_attempt_repo),
) -> ApiResponse[RunAttemptResponseDTO]:
    """Run autofill and persist the attempt."""
    logger.info(
        f"Prompt attempt run: document={request.document_id}, "
        f"conversation={request.conversation_id}, fields={len(request.fields)}"
    )

    domain_request = VisionAutofillRequest(
        document_id=request.document_id,
        conversation_id=request.conversation_id,
        fields=[
            FieldInfo(
                field_id=f.field_id,
                label=f.label,
                type=f.type,
                x=f.x,
                y=f.y,
                width=f.width,
                height=f.height,
                page=f.page,
            )
            for f in request.fields
        ],
        rules=request.rules,
        system_prompt=request.system_prompt,
    )

    result = await service.autofill(domain_request)

    # Store the attempt
    attempt = repo.create(
        conversation_id=request.conversation_id,
        document_id=request.document_id,
        system_prompt=result.system_prompt or "",
        user_prompt=result.user_prompt or "",
        custom_rules=request.rules,
        raw_response=result.raw_response or "",
        parsed_result=(
            {"filled_fields": [f.model_dump() for f in result.filled_fields]}
            if result.success
            else None
        ),
        success=result.success,
        error=result.error,
        metadata={"processing_time_ms": result.processing_time_ms},
    )

    autofill_dto = VisionAutofillResponseDTO(
        success=result.success,
        filled_fields=[
            FilledFieldDTO(
                field_id=f.field_id,
                value=f.value,
                confidence=f.confidence,
                source=f.source,
            )
            for f in result.filled_fields
        ],
        unfilled_fields=result.unfilled_fields,
        warnings=result.warnings,
        processing_time_ms=result.processing_time_ms,
        error=result.error,
    )

    response_dto = RunAttemptResponseDTO(
        attempt_id=attempt.id,
        autofill=autofill_dto,
    )

    return ApiResponse(
        success=result.success,
        data=response_dto,
    )


@router.get(
    "",
    response_model=ApiResponse[PromptAttemptListDTO],
    status_code=status.HTTP_200_OK,
    summary="List prompt attempts for a conversation",
    description="Returns paginated list of prompt tuning attempts with metadata.",
)
async def list_prompt_attempts(
    conversation_id: str = Query(..., min_length=1, description="Conversation ID"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Results to skip"),
    repo: PromptAttemptRepository = Depends(get_prompt_attempt_repo),
) -> ApiResponse[PromptAttemptListDTO]:
    """List prompt attempts for a conversation."""
    attempts = repo.list_by_conversation(
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )
    total = repo.count_by_conversation(conversation_id)

    response_dto = PromptAttemptListDTO(
        items=[PromptAttemptDTO.from_model(a) for a in attempts],
        total=total,
    )

    return ApiResponse(
        success=True,
        data=response_dto,
    )


@router.get(
    "/{attempt_id}",
    response_model=ApiResponse[PromptAttemptDTO],
    status_code=status.HTTP_200_OK,
    summary="Get a single prompt attempt",
    description="Returns full detail of a prompt attempt including raw request/response.",
)
async def get_prompt_attempt(
    attempt_id: str,
    repo: PromptAttemptRepository = Depends(get_prompt_attempt_repo),
) -> ApiResponse[PromptAttemptDTO]:
    """Get a single prompt attempt by ID."""
    attempt = repo.get(attempt_id)
    if not attempt:
        return ApiResponse(
            success=False,
            data=None,
            error=f"Prompt attempt {attempt_id} not found",
        )

    return ApiResponse(
        success=True,
        data=PromptAttemptDTO.from_model(attempt),
    )
