"""Autofill Pipeline routes (To-Be architecture).

POST /api/v1/autofill - Auto-fill form fields using the new pipeline.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.infrastructure.repositories import (
    get_correction_repository,
    get_data_source_repository,
    get_document_repository,
    get_file_repository,
    get_rule_snippet_repository,
)
from app.models.common import ApiResponse
from app.repositories import DataSourceRepository, DocumentRepository, FileRepository
from app.services.document_service import DocumentService
from app.services.text_extraction_service import TextExtractionService

from app.domain.models.fill_plan import FillActionType
from app.domain.models.form_context import FormFieldSpec
from app.services.autofill_pipeline import AutofillPipelineService
from app.services.form_context import FormContextBuilder
from app.services.fill_planner import FillPlanner
from app.services.form_renderer import FormRenderer
from app.services.rule_analyzer import RuleAnalyzer, RuleAnalyzerStub
from app.services.correction_tracker import CorrectionTracker, CorrectionTrackerStub

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autofill", tags=["autofill-pipeline"])


# ============================================================================
# Request/Response DTOs
# ============================================================================


class AutofillFieldDTO(BaseModel):
    """Field information for autofill request."""

    field_id: str = Field(..., min_length=1, description="Unique field identifier")
    label: str = Field(..., min_length=1, description="Field label/name")
    type: str = Field(default="text", description="Field type: text, date, checkbox, number")
    x: float | None = Field(None, description="Bbox X coordinate")
    y: float | None = Field(None, description="Bbox Y coordinate")
    width: float | None = Field(None, ge=0, description="Bbox width")
    height: float | None = Field(None, ge=0, description="Bbox height")
    page: int | None = Field(None, ge=1, description="Page number")

    model_config = {"frozen": True}


class AutofillRequestDTO(BaseModel):
    """Request body for autofill pipeline."""

    document_id: str = Field(..., min_length=1, description="Target document ID")
    conversation_id: str = Field(
        ..., min_length=1, description="Conversation ID with data sources"
    )
    fields: list[AutofillFieldDTO] = Field(
        ..., min_length=1, description="Fields to fill"
    )
    rules: list[str] | None = Field(None, description="Optional filling rules")

    model_config = {"frozen": True}


class FilledFieldDTO(BaseModel):
    """A filled field in the response."""

    field_id: str = Field(..., description="Field identifier")
    value: str = Field(..., description="Filled value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: str | None = Field(None, description="Data source name")

    model_config = {"frozen": True}


class AutofillResponseDTO(BaseModel):
    """Response body for autofill pipeline."""

    success: bool = Field(..., description="Whether autofill succeeded")
    filled_fields: list[FilledFieldDTO] = Field(
        default_factory=list, description="Fields that were filled"
    )
    unfilled_fields: list[str] = Field(
        default_factory=list, description="Fields that could not be filled"
    )
    skipped_fields: list[str] = Field(
        default_factory=list, description="Fields explicitly skipped"
    )
    ask_user_fields: list[str] = Field(
        default_factory=list, description="Fields requiring user input"
    )
    filled_document_ref: str | None = Field(
        None, description="Reference to the filled PDF"
    )
    processing_time_ms: int = Field(default=0, ge=0, description="Processing time in ms")
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


def get_pipeline_service(
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
    document_service: DocumentService = Depends(get_document_service),
) -> AutofillPipelineService:
    """Build and return the AutofillPipelineService with all dependencies."""
    from app.routes.vision_autofill import get_openai_client

    context_builder = FormContextBuilder(
        data_source_repo=data_source_repo,
        extraction_service=extraction_service,
        document_service=document_service,
    )

    llm_client = get_openai_client()
    fill_planner = FillPlanner(llm_client=llm_client)

    # FormRenderer needs a FillService — for now we import a factory
    # that creates a FillService with all adapters.
    # In Phase 2 we use a lightweight wrapper; real DI comes later.
    form_renderer = _build_form_renderer()

    if llm_client is not None:
        from app.infrastructure.gateways.embedding import (
            MockEmbeddingGateway,
            OpenAIEmbeddingGateway,
        )

        snippet_repo = get_rule_snippet_repository()
        try:
            embedding_gw = OpenAIEmbeddingGateway(client=llm_client)
        except Exception:
            embedding_gw = MockEmbeddingGateway()
        rule_analyzer = RuleAnalyzer(
            llm_client=llm_client,
            snippet_repo=snippet_repo,
            embedding_gateway=embedding_gw,
        )
    else:
        rule_analyzer = RuleAnalyzerStub()

    correction_repo = get_correction_repository()
    correction_tracker = CorrectionTracker(repository=correction_repo)

    return AutofillPipelineService(
        context_builder=context_builder,
        fill_planner=fill_planner,
        form_renderer=form_renderer,
        rule_analyzer=rule_analyzer,
        correction_tracker=correction_tracker,
    )


def _build_form_renderer() -> FormRenderer:
    """Build FormRenderer with FillService and its adapters.

    Uses the same adapter setup as the fill_service route.
    """
    from app.services.fill import (
        FillService,
        LocalStorageAdapter,
        PyMuPdfAcroFormAdapter,
        PyMuPdfMergerAdapter,
        PyMuPdfReaderAdapter,
        ReportlabMeasureAdapter,
        ReportlabOverlayAdapter,
    )

    fill_service = FillService(
        pdf_reader=PyMuPdfReaderAdapter(),
        acroform_writer=PyMuPdfAcroFormAdapter(),
        overlay_renderer=ReportlabOverlayAdapter(),
        pdf_merger=PyMuPdfMergerAdapter(),
        storage=LocalStorageAdapter(base_path="/tmp/fill-service"),
        text_measure=ReportlabMeasureAdapter(),
    )

    return FormRenderer(fill_service=fill_service)


# ============================================================================
# Route Handlers
# ============================================================================


@router.post(
    "",
    response_model=ApiResponse[AutofillResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Auto-fill form fields using the To-Be pipeline",
    description="""
Auto-fill form fields using the new architecture pipeline:
FormContextBuilder -> FillPlanner -> FormRenderer.

This endpoint provides the same functionality as /vision-autofill
but uses the new modular pipeline architecture.
""",
    responses={
        200: {"description": "Autofill completed"},
        400: {"description": "Invalid request"},
    },
)
async def autofill_pipeline(
    request: AutofillRequestDTO,
    pipeline: AutofillPipelineService = Depends(get_pipeline_service),
    doc_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[AutofillResponseDTO]:
    """Auto-fill form fields using the To-Be pipeline.

    Args:
        request: Autofill request with document and field definitions.
        pipeline: Injected pipeline service.
        doc_service: Document service for resolving document refs.

    Returns:
        API response with autofill results.
    """
    logger.info(
        f"Autofill pipeline request: document={request.document_id}, "
        f"conversation={request.conversation_id}, fields={len(request.fields)}"
    )

    fields = tuple(
        FormFieldSpec(
            field_id=f.field_id,
            label=f.label,
            field_type=f.type,
            page=f.page,
            x=f.x,
            y=f.y,
            width=f.width,
            height=f.height,
        )
        for f in request.fields
    )

    user_rules = tuple(request.rules) if request.rules else ()

    # Resolve document reference
    doc = doc_service.get_document(request.document_id)
    target_ref = doc.ref if doc else request.document_id

    try:
        result = await pipeline.autofill(
            document_id=request.document_id,
            conversation_id=request.conversation_id,
            fields=fields,
            target_document_ref=target_ref,
            user_rules=user_rules,
        )
    except Exception as e:
        logger.exception(f"Autofill pipeline failed: {e}")
        error_dto = AutofillResponseDTO(
            success=False,
            error=str(e),
        )
        return ApiResponse(success=False, data=error_dto, error=str(e))

    # Map plan actions to response categories
    filled_fields: list[FilledFieldDTO] = []
    unfilled_fields: list[str] = []
    skipped_fields: list[str] = []
    ask_user_fields: list[str] = []

    for action in result.plan.actions:
        if action.action == FillActionType.FILL and action.value:
            filled_fields.append(FilledFieldDTO(
                field_id=action.field_id,
                value=action.value,
                confidence=action.confidence,
                source=action.source,
            ))
        elif action.action == FillActionType.ASK_USER:
            ask_user_fields.append(action.field_id)
        elif action.action == FillActionType.SKIP:
            skipped_fields.append(action.field_id)
        else:
            unfilled_fields.append(action.field_id)

    response_dto = AutofillResponseDTO(
        success=result.report.success,
        filled_fields=filled_fields,
        unfilled_fields=unfilled_fields,
        skipped_fields=skipped_fields,
        ask_user_fields=ask_user_fields,
        filled_document_ref=result.report.filled_document_ref,
        processing_time_ms=result.processing_time_ms,
    )

    logger.info(
        f"Autofill pipeline completed: filled={len(filled_fields)}, "
        f"skipped={len(skipped_fields)}, time_ms={result.processing_time_ms}"
    )

    return ApiResponse(
        success=response_dto.success,
        data=response_dto,
        meta={
            "document_id": request.document_id,
            "conversation_id": request.conversation_id,
            "total_fields": len(request.fields),
            "filled_count": len(filled_fields),
            "skipped_count": len(skipped_fields),
            "ask_user_count": len(ask_user_fields),
            "processing_time_ms": result.processing_time_ms,
        },
    )
