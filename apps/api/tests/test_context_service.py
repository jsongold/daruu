"""Tests for ContextService context assembly."""

from app.context import ContextService
from app.models import (
    Annotation,
    BBox,
    FieldLabelMap,
    FieldType,
    FormField,
    HistoryMessage,
    Mapping,
    RuleItem,
    RuleType,
    TextBlock,
)


def _field(
    fid: str,
    name: str,
    page: int = 1,
    field_type: FieldType = FieldType.TEXT,
    bbox: BBox | None = None,
    value: str | None = None,
) -> FormField:
    return FormField(
        id=fid,
        name=name,
        field_type=field_type,
        bbox=bbox or BBox(x=0.1, y=0.1, width=0.2, height=0.03),
        page=page,
        value=value,
    )


def _block(text: str, page: int = 1, x: float = 0.08, y: float = 0.1) -> TextBlock:
    return TextBlock(
        id=f"tb-{text[:8]}",
        text=text,
        bbox=BBox(x=x, y=y, width=0.05, height=0.02),
        page=page,
    )


def _flm(field_id: str, label: str, semantic_key: str, confidence: int = 90) -> FieldLabelMap:
    return FieldLabelMap(
        document_id="doc1",
        field_id=field_id,
        field_name="",
        label_text=label,
        semantic_key=semantic_key,
        confidence=confidence,
    )


class TestContextServiceBuild:
    def setup_method(self):
        self.svc = ContextService()

    def test_basic_field_enrichment(self):
        fields = [_field("f1", "Text1")]
        maps = [_flm("f1", "氏名", "full_name", 95)]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={"name": "田中"},
            rules=[],
            history=[],
        )
        assert len(ctx.pages) == 1
        section_fields = ctx.pages[0].sections[0].fields
        assert len(section_fields) == 1
        ef = section_fields[0]
        assert ef.field_id == "f1"
        assert ef.label == "氏名"
        assert ef.semantic_key == "full_name"
        assert ef.confidence == 95

    def test_signature_fields_excluded(self):
        fields = [
            _field("f1", "Text1"),
            _field("f2", "Sig1", field_type=FieldType.SIGNATURE),
        ]
        maps = [_flm("f1", "氏名", "full_name")]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        all_field_ids = [
            ef.field_id
            for p in ctx.pages
            for s in p.sections
            for ef in s.fields
        ]
        assert "f2" not in all_field_ids

    def test_zero_confidence_no_annotation_excluded(self):
        fields = [_field("f1", "Text1")]
        maps = [_flm("f1", "?", "unknown", confidence=0)]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        all_field_ids = [
            ef.field_id
            for p in ctx.pages
            for s in p.sections
            for ef in s.fields
        ]
        assert "f1" not in all_field_ids

    def test_already_filled_separated(self):
        fields = [
            _field("f1", "Text1", value="existing"),
            _field("f2", "Text2"),
        ]
        maps = [
            _flm("f1", "氏名", "full_name"),
            _flm("f2", "住所", "address"),
        ]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        assert len(ctx.already_filled) == 1
        assert ctx.already_filled[0].field_id == "f1"
        assert ctx.already_filled[0].value == "existing"
        unfilled_ids = [
            ef.field_id
            for p in ctx.pages
            for s in p.sections
            for ef in s.fields
        ]
        assert "f2" in unfilled_ids
        assert "f1" not in unfilled_ids

    def test_annotation_sets_confirmed(self):
        fields = [_field("f1", "Text1")]
        ann = Annotation(
            document_id="doc1",
            label_text="氏名",
            label_bbox=BBox(x=0.05, y=0.1, width=0.04, height=0.02),
            field_id="f1",
            field_name="Text1",
        )
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[ann],
            field_label_maps=[],
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        ef = ctx.pages[0].sections[0].fields[0]
        assert ef.confirmed is True
        assert ef.label == "氏名"

    def test_mapping_inferred_value(self):
        fields = [_field("f1", "Text1")]
        maps = [_flm("f1", "氏名", "full_name")]
        mapping = Mapping(
            session_id="s1",
            annotation_id="a1",
            field_id="f1",
            inferred_value="田中太郎",
            confidence=0.9,
        )
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[mapping],
            user_info={},
            rules=[],
            history=[],
        )
        ef = ctx.pages[0].sections[0].fields[0]
        assert ef.inferred_value == "田中太郎"

    def test_history_truncated_to_6(self):
        fields = [_field("f1", "Text1")]
        history = [HistoryMessage(role="user", content=f"msg{i}") for i in range(10)]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=[],
            mappings=[],
            user_info={},
            rules=[],
            history=history,
        )
        assert len(ctx.history) == 6
        assert ctx.history[0].content == "msg4"

    def test_nearby_text_found(self):
        fields = [_field("f1", "Text1", bbox=BBox(x=0.5, y=0.5, width=0.1, height=0.02))]
        blocks = [
            _block("年", page=1, x=0.51, y=0.5),
            _block("月", page=1, x=0.52, y=0.5),
            _block("far away", page=1, x=0.9, y=0.9),
        ]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=blocks,
            annotations=[],
            field_label_maps=[],
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        ef = ctx.pages[0].sections[0].fields[0]
        assert "年" in ef.nearby_text
        assert "月" in ef.nearby_text
        assert "far away" not in ef.nearby_text

    def test_section_grouping_by_y(self):
        fields = [
            _field("f1", "Name", bbox=BBox(x=0.1, y=0.1, width=0.2, height=0.03)),
            _field("f2", "Kana", bbox=BBox(x=0.1, y=0.12, width=0.2, height=0.03)),
            _field("f3", "Address", bbox=BBox(x=0.1, y=0.5, width=0.2, height=0.03)),
        ]
        maps = [
            _flm("f1", "氏名", "name"),
            _flm("f2", "フリガナ", "name_kana"),
            _flm("f3", "住所", "address"),
        ]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        sections = ctx.pages[0].sections
        assert len(sections) == 2
        assert len(sections[0].fields) == 2  # Name + Kana together
        assert len(sections[1].fields) == 1  # Address separate

    def test_rules_and_user_message_passed_through(self):
        fields = [_field("f1", "Text1")]
        rules = [RuleItem(type=RuleType.FORMAT, rule_text="dates in wareki")]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=[],
            mappings=[],
            user_info={"name": "test"},
            rules=rules,
            history=[],
            user_message="扶養親族はいません",
        )
        assert len(ctx.rules) == 1
        assert ctx.rules[0].rule_text == "dates in wareki"
        assert ctx.user_message == "扶養親族はいません"
        assert ctx.user_info == {"name": "test"}

    def test_multi_page_grouping(self):
        fields = [
            _field("f1", "Name", page=1),
            _field("f2", "Address", page=2),
        ]
        maps = [
            _flm("f1", "氏名", "name"),
            _flm("f2", "住所", "address"),
        ]
        ctx = self.svc.build(
            form_fields=fields,
            text_blocks=[],
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={},
            rules=[],
            history=[],
        )
        assert len(ctx.pages) == 2
        assert ctx.pages[0].page == 1
        assert ctx.pages[1].page == 2
