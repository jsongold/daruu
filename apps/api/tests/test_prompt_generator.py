"""Tests for PromptGenerator."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.models.form_context import FormContext, FormFieldSpec, LabelCandidate
from app.services.prompt_generator.generator import PromptGenerator
from app.services.prompt_generator.meta_prompt import build_prompt_generation_user_prompt


# ── Fixtures ──


@dataclass
class FakeLLMResponse:
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


def _make_fields() -> tuple[FormFieldSpec, ...]:
    return (
        FormFieldSpec(
            field_id="Text1",
            label="Text1",
            field_type="text",
            page=1,
            x=100.0,
            y=200.0,
            width=200.0,
            height=20.0,
            label_candidates=(
                LabelCandidate(text="氏名", confidence=0.9, page=1),
            ),
        ),
        FormFieldSpec(
            field_id="Text2",
            label="Text2",
            field_type="text",
            page=1,
            x=100.0,
            y=250.0,
            width=200.0,
            height=20.0,
            label_candidates=(
                LabelCandidate(text="住所", confidence=0.85, page=1),
            ),
        ),
        FormFieldSpec(
            field_id="Check1",
            label="Check1",
            field_type="checkbox",
            page=1,
            x=400.0,
            y=200.0,
            width=15.0,
            height=15.0,
        ),
    )


def _make_context(fields: tuple[FormFieldSpec, ...] | None = None) -> FormContext:
    return FormContext(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=fields or _make_fields(),
        data_sources=(),
        mapping_candidates=(),
        rules=(),
    )


def _make_text_blocks() -> list[dict]:
    return [
        {"text": "申告書", "page": 1, "bbox": [50, 50, 200, 30]},
        {"text": "氏名", "page": 1, "bbox": [50, 200, 40, 20]},
        {"text": "住所", "page": 1, "bbox": [50, 250, 40, 20]},
    ]


# ── Tests: PromptGenerator.generate() ──


@pytest.mark.asyncio
async def test_generate_returns_result_with_all_fields() -> None:
    """Generated prompt should contain all field_ids."""
    import json as _json

    fields = _make_fields()
    context = _make_context(fields)

    # LLM returns valid JSON mapping with all field_ids
    mapping = {
        "form_title": "テスト申告書",
        "form_language": "ja",
        "field_labels": {
            "Text1": "氏名",
            "Text2": "住所",
            "Check1": "チェックボックス",
        },
        "key_field_mappings": [],
        "sections": [],
        "format_rules": {},
        "fill_rules": [],
    }

    llm_client = MagicMock()
    llm_client.model = "gpt-4o-mini"
    llm_client.complete = AsyncMock(
        return_value=FakeLLMResponse(content=_json.dumps(mapping))
    )

    doc_service = MagicMock()
    doc_service.extract_text_blocks = MagicMock(return_value=_make_text_blocks())

    generator = PromptGenerator(llm_client=llm_client, document_service=doc_service)
    result = await generator.generate("doc-1", context)

    assert result.validation_passed is True
    assert result.missing_field_ids == ()
    assert "Text1" in result.specialized_prompt
    assert "Text2" in result.specialized_prompt
    assert "Check1" in result.specialized_prompt
    assert result.model_used == "gpt-4o-mini"
    assert result.generation_time_ms >= 0


@pytest.mark.asyncio
async def test_generate_appends_missing_fields() -> None:
    """Missing field_ids should be appended as fallback mappings."""
    import json as _json

    fields = _make_fields()
    context = _make_context(fields)

    # LLM returns JSON mapping with only Text1, missing Text2 and Check1
    mapping = {
        "form_title": "テスト",
        "form_language": "ja",
        "field_labels": {"Text1": "氏名"},
        "key_field_mappings": [],
        "sections": [],
        "format_rules": {},
        "fill_rules": [],
    }

    llm_client = MagicMock()
    llm_client.model = "gpt-4o-mini"
    llm_client.complete = AsyncMock(
        return_value=FakeLLMResponse(content=_json.dumps(mapping))
    )

    doc_service = MagicMock()
    doc_service.extract_text_blocks = MagicMock(return_value=_make_text_blocks())

    generator = PromptGenerator(llm_client=llm_client, document_service=doc_service)
    result = await generator.generate("doc-1", context)

    assert result.validation_passed is False
    assert "Check1" in result.missing_field_ids
    assert "Text2" in result.missing_field_ids
    # Fallback mappings should be appended
    assert "Check1" in result.specialized_prompt
    assert "Text2" in result.specialized_prompt


@pytest.mark.asyncio
async def test_generate_handles_text_block_failure() -> None:
    """Should handle DocumentService failure gracefully."""
    context = _make_context()

    fake_prompt = "Text1: 氏名\nText2: 住所\nCheck1: checkbox\n"

    llm_client = MagicMock()
    llm_client.model = "test-model"
    llm_client.complete = AsyncMock(return_value=FakeLLMResponse(content=fake_prompt))

    doc_service = MagicMock()
    doc_service.extract_text_blocks = MagicMock(side_effect=RuntimeError("PDF error"))

    generator = PromptGenerator(llm_client=llm_client, document_service=doc_service)
    result = await generator.generate("doc-1", context)

    # Should still produce a result (with empty text blocks)
    assert result.specialized_prompt is not None
    llm_client.complete.assert_awaited_once()


# ── Tests: build_prompt_generation_user_prompt ──


def test_user_prompt_includes_nearby_labels() -> None:
    """User prompt should include nearby_labels for each field."""
    context = _make_context()
    text_blocks = _make_text_blocks()

    prompt = build_prompt_generation_user_prompt(context, text_blocks)

    assert "Text1" in prompt
    assert "氏名" in prompt
    assert "住所" in prompt
    assert "nearby_labels" in prompt


def test_user_prompt_includes_text_blocks() -> None:
    """User prompt should include PDF text content."""
    context = _make_context()
    text_blocks = _make_text_blocks()

    prompt = build_prompt_generation_user_prompt(context, text_blocks)

    assert "申告書" in prompt
    assert "[page 1]" in prompt


def test_user_prompt_includes_similar_prompts() -> None:
    """User prompt should include similar prompts as references."""
    context = _make_context()
    text_blocks = _make_text_blocks()
    similar = ["Reference prompt content here"]

    prompt = build_prompt_generation_user_prompt(context, text_blocks, similar)

    assert "Reference prompt content here" in prompt
    assert "Similar Prompt 1" in prompt


def test_user_prompt_includes_bbox_info() -> None:
    """User prompt should include field bbox information."""
    context = _make_context()
    text_blocks = _make_text_blocks()

    prompt = build_prompt_generation_user_prompt(context, text_blocks)

    assert "page=1" in prompt
    assert "x=100" in prompt


def test_user_prompt_includes_data_source_keys() -> None:
    """User prompt should include data source keys for key-field mapping."""
    from app.domain.models.form_context import DataSourceEntry

    context = FormContext(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
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
    text_blocks = _make_text_blocks()

    prompt = build_prompt_generation_user_prompt(context, text_blocks)

    assert "Data Source Keys" in prompt
    assert "resume.pdf" in prompt
    assert "氏名" in prompt
    assert "山田太郎" in prompt


@pytest.mark.asyncio
async def test_generate_with_key_field_mappings() -> None:
    """Generated result should include key_field_mappings from LLM."""
    import json as _json
    from app.domain.models.form_context import DataSourceEntry

    context = FormContext(
        document_id="doc-1",
        conversation_id="conv-1",
        fields=_make_fields(),
        data_sources=(
            DataSourceEntry(
                source_name="resume.pdf",
                source_type="pdf",
                extracted_fields={"氏名": "山田太郎", "住所": "東京都"},
            ),
        ),
        mapping_candidates=(),
        rules=(),
    )

    mapping = {
        "form_title": "テスト申告書",
        "form_language": "ja",
        "field_labels": {
            "Text1": "氏名",
            "Text2": "住所",
            "Check1": "チェックボックス",
        },
        "key_field_mappings": [
            {
                "source_key": "氏名",
                "field_id": "Text1",
                "bbox": {"page": 1, "x": 100, "y": 200},
                "reasoning": "nearby_label '氏名' directly above field",
            },
            {
                "source_key": "住所",
                "field_id": "Text2",
                "bbox": {"page": 1, "x": 100, "y": 250},
                "reasoning": "nearby_label '住所' directly above field",
            },
        ],
        "sections": [],
        "format_rules": {},
        "fill_rules": [],
    }

    llm_client = MagicMock()
    llm_client.model = "gpt-4o-mini"
    llm_client.complete = AsyncMock(
        return_value=FakeLLMResponse(content=_json.dumps(mapping))
    )

    doc_service = MagicMock()
    doc_service.extract_text_blocks = MagicMock(return_value=_make_text_blocks())

    generator = PromptGenerator(llm_client=llm_client, document_service=doc_service)
    result = await generator.generate("doc-1", context)

    # key_field_mappings should be in result
    assert result.key_field_mappings is not None
    assert len(result.key_field_mappings) == 2
    assert result.key_field_mappings[0]["source_key"] == "氏名"
    assert result.key_field_mappings[0]["field_id"] == "Text1"

    # Specialized prompt should include mapping section
    assert "Data Source Key" in result.specialized_prompt
    assert "\"氏名\" → Text1" in result.specialized_prompt
    assert "\"住所\" → Text2" in result.specialized_prompt
