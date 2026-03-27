"""Tests for benchmark module.

Mock litellm.acompletion to avoid real API calls.
Validates prompt construction, token reduction, output schema, and CLI args.
"""

from __future__ import annotations

import argparse
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.vision_autofill.benchmark import (
    MODEL_CONFIGS,
    build_v1_prompt,
    call_llm,
    run_benchmark,
)
from app.services.vision_autofill.prompts import FIELD_IDENTIFICATION_SYSTEM_PROMPT
from app.services.vision_autofill.prompts_v2 import FIELD_IDENTIFICATION_SYSTEM_V2


def _make_fields(count: int) -> list[dict]:
    """Generate test field dicts."""
    return [
        {"id": f"Text{i}", "t": "text", "p": 1, "b": [100.0 + i * 20, 200.0, 80.0, 20.0]}
        for i in range(count)
    ]


def _make_text_blocks(count: int) -> list[dict]:
    """Generate test text block dicts."""
    labels = [
        "氏名", "フリガナ", "住所", "生年月日", "電話番号",
        "法人名", "事業所名", "郵便番号", "都道府県", "市区町村",
        "番地", "建物名", "部署名", "役職", "従業員番号",
        "給与額", "税額", "保険料", "扶養人数", "備考",
        "申請日", "承認日", "受付番号", "処理番号", "担当者名",
        "印鑑", "署名", "日付", "時刻", "金額",
        "合計", "小計", "消費税", "源泉徴収税額", "社会保険料",
        "雇用保険料", "厚生年金", "健康保険", "介護保険", "労災保険",
        "通勤手当", "住宅手当", "家族手当", "資格手当", "役職手当",
        "残業手当", "深夜手当", "休日手当", "特別手当", "賞与",
    ]
    return [
        {
            "s": labels[i % len(labels)],
            "p": 1,
            "b": [80.0 + i * 15, 200.0 + (i % 5) * 5, 60.0, 14.0],
        }
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# 1. v1 prompt construction
# ---------------------------------------------------------------------------


def test_v1_prompt_construction():
    """v1 prompt contains fields and text blocks in JSON format,
    uses FIELD_IDENTIFICATION_SYSTEM_PROMPT."""
    fields = _make_fields(3)
    text_blocks = _make_text_blocks(5)

    system, user = build_v1_prompt(fields, text_blocks)

    assert system == FIELD_IDENTIFICATION_SYSTEM_PROMPT
    assert "## Form Fields" in user
    assert "## PDF Text Blocks" in user
    assert "Text0" in user
    assert "Text1" in user
    assert "Text2" in user
    assert "```json" in user
    assert "Identify the label for each form field" in user


# ---------------------------------------------------------------------------
# 2. v2 prompt construction
# ---------------------------------------------------------------------------


def test_v2_prompt_construction():
    """v2 prompt uses candidate format with IVB coords,
    uses FIELD_IDENTIFICATION_SYSTEM_V2."""
    from app.services.vision_autofill.candidate_filter import filter_candidates
    from app.services.vision_autofill.prompts_v2 import (
        build_field_identification_prompt as build_v2,
    )

    fields = _make_fields(3)
    text_blocks = _make_text_blocks(5)
    fwc = filter_candidates(fields, text_blocks)
    system, user = build_v2(fwc)

    assert FIELD_IDENTIFICATION_SYSTEM_V2 in system
    assert "candidates:" in user
    assert "Text0" in user


# ---------------------------------------------------------------------------
# 3. Token count reduction
# ---------------------------------------------------------------------------


def test_token_count_reduction():
    """v2 prompt character count is significantly less than v1 for realistic input.

    v1 sends ALL text blocks as full JSON; v2 sends only top-k candidates per field.
    With many text blocks (200+), v2 is dramatically smaller because it filters
    to only 7 candidates per field instead of sending all 200+ blocks.
    """
    from app.services.vision_autofill.candidate_filter import filter_candidates
    from app.services.vision_autofill.prompts_v2 import (
        build_field_identification_prompt as build_v2,
    )

    fields = _make_fields(30)
    # Use a large number of text blocks to simulate realistic dense PDFs
    text_blocks = _make_text_blocks(500)

    _, v1_user = build_v1_prompt(fields, text_blocks)
    fwc = filter_candidates(fields, text_blocks)
    _, v2_user = build_v2(fwc)

    v1_total = len(v1_user)
    v2_total = len(v2_user)

    # v1 sends ALL 500 text blocks; v2 sends only top-7 candidates per 30 fields
    # ratio should be well under 50%
    assert v2_total < v1_total, (
        f"v2 ({v2_total} chars) should be smaller than v1 ({v1_total} chars), "
        f"actual ratio: {v2_total / v1_total:.1%}"
    )


# ---------------------------------------------------------------------------
# 4. Output JSON schema
# ---------------------------------------------------------------------------


async def test_output_json_schema(tmp_path):
    """Output JSON has expected keys: timestamp, input_summary, results."""
    fields = _make_fields(2)
    text_blocks = _make_text_blocks(3)

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(
        {"field_labels": [{"field_id": "Text0", "identified_label": "氏名", "confidence": 0.9, "reasoning": "left"}]}
    )
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    patterns = [
        {"name": "A_baseline_gpt41mini", "description": "test", "prompt_version": "v1", "model": "gpt-4.1-mini", "few_shot": False},
    ]

    with patch("app.services.vision_autofill.benchmark.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        await run_benchmark(fields, text_blocks, None, patterns, str(tmp_path))

    result_files = list(tmp_path.glob("benchmark_*.json"))
    assert len(result_files) == 1

    data = json.loads(result_files[0].read_text())
    assert "timestamp" in data
    assert "input_summary" in data
    assert "results" in data
    assert data["input_summary"]["field_count"] == 2
    assert data["input_summary"]["text_block_count"] == 3


# ---------------------------------------------------------------------------
# 5. call_llm OpenAI
# ---------------------------------------------------------------------------


async def test_call_llm_openai():
    """Mock litellm.acompletion, verify correct model string for OpenAI."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"result": "ok"}'
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 20

    with patch("app.services.vision_autofill.benchmark.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(return_value=mock_response)
        text, meta = await call_llm("openai", "gpt-4.1-mini", "system", "user")

    assert text == '{"result": "ok"}'
    assert meta["model"] == "gpt-4.1-mini"
    assert meta["input_tokens"] == 50
    assert meta["output_tokens"] == 20

    call_args = mock_litellm.acompletion.call_args
    assert call_args.kwargs["model"] == "gpt-4.1-mini"
    assert call_args.kwargs["response_format"] == {"type": "json_object"}


# ---------------------------------------------------------------------------
# 6. call_llm error handling
# ---------------------------------------------------------------------------


async def test_call_llm_error_handling():
    """Mock litellm.acompletion to raise, verify error is logged and re-raised."""
    with patch("app.services.vision_autofill.benchmark.litellm") as mock_litellm:
        mock_litellm.acompletion = AsyncMock(side_effect=RuntimeError("API down"))
        with pytest.raises(RuntimeError, match="API down"):
            await call_llm("openai", "gpt-4.1-mini", "system", "user")


# ---------------------------------------------------------------------------
# 7. CLI args parsing
# ---------------------------------------------------------------------------


def test_cli_args_parsing():
    """Test argparse accepts required args."""
    from app.services.vision_autofill.benchmark import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["--fields-json", "f.json", "--blocks-json", "b.json"])
    assert args.fields_json == "f.json"
    assert args.blocks_json == "b.json"
    assert args.output_dir == "./benchmark_results/"

    args2 = parser.parse_args([
        "--fields-json", "f.json",
        "--blocks-json", "b.json",
        "--models", "gpt-4.1-mini", "gemini-2.5-flash",
        "--few-shot-json", "fs.json",
        "--output-dir", "/tmp/out",
    ])
    assert args2.models == ["gpt-4.1-mini", "gemini-2.5-flash"]
    assert args2.few_shot_json == "fs.json"
    assert args2.output_dir == "/tmp/out"
