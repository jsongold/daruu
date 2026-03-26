"""Autofill Pipeline routes (To-Be architecture).

POST /api/v1/autofill - Auto-fill form fields using the new pipeline.
"""

import logging
from typing import Any  # noqa: F401 — used in type annotations below

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

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
from app.services.form_context import FormContextBuilder, DirectionalFieldEnricher
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
    rule_docs: list[str] | None = Field(
        None, description="Rule document texts for RuleAnalyzer"
    )
    mode: str = Field(
        default="quick",
        description="Autofill mode: 'quick' (one-shot) or 'detailed' (interactive Q&A)",
    )

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
    step_logs: list[dict] = Field(
        default_factory=list, description="Per-step pipeline execution logs"
    )

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


_pipeline_service: AutofillPipelineService | None = None


def get_pipeline_service(
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
    document_service: DocumentService = Depends(get_document_service),
) -> AutofillPipelineService:
    """Get the singleton AutofillPipelineService.

    The service is created once and reused across requests so that
    caches (turn context, enriched fields) survive between turns in
    detailed Q&A mode.  Per-request dependencies (repos, services)
    are injected fresh each time.
    """
    global _pipeline_service

    if _pipeline_service is None:
        from app.services.llm import get_llm_client

        llm_client = get_llm_client()

        enricher = DirectionalFieldEnricher(document_service=document_service)

        context_builder = FormContextBuilder(
            data_source_repo=data_source_repo,
            extraction_service=extraction_service,
            enricher=enricher,
        )
        fill_planner = FillPlanner(llm_client=llm_client)

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

        from app.services.prompt_generator import PromptGenerator, PromptStore
        from app.services.question_generator import QuestionGenerator

        prompt_generator = PromptGenerator(
            llm_client=llm_client,
            document_service=document_service,
        ) if llm_client else None

        prompt_store = PromptStore()

        question_generator = QuestionGenerator(
            llm_client=llm_client,
        ) if llm_client else None

        _pipeline_service = AutofillPipelineService(
            context_builder=context_builder,
            fill_planner=fill_planner,
            form_renderer=form_renderer,
            rule_analyzer=rule_analyzer,
            correction_tracker=correction_tracker,
            prompt_generator=prompt_generator,
            prompt_store=prompt_store,
            question_generator=question_generator,
        )

    # Refresh per-request dependencies (fresh DB connections each request)
    _pipeline_service._context_builder._data_source_repo = data_source_repo
    _pipeline_service._context_builder._extraction_service = extraction_service
    _pipeline_service._context_builder._enricher._document_service = document_service
    if _pipeline_service._prompt_generator:
        _pipeline_service._prompt_generator._document_service = document_service

    return _pipeline_service


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
    rule_docs = tuple(request.rule_docs) if request.rule_docs else ()

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
            rule_docs=rule_docs,
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
        step_logs=[log.model_dump() for log in result.step_logs],
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
            "mode": request.mode,
        },
    )


# ============================================================================
# Detailed Mode: Turn Endpoint DTOs
# ============================================================================


class QuestionOptionDTO(BaseModel):
    """An option in a question."""

    id: str = Field(..., description="Option identifier")
    label: str = Field(..., description="Option display text")

    model_config = {"frozen": True}


class AnswerDTO(BaseModel):
    """A user answer to a question from the draft fill phase."""

    question_id: str = Field(..., description="Question ID this answer responds to")
    question_text: str = Field(default="", description="Original question text")
    selected_option_ids: list[str] = Field(
        default_factory=list, description="Selected option IDs"
    )
    free_text: str | None = Field(None, description="Free text answer")

    model_config = {"frozen": True}


class AutofillTurnRequestDTO(BaseModel):
    """Request body for a single turn in detailed autofill mode (fill-first).

    Turn 1: answers=None -> draft fill + questions.
    Turn 2: answers provided -> final fill with user answers.
    """

    document_id: str = Field(..., min_length=1, description="Target document ID")
    conversation_id: str = Field(
        ..., min_length=1, description="Conversation ID with data sources"
    )
    fields: list[AutofillFieldDTO] = Field(
        ..., min_length=1, description="Fields to fill"
    )
    rules: list[str] | None = Field(None, description="Optional filling rules")
    rule_docs: list[str] | None = Field(
        None, description="Rule document texts for RuleAnalyzer"
    )
    answers: list[AnswerDTO] | None = Field(
        None, description="User answers from the question phase (None on first turn)"
    )

    model_config = {"frozen": True}


class QuestionDTO(BaseModel):
    """A single question in a batch."""

    id: str = Field(..., description="Question identifier (q0, q1, ...)")
    question: str = Field(..., description="Question text")
    question_type: str = Field(..., description="single_choice | multiple_choice | free_text | confirm")
    options: list[QuestionOptionDTO] = Field(
        default_factory=list, description="Options for choice questions"
    )
    context: str | None = Field(None, description="Why the system is asking")

    model_config = {"frozen": True}


class AutofillTurnResponseDTO(BaseModel):
    """Response from a single turn in detailed autofill mode (fill-first).

    Always includes filled_fields (draft or final).
    questions non-empty = draft (show Q&A modal), empty = final (done).
    """

    filled_fields: list[FilledFieldDTO] = Field(
        default_factory=list, description="Filled fields (always present: draft or final)"
    )
    questions: list[QuestionDTO] = Field(
        default_factory=list, description="Non-empty = draft, empty = final"
    )
    skipped_fields: list[str] = Field(
        default_factory=list, description="Skipped field IDs"
    )
    filled_document_ref: str | None = Field(None, description="Filled PDF ref")
    is_draft: bool = Field(default=False, description="True when questions are present")
    processing_time_ms: int = Field(default=0, ge=0, description="Processing time")
    step_logs: list[dict] = Field(
        default_factory=list, description="Per-step pipeline execution logs"
    )

    model_config = {"frozen": True}


# ============================================================================
# Turn Endpoint (Detailed Mode — Phase 3+)
# ============================================================================


@router.post(
    "/turn",
    response_model=ApiResponse[AutofillTurnResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Single turn in detailed autofill mode (fill-first)",
    description="""
Fill-first pipeline for detailed autofill mode.

Turn 1 (answers=null): Draft fill + generate questions from gaps.
Returns filled_fields (draft) + questions. Frontend shows draft values
and QuestionModal.

Turn 2 (answers provided): Re-fill with user answers.
Returns filled_fields (final) + empty questions. Done.
""",
)
async def autofill_turn(
    request: AutofillTurnRequestDTO,
    pipeline: AutofillPipelineService = Depends(get_pipeline_service),
    doc_service: DocumentService = Depends(get_document_service),
) -> ApiResponse[AutofillTurnResponseDTO]:
    """Handle a single turn in detailed autofill mode (fill-first)."""
    has_answers = request.answers is not None and len(request.answers) > 0
    logger.info(
        f"Autofill turn: document={request.document_id}, "
        f"has_answers={has_answers}"
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
    rule_docs = tuple(request.rule_docs) if request.rule_docs else ()

    doc = doc_service.get_document(request.document_id)
    target_ref = doc.ref if doc else request.document_id

    # Convert AnswerDTOs to dicts for the planner
    answers: list[dict[str, Any]] | None = None
    if request.answers:
        answers = [
            {
                "question_id": a.question_id,
                "question_text": a.question_text,
                "selected_option_ids": a.selected_option_ids,
                "free_text": a.free_text,
            }
            for a in request.answers
        ]

    try:
        plan, questions, pipeline_result, step_logs = await pipeline.autofill_turn(
            document_id=request.document_id,
            conversation_id=request.conversation_id,
            fields=fields,
            target_document_ref=target_ref,
            user_rules=user_rules,
            rule_docs=rule_docs,
            answers=answers,
        )
    except Exception as e:
        logger.exception(f"Autofill turn failed: {e}")
        error_dto = AutofillTurnResponseDTO(processing_time_ms=0)
        return ApiResponse(success=False, data=error_dto, error=str(e))

    # Build filled fields from plan
    filled_fields: list[FilledFieldDTO] = []
    skipped_fields: list[str] = []

    for action in plan.actions:
        if action.action == FillActionType.FILL and action.value:
            filled_fields.append(FilledFieldDTO(
                field_id=action.field_id,
                value=action.value,
                confidence=action.confidence,
                source=action.source,
            ))
        elif action.action == FillActionType.SKIP:
            skipped_fields.append(action.field_id)

    # Build question DTOs
    question_dtos = [
        QuestionDTO(
            id=q.id,
            question=q.text,
            question_type=q.type.value,
            options=[
                QuestionOptionDTO(id=o.id, label=o.label)
                for o in q.options
            ],
            context=q.context,
        )
        for q in questions
    ]

    is_draft = len(question_dtos) > 0

    response_dto = AutofillTurnResponseDTO(
        filled_fields=filled_fields,
        questions=question_dtos,
        skipped_fields=skipped_fields,
        filled_document_ref=(
            pipeline_result.report.filled_document_ref if pipeline_result else None
        ),
        is_draft=is_draft,
        processing_time_ms=(
            pipeline_result.processing_time_ms if pipeline_result else 0
        ),
        step_logs=[log.model_dump() for log in step_logs],
    )

    return ApiResponse(success=True, data=response_dto)
