"""Tests for AutofillPipelineService fill-first detailed mode (autofill_turn)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.models.fill_plan import (
    FieldFillAction,
    FieldQuestion,
    FillActionType,
    FillPlan,
    QuestionOption,
    QuestionType,
)
from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
)
from app.domain.models.render_report import RenderReport
from app.services.autofill_pipeline.models import AutofillPipelineResult
from app.services.autofill_pipeline.service import AutofillPipelineService


# ── Fixtures ──


def _make_fields() -> tuple[FormFieldSpec, ...]:
    return (
        FormFieldSpec(field_id="Text1", label="Name", field_type="text", page=1),
        FormFieldSpec(field_id="Text2", label="Address", field_type="text", page=1),
        FormFieldSpec(field_id="Text3", label="DOB", field_type="date", page=1),
    )


def _make_context() -> FormContext:
    return FormContext(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        data_sources=(
            DataSourceEntry(
                source_name="src.pdf",
                source_type="pdf",
                extracted_fields={"Name": "John"},
            ),
        ),
        mapping_candidates=(),
        rules=(),
    )


def _make_draft_plan() -> FillPlan:
    return FillPlan(
        document_id="doc-1",
        actions=(
            FieldFillAction(field_id="Text1", action=FillActionType.FILL, value="John", confidence=0.95, source="src.pdf"),
            FieldFillAction(field_id="Text2", action=FillActionType.SKIP, reason="no data"),
            FieldFillAction(field_id="Text3", action=FillActionType.FILL, value="1990-01-01", confidence=0.5, source="src.pdf"),
        ),
    )


def _make_final_plan() -> FillPlan:
    return FillPlan(
        document_id="doc-1",
        actions=(
            FieldFillAction(field_id="Text1", action=FillActionType.FILL, value="John", confidence=0.95),
            FieldFillAction(field_id="Text2", action=FillActionType.FILL, value="123 Main St", confidence=0.95),
            FieldFillAction(field_id="Text3", action=FillActionType.FILL, value="1990-05-15", confidence=0.95),
        ),
    )


def _make_questions() -> tuple[FieldQuestion, ...]:
    return (
        FieldQuestion(
            id="q1",
            text="What is your address?",
            type=QuestionType.FREE_TEXT,
        ),
        FieldQuestion(
            id="q2",
            text="Is your DOB 1990-01-01?",
            type=QuestionType.CONFIRM,
            options=(
                QuestionOption(id="yes", label="Yes"),
                QuestionOption(id="no", label="No"),
            ),
        ),
    )


def _make_render_report() -> RenderReport:
    return RenderReport(
        success=True,
        filled_count=2,
        failed_count=0,
        filled_document_ref="filled.pdf",
        field_results=(),
    )


def _build_service(
    plan_return: FillPlan | None = None,
    plan_with_answers_return: FillPlan | None = None,
    questions_return: tuple[FieldQuestion, ...] = (),
    context_return: FormContext | None = None,
    prompt_result: str | None = None,
) -> AutofillPipelineService:
    """Build an AutofillPipelineService with mocked dependencies."""
    context = context_return or _make_context()

    context_builder = MagicMock()
    context_builder.build = AsyncMock(return_value=context)

    fill_planner = MagicMock()
    fill_planner.plan = AsyncMock(return_value=plan_return or _make_draft_plan())
    fill_planner.plan_with_answers = AsyncMock(return_value=plan_with_answers_return or _make_final_plan())
    fill_planner.set_specialized_prompt = MagicMock()

    form_renderer = MagicMock()
    form_renderer.render = AsyncMock(return_value=_make_render_report())

    rule_analyzer = MagicMock()
    rule_analyzer.analyze = AsyncMock(return_value=[])

    correction_tracker = MagicMock()

    question_generator = MagicMock()
    question_generator.generate = AsyncMock(return_value=questions_return)

    prompt_generator = None
    prompt_store = None

    return AutofillPipelineService(
        context_builder=context_builder,
        fill_planner=fill_planner,
        form_renderer=form_renderer,
        rule_analyzer=rule_analyzer,
        correction_tracker=correction_tracker,
        prompt_generator=prompt_generator,
        prompt_store=prompt_store,
        question_generator=question_generator,
    )


# ── Tests ──


@pytest.mark.asyncio
async def test_turn1_returns_draft_and_questions() -> None:
    """Turn 1 (no answers) should return draft plan + generated questions."""
    questions = _make_questions()
    service = _build_service(questions_return=questions)

    plan, qs, result, step_logs = await service.autofill_turn(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        target_document_ref="target.pdf",
    )

    # Draft plan returned
    assert len(plan.actions) == 3
    fill_count = sum(1 for a in plan.actions if a.action == FillActionType.FILL)
    assert fill_count == 2

    # Questions returned
    assert len(qs) == 2
    assert qs[0].id == "q1"
    assert qs[1].id == "q2"

    # Pipeline result present
    assert result is not None

    # Step logs include context_build, fill_plan, render, question_gen
    step_names = [sl.step_name for sl in step_logs]
    assert "context_build" in step_names
    assert "fill_plan" in step_names
    assert "render" in step_names
    assert "question_gen" in step_names


@pytest.mark.asyncio
async def test_turn2_returns_final_no_questions() -> None:
    """Turn 2 (with answers) should return final plan with no questions."""
    service = _build_service()

    # Simulate turn 1 to cache context
    await service.autofill_turn(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        target_document_ref="target.pdf",
    )

    # Turn 2 with answers
    answers = [
        {"question_id": "q1", "question_text": "What is your address?", "free_text": "123 Main St"},
        {"question_id": "q2", "question_text": "Is your DOB 1990-01-01?", "selected_option_ids": ["no"], "free_text": "1990-05-15"},
    ]

    plan, qs, result, step_logs = await service.autofill_turn(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        target_document_ref="target.pdf",
        answers=answers,
    )

    # Final plan — all fields filled
    fill_count = sum(1 for a in plan.actions if a.action == FillActionType.FILL)
    assert fill_count == 3

    # No questions
    assert qs == ()

    # Pipeline result present
    assert result is not None

    # plan_with_answers was called
    planner = service._fill_planner
    planner.plan_with_answers.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_cached_between_turns() -> None:
    """Context built on turn 1 should be reused on turn 2."""
    service = _build_service()

    # Turn 1
    await service.autofill_turn(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        target_document_ref="target.pdf",
    )

    # Turn 2
    await service.autofill_turn(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        target_document_ref="target.pdf",
        answers=[{"question_id": "q1", "question_text": "test", "free_text": "val"}],
    )

    # Context builder should only be called once (turn 1)
    builder = service._context_builder
    builder.build.assert_awaited_once()


@pytest.mark.asyncio
async def test_turn1_without_question_generator() -> None:
    """Turn 1 without a QuestionGenerator should return empty questions."""
    context = _make_context()

    context_builder = MagicMock()
    context_builder.build = AsyncMock(return_value=context)

    fill_planner = MagicMock()
    fill_planner.plan = AsyncMock(return_value=_make_draft_plan())
    fill_planner.set_specialized_prompt = MagicMock()

    form_renderer = MagicMock()
    form_renderer.render = AsyncMock(return_value=_make_render_report())

    rule_analyzer = MagicMock()
    rule_analyzer.analyze = AsyncMock(return_value=[])

    correction_tracker = MagicMock()

    service = AutofillPipelineService(
        context_builder=context_builder,
        fill_planner=fill_planner,
        form_renderer=form_renderer,
        rule_analyzer=rule_analyzer,
        correction_tracker=correction_tracker,
        question_generator=None,  # No question generator
    )

    plan, qs, result, step_logs = await service.autofill_turn(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        target_document_ref="target.pdf",
    )

    assert qs == ()
    assert plan is not None
    assert result is not None


@pytest.mark.asyncio
async def test_different_sessions_get_separate_caches() -> None:
    """Different (doc_id, conv_id) pairs should have independent caches."""
    service = _build_service()

    # Turn 1 for session A
    await service.autofill_turn(
        document_id="doc-A",
        conversation_id="conv-A",
        fields=_make_fields(),
        target_document_ref="target-A.pdf",
    )

    # Turn 1 for session B
    await service.autofill_turn(
        document_id="doc-B",
        conversation_id="conv-B",
        fields=_make_fields(),
        target_document_ref="target-B.pdf",
    )

    # Context builder should be called twice (once per session)
    builder = service._context_builder
    assert builder.build.await_count == 2
