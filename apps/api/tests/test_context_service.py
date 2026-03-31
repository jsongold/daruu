"""Tests for ContextService: rule resolution and field filtering."""

from app.context import ContextService
from app.models import (
    Annotation,
    BBox,
    FieldLabelMap,
    FieldType,
    FormField,
    FormSchemaField,
    Mapping,
    RuleItem,
    RuleType,
)


def _schema_field(
    fid: str,
    name: str,
    label: str | None = None,
    semantic_key: str | None = None,
    confidence: int = 90,
    field_type: str = "text",
    default_value: str | None = None,
    is_confirmed: bool = False,
    label_source: str | None = "map_auto",
) -> FormSchemaField:
    return FormSchemaField(
        field_id=fid,
        field_name=name,
        field_type=field_type,
        label_text=label or name,
        label_source=label_source,
        semantic_key=semantic_key,
        confidence=confidence,
        default_value=default_value,
        is_confirmed=is_confirmed,
    )


# Legacy helpers for build_legacy tests
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


def _flm(field_id: str, label: str, semantic_key: str, confidence: int = 90) -> FieldLabelMap:
    return FieldLabelMap(
        form_id="doc1",
        field_id=field_id,
        field_name="",
        label_text=label,
        semantic_key=semantic_key,
        confidence=confidence,
    )


class TestContextServiceBuild:
    def setup_method(self):
        self.svc = ContextService()

    def test_basic_field_included(self):
        fields = [_schema_field("f1", "Text1", label="name", semantic_key="full_name", confidence=95)]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={"name": "Tanaka"},
            rules=[],
        )
        assert len(ctx.fields) == 1
        assert ctx.fields[0].field_id == "f1"
        assert ctx.fields[0].label == "name"
        assert ctx.fields[0].semantic_key == "full_name"
        assert ctx.user_info == {"name": "Tanaka"}

    def test_signature_fields_excluded(self):
        fields = [
            _schema_field("f1", "Text1", label="name", semantic_key="full_name"),
            _schema_field("f2", "Sig1", field_type="signature"),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        field_ids = [f.field_id for f in ctx.fields]
        assert "f2" not in field_ids

    def test_zero_confidence_no_label_excluded(self):
        fields = [_schema_field("f1", "", label=None, semantic_key="unknown", confidence=0, label_source=None)]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        assert len(ctx.fields) == 0

    def test_already_filled_excluded(self):
        fields = [
            _schema_field("f1", "Text1", label="name", semantic_key="full_name", default_value="existing"),
            _schema_field("f2", "Text2", label="address", semantic_key="address"),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        field_ids = [f.field_id for f in ctx.fields]
        assert "f1" not in field_ids
        assert "f2" in field_ids

    def test_annotation_label_used(self):
        fields = [_schema_field("f1", "Text1", label="name", label_source="annotation", is_confirmed=True)]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        assert len(ctx.fields) == 1
        assert ctx.fields[0].label == "name"


    def test_confidence_zero_unconfirmed_excluded(self):
        """Fields with confidence=0 that are not annotation-confirmed are excluded."""
        fields = [
            _schema_field("f1", "Name", label="name", semantic_key="full_name", confidence=90),
            _schema_field("f2", "Separator", label="・", semantic_key="separator_dot", confidence=0),
            _schema_field("f3", "EraSelect", label="明・大", semantic_key="era_select", confidence=0),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        field_ids = [f.field_id for f in ctx.fields]
        assert "f1" in field_ids
        assert "f2" not in field_ids
        assert "f3" not in field_ids

    def test_confidence_zero_but_confirmed_included(self):
        """Fields with confidence=0 but confirmed by annotation ARE included."""
        fields = [
            _schema_field("f1", "ManualLabel", label="Important Field", confidence=0, is_confirmed=True),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        assert len(ctx.fields) == 1
        assert ctx.fields[0].field_id == "f1"


class TestBuildLegacy:
    """Tests for the legacy build path that converts old-style inputs."""

    def setup_method(self):
        self.svc = ContextService()

    def test_legacy_basic(self):
        fields = [_field("f1", "Text1")]
        maps = [_flm("f1", "name", "full_name", 95)]
        ctx = self.svc.build_legacy(
            form_fields=fields,
            annotations=[],
            field_label_maps=maps,
            mappings=[],
            user_info={"name": "Tanaka"},
            rules=[],
        )
        assert len(ctx.fields) == 1
        assert ctx.fields[0].field_id == "f1"
        assert ctx.fields[0].label == "name"

    def test_legacy_annotation_wins(self):
        fields = [_field("f1", "Text1")]
        ann = Annotation(
            form_id="doc1",
            label_text="annotated_name",
            label_bbox=BBox(x=0.05, y=0.1, width=0.04, height=0.02),
            field_id="f1",
            field_name="Text1",
        )
        maps = [_flm("f1", "map_name", "full_name")]
        ctx = self.svc.build_legacy(
            form_fields=fields,
            annotations=[ann],
            field_label_maps=maps,
            mappings=[],
            user_info={},
            rules=[],
        )
        assert ctx.fields[0].label == "annotated_name"


class TestConditionalRuleResolution:
    def setup_method(self):
        self.svc = ContextService()

    def test_unanswered_conditional_skips_fields(self):
        fields = [
            _schema_field("f1", "ApplicantName", label="name", semantic_key="applicant_name"),
            _schema_field("f2", "SpouseName", label="spouse", semantic_key="spouse_name"),
        ]
        rules = [
            RuleItem(
                type=RuleType.CONDITIONAL,
                rule_text="Fill spouse only if married",
                field_ids=["f2"],
                question="Are you married?",
                options=["Yes", "No"],
            ),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={"name": "Tanaka"},
            rules=rules,
        )
        field_ids = [f.field_id for f in ctx.fields]
        assert "f1" in field_ids
        assert "f2" not in field_ids

    def test_negative_answer_skips_fields(self):
        fields = [
            _schema_field("f1", "ApplicantName", label="name", semantic_key="applicant_name"),
            _schema_field("f2", "SpouseName", label="spouse", semantic_key="spouse_name"),
        ]
        rules = [
            RuleItem(
                type=RuleType.CONDITIONAL,
                rule_text="Fill spouse only if married",
                field_ids=["f2"],
                question="Are you married?",
                options=["Yes", "No"],
            ),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=rules,
            ask_answers={"Are you married?": "No"},
        )
        field_ids = [f.field_id for f in ctx.fields]
        assert "f2" not in field_ids

    def test_positive_answer_includes_fields(self):
        fields = [
            _schema_field("f1", "ApplicantName", label="name", semantic_key="applicant_name"),
            _schema_field("f2", "SpouseName", label="spouse", semantic_key="spouse_name"),
        ]
        rules = [
            RuleItem(
                type=RuleType.CONDITIONAL,
                rule_text="Fill spouse only if married",
                field_ids=["f2"],
                question="Are you married?",
                options=["Yes", "No"],
            ),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=rules,
            ask_answers={"Are you married?": "Yes"},
        )
        field_ids = [f.field_id for f in ctx.fields]
        assert "f1" in field_ids
        assert "f2" in field_ids


class TestFormatRules:
    def setup_method(self):
        self.svc = ContextService()

    def test_format_rule_attached_to_field(self):
        fields = [_schema_field("f1", "BirthDate", label="birth", semantic_key="birth_date")]
        rules = [
            RuleItem(
                type=RuleType.FORMAT,
                rule_text="Use Japanese era format (e.g. R7/03/28)",
                field_ids=["f1"],
            ),
        ]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=rules,
        )
        assert ctx.fields[0].format_rule == "Use Japanese era format (e.g. R7/03/28)"

    def test_no_format_rule_is_none(self):
        fields = [_schema_field("f1", "Name", label="name", semantic_key="full_name")]
        ctx = self.svc.build(
            schema_fields=fields,
            user_info={},
            rules=[],
        )
        assert ctx.fields[0].format_rule is None


class TestGetUnansweredQuestions:
    def setup_method(self):
        self.svc = ContextService()

    def test_returns_unanswered_conditionals(self):
        rules = [
            RuleItem(type=RuleType.CONDITIONAL, rule_text="r1", field_ids=["f1"], question="Married?", options=["Yes", "No"]),
            RuleItem(type=RuleType.FORMAT, rule_text="r2", field_ids=["f2"]),
            RuleItem(type=RuleType.CONDITIONAL, rule_text="r3", field_ids=["f3"], question="Has dependents?", options=["Yes", "No"]),
        ]
        result = self.svc.get_unanswered_questions(rules)
        assert len(result) == 2

    def test_answered_questions_excluded(self):
        rules = [
            RuleItem(type=RuleType.CONDITIONAL, rule_text="r1", field_ids=["f1"], question="Married?", options=["Yes", "No"]),
        ]
        result = self.svc.get_unanswered_questions(rules, {"Married?": "Yes"})
        assert len(result) == 0
