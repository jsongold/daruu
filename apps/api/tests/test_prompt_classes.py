"""Tests for Prompt classes: FillPrompt, MapPrompt, RulesPrompt, AskPrompt."""

import json

from app.models import (
    AskContext,
    Annotation,
    BBox,
    FillContext,
    FieldType,
    FormField,
    HistoryMessage,
    MapContext,
    PageContext,
    FieldSection,
    EnrichedField,
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
    def test_build_returns_prompt(self):
        ctx = FillContext(
            pages=[PageContext(page=1, sections=[
                FieldSection(fields=[
                    EnrichedField(field_id="f1", name="Text1", type="text", label="name"),
                ]),
            ])],
            user_info={"name": "Tanaka"},
            rules=[],
            history=[],
        )
        result = FillPrompt.build(ctx)
        assert isinstance(result, Prompt)
        assert "form-filling assistant" in result.system
        parsed = json.loads(result.user)
        assert parsed["user_info"]["name"] == "Tanaka"

    def test_build_includes_rules_and_history(self):
        ctx = FillContext(
            pages=[],
            user_info={},
            rules=[RuleItem(type=RuleType.FORMAT, rule_text="dates in wareki")],
            history=[HistoryMessage(role="user", content="hello")],
        )
        result = FillPrompt.build(ctx)
        parsed = json.loads(result.user)
        assert len(parsed["rules"]) == 1
        assert len(parsed["history"]) == 1


class TestMapPrompt:
    def test_build_returns_prompt_with_fields(self):
        ctx = MapContext(
            fields=[_field("f1", "Text1")],
            text_blocks=[_block("label")],
            confirmed_annotations=[],
        )
        result = MapPrompt.build(ctx)
        assert isinstance(result, Prompt)
        assert "Japanese PDF form" in result.system
        assert "f1" in result.user

    def test_build_with_confirmed_annotations(self):
        ann = Annotation(
            document_id="doc1",
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
        assert "document analysis assistant" in result.system
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
