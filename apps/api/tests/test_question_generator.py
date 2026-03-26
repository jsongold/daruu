"""Tests for QuestionGenerator service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models.fill_plan import (
    FieldFillAction,
    FieldQuestion,
    FillActionType,
    FillPlan,
    QuestionType,
)
from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
    LabelCandidate,
)
from app.services.question_generator.generator import QuestionGenerator


# ── Fixtures ──


@dataclass
class FakeLLMResponse:
    content: str


def _make_fields(count: int = 5) -> tuple[FormFieldSpec, ...]:
    labels = ["氏名", "住所", "生年月日", "電話番号", "メールアドレス"]
    return tuple(
        FormFieldSpec(
            field_id=f"Text{i + 1}",
            label=f"Text{i + 1}",
            field_type="text",
            page=1,
            label_candidates=(
                LabelCandidate(text=labels[i], confidence=0.9, page=1),
            ) if i < len(labels) else (),
        )
        for i in range(count)
    )


def _make_context(
    fields: tuple[FormFieldSpec, ...] | None = None,
) -> FormContext:
    return FormContext(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=fields or _make_fields(),
        data_sources=(
            DataSourceEntry(
                source_name="resume.pdf",
                source_type="pdf",
                extracted_fields={"氏名": "山田太郎", "住所": "東京都渋谷区"},
            ),
        ),
        mapping_candidates=(),
        rules=(),
    )


def _make_plan(
    actions: tuple[FieldFillAction, ...],
) -> FillPlan:
    return FillPlan(
        document_id="doc-1",
        actions=actions,
    )


def _make_llm_response(questions: list[dict]) -> FakeLLMResponse:
    return FakeLLMResponse(content=json.dumps({"questions": questions}))


# ── Tests: generate() ──


@pytest.mark.asyncio
async def test_questions_from_skipped_fields() -> None:
    """Skipped fields should produce questions."""
    fields = _make_fields(3)
    context = _make_context(fields)

    actions = (
        FieldFillAction(field_id="Text1", action=FillActionType.FILL, value="山田太郎", confidence=0.95, source="resume.pdf"),
        FieldFillAction(field_id="Text2", action=FillActionType.SKIP, reason="no data found"),
        FieldFillAction(field_id="Text3", action=FillActionType.SKIP, reason="no data found"),
    )
    plan = _make_plan(actions)

    llm_response = _make_llm_response([
        {
            "id": "q1",
            "question": "住所を教えてください",
            "question_type": "free_text",
            "context": "データソースに住所が見つかりませんでした",
        },
        {
            "id": "q2",
            "question": "生年月日を教えてください",
            "question_type": "free_text",
        },
    ])

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)

    generator = QuestionGenerator(llm_client=llm_client)
    questions = await generator.generate(plan, context)

    assert len(questions) == 2
    assert questions[0].id == "q1"
    assert questions[0].type == QuestionType.FREE_TEXT
    assert "住所" in questions[0].text
    llm_client.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_questions_from_low_confidence() -> None:
    """Low-confidence fills should produce confirm-type questions."""
    fields = _make_fields(2)
    context = _make_context(fields)

    actions = (
        FieldFillAction(field_id="Text1", action=FillActionType.FILL, value="山田太郎", confidence=0.95, source="resume.pdf"),
        FieldFillAction(field_id="Text2", action=FillActionType.FILL, value="渋谷区", confidence=0.5, source="resume.pdf"),
    )
    plan = _make_plan(actions)

    llm_response = _make_llm_response([
        {
            "id": "q1",
            "question": "住所は「渋谷区」で正しいですか？",
            "question_type": "confirm",
            "options": [
                {"id": "yes", "label": "はい"},
                {"id": "no", "label": "いいえ"},
            ],
        },
    ])

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)

    generator = QuestionGenerator(llm_client=llm_client)
    questions = await generator.generate(plan, context)

    assert len(questions) == 1
    assert questions[0].type == QuestionType.CONFIRM
    assert len(questions[0].options) == 2


@pytest.mark.asyncio
async def test_max_questions_limit() -> None:
    """LLM returns more than MAX_QUESTIONS — generator should accept them all (LLM prompt caps it)."""
    fields = _make_fields(3)
    context = _make_context(fields)

    actions = (
        FieldFillAction(field_id="Text1", action=FillActionType.SKIP, reason="no data"),
        FieldFillAction(field_id="Text2", action=FillActionType.SKIP, reason="no data"),
        FieldFillAction(field_id="Text3", action=FillActionType.SKIP, reason="no data"),
    )
    plan = _make_plan(actions)

    # LLM returns exactly 3 questions
    raw_questions = [
        {"id": f"q{i}", "question": f"Question {i}?", "question_type": "free_text"}
        for i in range(3)
    ]
    llm_response = _make_llm_response(raw_questions)

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(return_value=llm_response)

    generator = QuestionGenerator(llm_client=llm_client)
    questions = await generator.generate(plan, context)

    assert len(questions) == 3


@pytest.mark.asyncio
async def test_no_questions_when_all_confident() -> None:
    """Good fills (all high confidence) should produce zero questions."""
    fields = _make_fields(2)
    context = _make_context(fields)

    actions = (
        FieldFillAction(field_id="Text1", action=FillActionType.FILL, value="山田太郎", confidence=0.95, source="resume.pdf"),
        FieldFillAction(field_id="Text2", action=FillActionType.FILL, value="東京都", confidence=0.9, source="resume.pdf"),
    )
    plan = _make_plan(actions)

    llm_client = MagicMock()
    llm_client.complete = AsyncMock()  # Should not be called

    generator = QuestionGenerator(llm_client=llm_client)
    questions = await generator.generate(plan, context)

    assert questions == ()
    llm_client.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_without_llm() -> None:
    """Without an LLM client, generator returns empty tuple."""
    fields = _make_fields(2)
    context = _make_context(fields)

    actions = (
        FieldFillAction(field_id="Text1", action=FillActionType.SKIP, reason="no data"),
        FieldFillAction(field_id="Text2", action=FillActionType.SKIP, reason="no data"),
    )
    plan = _make_plan(actions)

    generator = QuestionGenerator(llm_client=None)
    questions = await generator.generate(plan, context)

    assert questions == ()


@pytest.mark.asyncio
async def test_llm_failure_returns_empty() -> None:
    """If the LLM call fails, generator should return empty tuple gracefully."""
    fields = _make_fields(2)
    context = _make_context(fields)

    actions = (
        FieldFillAction(field_id="Text1", action=FillActionType.SKIP, reason="no data"),
        FieldFillAction(field_id="Text2", action=FillActionType.SKIP, reason="no data"),
    )
    plan = _make_plan(actions)

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(side_effect=RuntimeError("LLM error"))

    generator = QuestionGenerator(llm_client=llm_client)
    questions = await generator.generate(plan, context)

    assert questions == ()


# ── Tests: _partition_actions() ──


def test_partition_actions() -> None:
    """Actions should be partitioned into skipped, low_confidence, good_fills."""
    actions = (
        FieldFillAction(field_id="f1", action=FillActionType.FILL, value="v1", confidence=0.95),
        FieldFillAction(field_id="f2", action=FillActionType.FILL, value="v2", confidence=0.5),
        FieldFillAction(field_id="f3", action=FillActionType.SKIP, reason="no data"),
        FieldFillAction(field_id="f4", action=FillActionType.FILL, value="v4", confidence=0.8),
    )

    generator = QuestionGenerator()
    skipped, low_conf, good = generator._partition_actions(actions)

    assert len(skipped) == 1
    assert skipped[0].field_id == "f3"
    assert len(low_conf) == 1
    assert low_conf[0].field_id == "f2"
    assert len(good) == 2
    assert {a.field_id for a in good} == {"f1", "f4"}


# ── Tests: _parse_questions() ──


def test_parse_questions_with_options() -> None:
    """Should parse questions with options correctly."""
    result = {
        "questions": [
            {
                "id": "q1",
                "question": "性別を選択してください",
                "question_type": "single_choice",
                "options": [
                    {"id": "male", "label": "男性"},
                    {"id": "female", "label": "女性"},
                ],
                "context": "データソースに性別情報がありません",
            },
        ],
    }

    questions = QuestionGenerator._parse_questions(result)

    assert len(questions) == 1
    q = questions[0]
    assert q.id == "q1"
    assert q.type == QuestionType.SINGLE_CHOICE
    assert len(q.options) == 2
    assert q.options[0].id == "male"
    assert q.options[0].label == "男性"
    assert q.context is not None


def test_parse_questions_with_unknown_type() -> None:
    """Unknown question_type should fallback to free_text."""
    result = {
        "questions": [
            {
                "id": "q1",
                "question": "何か入力してください",
                "question_type": "unknown_type",
            },
        ],
    }

    questions = QuestionGenerator._parse_questions(result)

    assert len(questions) == 1
    assert questions[0].type == QuestionType.FREE_TEXT


def test_parse_questions_empty() -> None:
    """Empty questions list should return empty tuple."""
    questions = QuestionGenerator._parse_questions({"questions": []})
    assert questions == ()


def test_parse_questions_single_choice_no_options_downgraded() -> None:
    """single_choice with no options should be downgraded to free_text."""
    result = {
        "questions": [
            {
                "id": "q1",
                "question": "職業は何ですか？",
                "question_type": "single_choice",
                "options": [],
            },
        ],
    }

    questions = QuestionGenerator._parse_questions(result)

    assert len(questions) == 1
    assert questions[0].type == QuestionType.FREE_TEXT
    assert questions[0].options == ()


def test_parse_questions_confirm_no_options_gets_yes_no() -> None:
    """confirm with no options should get auto-added yes/no."""
    result = {
        "questions": [
            {
                "id": "q1",
                "question": "名前は山田太郎で正しいですか？",
                "question_type": "confirm",
            },
        ],
    }

    questions = QuestionGenerator._parse_questions(result)

    assert len(questions) == 1
    assert questions[0].type == QuestionType.CONFIRM
    assert len(questions[0].options) == 2
    assert questions[0].options[0].id == "yes"
    assert questions[0].options[1].id == "no"


def test_parse_questions_empty_text_skipped() -> None:
    """Questions with empty text should be filtered out."""
    result = {
        "questions": [
            {"id": "q1", "question": "", "question_type": "free_text"},
            {"id": "q2", "question": "有効な質問", "question_type": "free_text"},
        ],
    }

    questions = QuestionGenerator._parse_questions(result)

    assert len(questions) == 1
    assert questions[0].id == "q2"
