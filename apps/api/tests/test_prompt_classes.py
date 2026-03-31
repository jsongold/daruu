"""Tests for Prompt classes: FillPrompt, MapPrompt, RulesPrompt, AskPrompt."""

import json

from app.models import (
    AskContext,
    Annotation,
    BBox,
    FillContext,
    FillField,
    FieldType,
    FormField,
    HistoryMessage,
    MapContext,
    Prompt,
    RuleItem,
    RulesContext,
    RuleType,
    TextBlock,
)
from app.prompts import AskPrompt, FillPrompt, MapPrompt, RulesPrompt


def _field(fid: str = "f1", name: str = "Text1", page: int = 1) -> FormField:
    return FormField(
        id=fid,
        name=name,
        field_type=FieldType.TEXT,
        bbox=BBox(x=0.1, y=0.1, width=0.2, height=0.03),
        page=page,
    )


def _block(text: str = "label", page: int = 1) -> TextBlock:
    return TextBlock(
        id=f"tb-{text[:8]}",
        text=text,
        bbox=BBox(x=0.05, y=0.1, width=0.04, height=0.02),
        page=page,
    )


class TestFillPrompt:
    def test_build_returns_prompt_and_index(self):
        ctx = FillContext(
            fields=[FillField(field_id="f1", label="name", semantic_key="full_name", type="text")],
            user_info={"k": "Tanaka"},
        )
        prompt, idx_map = FillPrompt.build(ctx)
        assert isinstance(prompt, Prompt)
        assert "Form-fill" in prompt.system
        assert "input\nTanaka\n" in prompt.user
        assert "form_schema\n0|name|full_name" in prompt.user
        assert idx_map == ["f1"]

    def test_build_includes_format_rule_and_type(self):
        ctx = FillContext(
            fields=[FillField(field_id="f1", label="date", semantic_key="birth_date", type="date", format_rule="YYYY/MM/DD")],
            user_info={"birthday": "1990-01-15"},
        )
        prompt, idx_map = FillPrompt.build(ctx)
        assert "0|date|birth_date|date|YYYY/MM/DD" in prompt.user

    def test_build_omits_default_type(self):
        ctx = FillContext(
            fields=[FillField(field_id="f1", label="name", semantic_key="full_name", type="text")],
            user_info={},
        )
        prompt, _ = FillPrompt.build(ctx)
        # text type should not appear
        assert "0|name|full_name" in prompt.user
        assert "text" not in prompt.user.split("\n")[-1]

    def test_parse_basic(self):
        content = "0:Tanaka\n1:1990-01-15\n"
        result = FillPrompt.parse(content, ["field-uuid-0", "field-uuid-1"])
        assert result == [
            {"field_id": "field-uuid-0", "value": "Tanaka"},
            {"field_id": "field-uuid-1", "value": "1990-01-15"},
        ]

    def test_parse_skips_invalid(self):
        content = "0:Tanaka\nbad line\n99:out of range\n"
        result = FillPrompt.parse(content, ["f1"])
        assert len(result) == 1
        assert result[0]["field_id"] == "f1"

    def test_parse_value_with_colon(self):
        content = "0:10:30 AM\n"
        result = FillPrompt.parse(content, ["f1"])
        assert result[0]["value"] == "10:30 AM"


class TestMapPrompt:
    def test_build_returns_prompt_with_fields(self):
        ctx = MapContext(
            fields=[_field("f1", "Text1")],
            text_blocks=[_block("label")],
            confirmed_annotations=[],
        )
        result = MapPrompt.build(ctx)
        assert isinstance(result, Prompt)
        assert "PDF form field identification" in result.system
        assert "f1" in result.user

    def test_build_with_confirmed_annotations(self):
        ann = Annotation(
            form_id="doc1",
            label_text="name",
            label_bbox=BBox(x=0.05, y=0.1, width=0.04, height=0.02),
            field_id="f1",
            field_name="Text1",
            field_bbox=BBox(x=0.1, y=0.1, width=0.2, height=0.03),
        )
        ctx = MapContext(
            fields=[_field()],
            text_blocks=[_block()],
            confirmed_annotations=[ann],
        )
        result = MapPrompt.build(ctx)
        assert "Confirmed mappings" in result.user

    def test_build_empty_fields(self):
        ctx = MapContext(fields=[], text_blocks=[], confirmed_annotations=[])
        result = MapPrompt.build(ctx)
        assert isinstance(result, Prompt)
        assert result.user.startswith("Match each field")


class TestRulesPrompt:
    def test_build_returns_prompt(self):
        ctx = RulesContext(
            fields=[_field()],
            text_blocks=[_block("instruction text")],
        )
        result = RulesPrompt.build(ctx)
        assert isinstance(result, Prompt)
        assert "form analysis assistant" in result.system
        parsed_user = result.user
        assert "f1" in parsed_user
        assert "instruction text" in parsed_user

    def test_build_empty(self):
        ctx = RulesContext(fields=[], text_blocks=[])
        result = RulesPrompt.build(ctx)
        assert isinstance(result, Prompt)


class TestAskPrompt:
    def test_build_filters_conditional_rules(self):
        rules = [
            RuleItem(type=RuleType.CONDITIONAL, rule_text="r1", question="Married?", options=["Yes", "No"]),
            RuleItem(type=RuleType.FORMAT, rule_text="r2"),
            RuleItem(type=RuleType.CONDITIONAL, rule_text="r3", question="Has dependents?", options=["Yes", "No"]),
        ]
        ctx = AskContext(rules=rules)
        result = AskPrompt.build(ctx)
        assert isinstance(result, Prompt)
        assert result.system == ""
        parsed = json.loads(result.user)
        assert len(parsed["questions"]) == 2
        assert parsed["questions"][0]["question"] == "Married?"
        assert parsed["questions"][1]["question"] == "Has dependents?"

    def test_build_no_conditional_rules(self):
        rules = [RuleItem(type=RuleType.FORMAT, rule_text="all caps")]
        ctx = AskContext(rules=rules)
        result = AskPrompt.build(ctx)
        parsed = json.loads(result.user)
        assert parsed["questions"] == []

    def test_build_skips_conditional_without_question(self):
        rules = [RuleItem(type=RuleType.CONDITIONAL, rule_text="no question")]
        ctx = AskContext(rules=rules)
        result = AskPrompt.build(ctx)
        parsed = json.loads(result.user)
        assert parsed["questions"] == []
