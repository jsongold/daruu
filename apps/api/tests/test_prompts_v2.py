"""Tests for prompts_v2 module.

TDD tests for prompt construction and response parsing
in the v2 field identification pipeline.
"""

from __future__ import annotations

from app.services.vision_autofill.candidate_filter import CandidateLabel, FieldWithCandidates
from app.services.vision_autofill.prompts_v2 import (
    build_field_identification_prompt,
    parse_identification_response,
)


def test_build_prompt_no_few_shot():
    """few-shotなしでプロンプトが正しく構築される"""
    fields = [
        FieldWithCandidates(
            field_id="Text1",
            field_type="text",
            page=1,
            bbox_ivb=(200, 148, 450, 172),
            candidates=[
                CandidateLabel(
                    text="氏名",
                    bbox_ivb=(120, 150, 180, 170),
                    distance_score=50.0,
                    direction="left",
                ),
            ],
        )
    ]
    system, user = build_field_identification_prompt(fields)
    assert "氏名" in user
    assert "Text1" in user
    assert "[120,150,180,170]" in user
    assert "left" in user
    assert "Confirmed mappings" not in system


def test_build_prompt_with_few_shot():
    """few-shotありでプロンプトにConfirmed mappingsセクションが含まれる"""
    pairs = [
        {
            "field_id": "Text3",
            "label": "氏名",
            "semantic_key": "applicant_name",
            "field_bbox_ivb": [200, 148, 450, 172],
            "label_bbox_ivb": [120, 150, 180, 170],
            "confidence": 95,
        }
    ]
    fields = [
        FieldWithCandidates(
            field_id="Text1",
            field_type="text",
            page=1,
            bbox_ivb=(200, 200, 450, 220),
            candidates=[
                CandidateLabel("住所", (120, 200, 180, 220), 30.0, "left"),
            ],
        )
    ]
    system, user = build_field_identification_prompt(fields, confirmed_pairs=pairs)
    assert "Confirmed mappings" in system
    assert "氏名" in system
    assert "applicant_name" in system


def test_parse_valid_response():
    """正常なJSONレスポンスのパース"""
    response = (
        '[{"field_id":"Text1","label":"氏名",'
        '"semantic_key":"applicant_name","confidence":90}]'
    )
    fields, missing = parse_identification_response(response, ["Text1", "Text2"])
    assert len(fields) == 1
    assert fields[0].label == "氏名"
    assert fields[0].confidence == 90
    assert "Text2" in missing


def test_parse_fenced_response():
    """```json ... ``` で囲まれたレスポンスのパース"""
    response = (
        '```json\n[{"field_id":"Text1","label":"氏名",'
        '"semantic_key":"name","confidence":85}]\n```'
    )
    fields, missing = parse_identification_response(response, ["Text1"])
    assert len(fields) == 1


def test_parse_invalid_json():
    """JSONパース失敗時のフォールバック"""
    fields, missing = parse_identification_response("not json", ["Text1", "Text2"])
    assert len(fields) == 0
    assert set(missing) == {"Text1", "Text2"}


def test_parse_null_label():
    """label=null のフィールド"""
    response = (
        '[{"field_id":"Text1","label":null,'
        '"semantic_key":"unknown","confidence":10}]'
    )
    fields, _ = parse_identification_response(response, ["Text1"])
    assert fields[0].label is None


def test_build_prompt_multi_page():
    """複数ページのフィールドが正しくグループ化される"""
    fields = [
        FieldWithCandidates(
            field_id="Text1",
            field_type="text",
            page=1,
            bbox_ivb=(200, 148, 450, 172),
            candidates=[
                CandidateLabel("氏名", (120, 150, 180, 170), 50.0, "left"),
            ],
        ),
        FieldWithCandidates(
            field_id="Text50",
            field_type="text",
            page=2,
            bbox_ivb=(100, 80, 300, 100),
            candidates=[
                CandidateLabel("住所", (50, 80, 90, 100), 20.0, "left"),
            ],
        ),
    ]
    _, user = build_field_identification_prompt(fields)
    assert "--- Page 1 ---" in user
    assert "--- Page 2 ---" in user


def test_candidates_sorted_by_distance():
    """候補がdistance_score昇順でソートされる"""
    fields = [
        FieldWithCandidates(
            field_id="Text1",
            field_type="text",
            page=1,
            bbox_ivb=(200, 148, 450, 172),
            candidates=[
                CandidateLabel("遠い", (500, 500, 600, 520), 200.0, "right"),
                CandidateLabel("近い", (120, 150, 180, 170), 10.0, "left"),
            ],
        ),
    ]
    _, user = build_field_identification_prompt(fields)
    near_pos = user.index("近い")
    far_pos = user.index("遠い")
    assert near_pos < far_pos


def test_parse_confidence_as_string():
    """confidence が文字列で返ってきた場合のint変換"""
    response = (
        '[{"field_id":"Text1","label":"氏名",'
        '"semantic_key":"name","confidence":"85"}]'
    )
    fields, _ = parse_identification_response(response, ["Text1"])
    assert fields[0].confidence == 85
    assert isinstance(fields[0].confidence, int)


def test_parse_empty_string_label():
    """label="" が None に変換される"""
    response = (
        '[{"field_id":"Text1","label":"",'
        '"semantic_key":"unknown","confidence":10}]'
    )
    fields, _ = parse_identification_response(response, ["Text1"])
    assert fields[0].label is None
