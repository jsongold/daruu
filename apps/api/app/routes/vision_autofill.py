"""Vision Autofill routes.

POST /api/v1/vision-autofill - Auto-fill form fields using LLM vision.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.infrastructure.repositories import (
    get_data_source_repository,
    get_document_repository,
    get_file_repository,
)
from app.config import DEFAULT_MODEL
from app.models.common import ApiResponse
from app.repositories import DataSourceRepository, DocumentRepository, FileRepository
from app.services.document_service import DocumentService
from app.services.text_extraction_service import TextExtractionService
from app.services.vision_autofill import (
    FieldInfo,
    VisionAutofillRequest,
    VisionAutofillService,
)


# ============================================================================
# OpenAI Client Wrapper
# ============================================================================


@dataclass
class LLMResponse:
    """Simple LLM response wrapper."""
    content: str


class OpenAIClient:
    """Simple OpenAI client for autofill."""

    def __init__(self) -> None:
        """Initialize OpenAI client."""
        try:
            from openai import AsyncOpenAI
            api_key = os.getenv("DARU_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("DARU_OPENAI_BASE_URL", "https://api.openai.com/v1")
            self._model = os.getenv("DARU_OPENAI_MODEL", DEFAULT_MODEL)

            if api_key:
                self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            else:
                self._client = None
        except ImportError:
            self._client = None

    @property
    def is_available(self) -> bool:
        """Check if client is available."""
        return self._client is not None

    async def complete(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Call OpenAI API."""
        if not self._client:
            raise RuntimeError("OpenAI client not configured")

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        return LLMResponse(content=content)


# Global client instance
_openai_client: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient | None:
    """Get OpenAI client singleton."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client if _openai_client.is_available else None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vision-autofill", tags=["vision-autofill"])


# ============================================================================
# Request/Response DTOs
# ============================================================================


class FieldInfoDTO(BaseModel):
    """Field information for autofill request."""

    field_id: str = Field(..., min_length=1, description="Unique field identifier")
    label: str = Field(..., min_length=1, description="Field label/name")
    type: str = Field(
        default="text",
        description="Field type: text, date, checkbox, number",
    )
    x: float | None = Field(None, description="Bbox X coordinate")
    y: float | None = Field(None, description="Bbox Y coordinate")
    width: float | None = Field(None, ge=0, description="Bbox width")
    height: float | None = Field(None, ge=0, description="Bbox height")
    page: int | None = Field(None, ge=1, description="Page number")

    model_config = {"frozen": True}


class VisionAutofillRequestDTO(BaseModel):
    """Request body for vision autofill."""

    document_id: str = Field(..., min_length=1, description="Target document ID")
    conversation_id: str = Field(
        ..., min_length=1, description="Conversation ID with data sources"
    )
    fields: list[FieldInfoDTO] = Field(
        ..., min_length=1, description="Fields to fill"
    )
    rules: list[str] | None = Field(
        None, description="Optional rules for field filling"
    )

    model_config = {"frozen": True}


class FilledFieldDTO(BaseModel):
    """A filled field in the response."""

    field_id: str = Field(..., description="Field identifier")
    value: str = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: str | None = Field(None, description="Data source name")

    model_config = {"frozen": True}


class VisionAutofillResponseDTO(BaseModel):
    """Response body for vision autofill."""

    success: bool = Field(..., description="Whether autofill succeeded")
    filled_fields: list[FilledFieldDTO] = Field(
        default_factory=list, description="Filled field values"
    )
    unfilled_fields: list[str] = Field(
        default_factory=list, description="Fields that couldn't be filled"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings about data"
    )
    processing_time_ms: int = Field(
        default=0, ge=0, description="Processing time in ms"
    )
    error: str | None = Field(None, description="Error message if failed")

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


def get_vision_autofill_service(
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
) -> VisionAutofillService:
    """Get the vision autofill service."""
    llm_client = get_openai_client()
    if llm_client:
        logger.info("Using OpenAI for vision autofill")
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
    "",
    response_model=ApiResponse[VisionAutofillResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Auto-fill form fields using AI",
    description="""
Auto-fill form fields by extracting information from user-provided data sources.

This endpoint:
1. Retrieves all data sources linked to the conversation
2. Extracts text and structured data from each source
3. Uses AI to match extracted data to form fields
4. Returns filled values with confidence scores

Data sources can include:
- PDFs (driver's license, passport, etc.)
- Images (photos of documents)
- CSV files (structured data)
- Text content (free-form text)

The service uses semantic matching to align extracted data with form fields,
handling variations in field names and data formats.
""",
    responses={
        200: {"description": "Autofill completed (may have unfilled fields)"},
        400: {"description": "Invalid request"},
        404: {"description": "Conversation or document not found"},
    },
)
async def vision_autofill(
    request: VisionAutofillRequestDTO,
    service: VisionAutofillService = Depends(get_vision_autofill_service),
) -> ApiResponse[VisionAutofillResponseDTO]:
    """Auto-fill form fields using AI vision.

    Args:
        request: Autofill request with document and field definitions.
        service: Injected VisionAutofillService instance.

    Returns:
        API response with autofill results.
    """
    logger.info(
        f"Vision autofill request: document={request.document_id}, "
        f"conversation={request.conversation_id}, fields={len(request.fields)}"
    )

    # Convert DTO to domain model
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
    )

    # Call the service
    result = await service.autofill(domain_request)

    # Convert to response DTO
    response_dto = VisionAutofillResponseDTO(
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

    logger.info(
        f"Vision autofill completed: filled={len(response_dto.filled_fields)}, "
        f"unfilled={len(response_dto.unfilled_fields)}, "
        f"time_ms={response_dto.processing_time_ms}"
    )

    return ApiResponse(
        success=response_dto.success,
        data=response_dto,
        meta={
            "document_id": request.document_id,
            "conversation_id": request.conversation_id,
            "total_fields": len(request.fields),
            "filled_count": len(response_dto.filled_fields),
            "unfilled_count": len(response_dto.unfilled_fields),
            "processing_time_ms": response_dto.processing_time_ms,
        },
    )
