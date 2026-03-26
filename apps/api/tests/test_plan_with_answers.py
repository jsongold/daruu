"""Tests for FillPlanner.plan_with_answers()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.domain.models.fill_plan import FillActionType, FillPlan
from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
    MappingCandidate,
)
from app.services.fill_planner.planner import FillPlanner
from app.services.fill_planner.schemas import LLMFilledField, LLMFillResponse

# ── Fixtures ──


def _make_fields() -> tuple[FormFieldSpec, ...]:
    return (
        FormFieldSpec(
            field_id="Text1",
            label="氏名",
            field_type="text",
            page=1,
        ),
        FormFieldSpec(
            field_id="Text2",
            label="住所",
            field_type="text",
            page=1,
        ),
        FormFieldSpec(
            field_id="Text3",
            label="生年月日",
            field_type="date",
            page=1,
        ),
    )


def _make_context(
    fields: tuple[FormFieldSpec, ...] | None = None,
    data_sources: tuple[DataSourceEntry, ...] = (),
    mapping_candidates: tuple[MappingCandidate, ...] = (),
) -> FormContext:
    return FormContext(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=fields or _make_fields(),
        data_sources=data_sources,
        mapping_candidates=mapping_candidates,
        rules=(),
    )


def _make_instructor_client(
    fill_response: LLMFillResponse,
) -> MagicMock:
    """Create a mock client with Instructor's create() method."""
    client = MagicMock()
    client.model = "gpt-4o-mini"
    client.create = AsyncMock(return_value=fill_response)
    return client


# ── Tests: plan_with_answers() ──


@pytest.mark.asyncio
async def test_answers_override_skipped() -> None:
    """User answers should fill fields that were previously skipped."""
    context = _make_context(
        data_sources=(
            DataSourceEntry(
                source_name="resume.pdf",
                source_type="pdf",
                extracted_fields={"氏名": "山田太郎"},
            ),
        )
    )

    # Simulate: LLM fills Text1 (name) and Text3 (date) with answers,
    # Text2 (address) comes from user answer
    fill_response = LLMFillResponse(
        filled_fields=[
            LLMFilledField(
                field_id="Text1", value="山田太郎", confidence=0.95, source="resume.pdf"
            ),
            LLMFilledField(
                field_id="Text2", value="東京都新宿区", confidence=0.95, source="user_answer"
            ),
            LLMFilledField(
                field_id="Text3", value="1990-01-15", confidence=0.95, source="user_answer"
            ),
        ],
    )

    client = _make_instructor_client(fill_response)
    planner = FillPlanner(llm_client=client)

    answers = [
        {
            "question_id": "q1",
            "question_text": "住所を教えてください",
            "selected_option_ids": [],
            "free_text": "東京都新宿区",
        },
        {
            "question_id": "q2",
            "question_text": "生年月日は？",
            "selected_option_ids": [],
            "free_text": "1990-01-15",
        },
    ]

    plan = await planner.plan_with_answers(context, answers)

    assert isinstance(plan, FillPlan)
    assert len(plan.actions) == 3

    filled = {a.field_id: a for a in plan.actions if a.action == FillActionType.FILL}
    assert "Text1" in filled
    assert filled["Text1"].value == "山田太郎"
    assert "Text2" in filled
    assert filled["Text2"].value == "東京都新宿区"
    assert "Text3" in filled
    assert filled["Text3"].value == "1990-01-15"

    # Verify create was called with messages containing user answers
    client.create.assert_awaited_once()
    call_kwargs = client.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_msg = messages[-1]["content"]
    assert "東京都新宿区" in user_msg
    assert "1990-01-15" in user_msg


@pytest.mark.asyncio
async def test_answers_combined_with_sources() -> None:
    """Answers should be combined with data source values in the prompt."""
    context = _make_context(
        data_sources=(
            DataSourceEntry(
                source_name="id_card.jpg",
                source_type="image",
                extracted_fields={"氏名": "佐藤花子", "住所": "大阪府"},
            ),
        )
    )

    fill_response = LLMFillResponse(
        filled_fields=[
            LLMFilledField(
                field_id="Text1", value="佐藤花子", confidence=0.95, source="id_card.jpg"
            ),
            LLMFilledField(field_id="Text2", value="大阪府", confidence=0.9, source="id_card.jpg"),
            LLMFilledField(
                field_id="Text3", value="1985-03-20", confidence=0.95, source="user_answer"
            ),
        ],
    )

    client = _make_instructor_client(fill_response)
    planner = FillPlanner(llm_client=client)

    answers = [
        {
            "question_id": "q1",
            "question_text": "生年月日は？",
            "selected_option_ids": [],
            "free_text": "1985-03-20",
        },
    ]

    plan = await planner.plan_with_answers(context, answers)

    filled_ids = {a.field_id for a in plan.actions if a.action == FillActionType.FILL}
    assert filled_ids == {"Text1", "Text2", "Text3"}

    # Verify prompt mentions both data sources and answers
    call_kwargs = client.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_msg = messages[-1]["content"]
    assert "User-Provided Answers" in user_msg
    assert "1985-03-20" in user_msg


@pytest.mark.asyncio
async def test_no_llm_fallback() -> None:
    """Without LLM, plan_with_answers should fall back to candidate-based plan."""
    context = _make_context(
        mapping_candidates=(
            MappingCandidate(
                field_id="Text1",
                source_key="氏名",
                source_value="田中一郎",
                source_name="src1",
                score=0.8,
            ),
        ),
    )

    planner = FillPlanner(llm_client=None)
    answers = [{"question_id": "q1", "question_text": "test", "free_text": "value"}]

    plan = await planner.plan_with_answers(context, answers)

    assert isinstance(plan, FillPlan)
    # Should use candidate plan (only Text1 has a match)
    filled = [a for a in plan.actions if a.action == FillActionType.FILL]
    assert len(filled) == 1
    assert filled[0].field_id == "Text1"


@pytest.mark.asyncio
async def test_answers_with_selected_options() -> None:
    """Selected option answers should be formatted in the prompt."""
    context = _make_context()

    fill_response = LLMFillResponse(
        filled_fields=[
            LLMFilledField(field_id="Text1", value="山田太郎", confidence=0.95),
            LLMFilledField(field_id="Text2", value="東京都", confidence=0.95),
            LLMFilledField(field_id="Text3", value="1990-01-01", confidence=0.95),
        ],
    )

    client = _make_instructor_client(fill_response)
    planner = FillPlanner(llm_client=client)

    answers = [
        {
            "question_id": "q1",
            "question_text": "性別は？",
            "selected_option_ids": ["male"],
            "free_text": None,
        },
    ]

    plan = await planner.plan_with_answers(context, answers)

    # Verify the prompt includes selected option
    call_kwargs = client.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_msg = messages[-1]["content"]
    assert "male" in user_msg


@pytest.mark.asyncio
async def test_specialized_prompt_used_for_refill() -> None:
    """When a specialized prompt is set, it should be used as system prompt for refill."""
    context = _make_context()

    fill_response = LLMFillResponse(
        filled_fields=[
            LLMFilledField(field_id="Text1", value="v1", confidence=0.95),
            LLMFilledField(field_id="Text2", value="v2", confidence=0.95),
            LLMFilledField(field_id="Text3", value="v3", confidence=0.95),
        ],
    )

    client = _make_instructor_client(fill_response)
    planner = FillPlanner(llm_client=client)
    planner.set_specialized_prompt("Custom specialized prompt for this form.")

    answers = [{"question_id": "q1", "question_text": "test", "free_text": "val"}]
    plan = await planner.plan_with_answers(context, answers)

    call_kwargs = client.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    system_msg = messages[0]["content"]
    assert system_msg == "Custom specialized prompt for this form."
    assert plan.system_prompt == "Custom specialized prompt for this form."
