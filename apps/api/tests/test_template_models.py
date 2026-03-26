"""Tests for Template Pydantic models.

Tests all Phase 2 template-related models including:
- Template creation and validation
- TemplateBbox validation (coordinates, field types)
- TemplateRule validation (rule types, configs)
- Immutability (frozen models)
- Serialization/deserialization
- Edge cases (empty bboxes, no rules, etc.)
"""

import json

import pytest
from pydantic import ValidationError

# =============================================================================
# Template Model Tests
# =============================================================================


class TestTemplateBbox:
    """Tests for TemplateBbox model."""

    def test_valid_bbox(self) -> None:
        """Test creating a valid TemplateBbox."""
        from app.models.template import FieldType, TemplateBbox

        bbox = TemplateBbox(
            id="field-1",
            x=10.0,
            y=20.0,
            width=100.0,
            height=50.0,
            page=1,
            field_type=FieldType.TEXT,
        )
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 100.0
        assert bbox.height == 50.0
        assert bbox.page == 1
        assert bbox.id == "field-1"
        assert bbox.field_type == FieldType.TEXT

    def test_bbox_with_optional_label(self) -> None:
        """Test bbox with optional label."""
        from app.models.template import FieldType, TemplateBbox

        bbox = TemplateBbox(
            id="dob-field",
            x=10.0,
            y=20.0,
            width=100.0,
            height=50.0,
            page=1,
            field_type=FieldType.DATE,
            label="Date of Birth",
        )
        assert bbox.label == "Date of Birth"

    def test_bbox_negative_width_fails(self) -> None:
        """Test that negative width is rejected."""
        from app.models.template import FieldType, TemplateBbox

        with pytest.raises(ValidationError):
            TemplateBbox(
                id="test",
                x=10.0,
                y=20.0,
                width=-100.0,
                height=50.0,
                page=1,
                field_type=FieldType.TEXT,
            )

    def test_bbox_negative_height_fails(self) -> None:
        """Test that negative height is rejected."""
        from app.models.template import FieldType, TemplateBbox

        with pytest.raises(ValidationError):
            TemplateBbox(
                id="test",
                x=10.0,
                y=20.0,
                width=100.0,
                height=-50.0,
                page=1,
                field_type=FieldType.TEXT,
            )

    def test_bbox_zero_page_fails(self) -> None:
        """Test that page 0 is rejected (1-indexed)."""
        from app.models.template import FieldType, TemplateBbox

        with pytest.raises(ValidationError):
            TemplateBbox(
                id="test",
                x=10.0,
                y=20.0,
                width=100.0,
                height=50.0,
                page=0,
                field_type=FieldType.TEXT,
            )

    def test_bbox_is_frozen(self) -> None:
        """Test that TemplateBbox is immutable."""
        from app.models.template import FieldType, TemplateBbox

        bbox = TemplateBbox(
            id="test",
            x=10.0,
            y=20.0,
            width=100.0,
            height=50.0,
            page=1,
            field_type=FieldType.TEXT,
        )
        with pytest.raises(ValidationError):
            bbox.x = 20.0  # type: ignore

    def test_bbox_field_types(self) -> None:
        """Test various valid field types."""
        from app.models.template import FieldType, TemplateBbox

        valid_types = [
            FieldType.TEXT,
            FieldType.DATE,
            FieldType.CHECKBOX,
            FieldType.SIGNATURE,
            FieldType.NUMBER,
        ]
        for field_type in valid_types:
            bbox = TemplateBbox(
                id="test_field",
                x=10.0,
                y=20.0,
                width=100.0,
                height=50.0,
                page=1,
                field_type=field_type,
            )
            assert bbox.field_type == field_type

    def test_bbox_serialization(self) -> None:
        """Test bbox can be serialized to dict/JSON."""
        from app.models.template import FieldType, TemplateBbox

        bbox = TemplateBbox(
            id="test",
            x=10.0,
            y=20.0,
            width=100.0,
            height=50.0,
            page=1,
            field_type=FieldType.TEXT,
            label="Test Label",
        )
        data = bbox.model_dump()
        assert data["x"] == 10.0
        assert data["id"] == "test"
        assert data["label"] == "Test Label"

        # Test JSON serialization
        json_str = bbox.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["field_type"] == "text"


class TestTemplateRule:
    """Tests for TemplateRule model."""

    def test_valid_format_rule(self) -> None:
        """Test creating a valid format rule."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="phone",
            rule_type=RuleType.FORMAT,
            rule_config={"pattern": r"^\d{3}-\d{4}-\d{4}$"},
        )
        assert rule.field_id == "phone"
        assert rule.rule_type == RuleType.FORMAT
        assert rule.rule_config["pattern"] == r"^\d{3}-\d{4}-\d{4}$"

    def test_valid_required_rule(self) -> None:
        """Test creating a valid required rule."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="name",
            rule_type=RuleType.REQUIRED,
            rule_config={"message": "Name is required"},
        )
        assert rule.rule_type == RuleType.REQUIRED

    def test_valid_range_rule(self) -> None:
        """Test creating a valid range rule."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="age",
            rule_type=RuleType.RANGE,
            rule_config={"min": 0, "max": 150},
        )
        assert rule.rule_config["min"] == 0
        assert rule.rule_config["max"] == 150

    def test_valid_pattern_rule(self) -> None:
        """Test creating a valid pattern rule."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="ssn",
            rule_type=RuleType.PATTERN,
            rule_config={"regex": r"^\d{3}-\d{2}-\d{4}$"},
        )
        assert rule.rule_config["regex"] == r"^\d{3}-\d{2}-\d{4}$"

    def test_valid_dependency_rule(self) -> None:
        """Test creating a dependency rule."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="spouse_name",
            rule_type=RuleType.DEPENDENCY,
            rule_config={"depends_on": "marital_status", "condition": "equals", "value": "married"},
        )
        assert rule.rule_config["depends_on"] == "marital_status"

    def test_rule_is_frozen(self) -> None:
        """Test that TemplateRule is immutable."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="test",
            rule_type=RuleType.REQUIRED,
            rule_config={},
        )
        with pytest.raises(ValidationError):
            rule.field_id = "new_name"  # type: ignore

    def test_rule_with_empty_config(self) -> None:
        """Test rule with empty config is valid."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="test",
            rule_type=RuleType.REQUIRED,
            rule_config={},
        )
        assert rule.rule_config == {}

    def test_rule_serialization(self) -> None:
        """Test rule can be serialized to dict/JSON."""
        from app.models.template import RuleType, TemplateRule

        rule = TemplateRule(
            field_id="phone",
            rule_type=RuleType.FORMAT,
            rule_config={"pattern": r"^\d+$"},
        )
        data = rule.model_dump()
        assert data["field_id"] == "phone"
        assert data["rule_type"] == "format"


class TestTemplate:
    """Tests for Template model."""

    def test_valid_template_minimal(self) -> None:
        """Test creating a minimal valid template."""
        from datetime import datetime, timezone

        from app.models.template import Template

        now = datetime.now(timezone.utc)
        template = Template(
            id="tpl-001",
            name="Basic Form",
            form_type="application",
            created_at=now,
            updated_at=now,
        )
        assert template.id == "tpl-001"
        assert template.name == "Basic Form"
        assert template.form_type == "application"
        assert template.bboxes == ()
        assert template.rules == ()
        assert template.embedding_id is None

    def test_valid_template_with_bboxes(self) -> None:
        """Test creating a template with bboxes."""
        from datetime import datetime, timezone

        from app.models.template import FieldType, Template, TemplateBbox

        now = datetime.now(timezone.utc)
        bbox1 = TemplateBbox(
            id="name",
            x=10.0,
            y=20.0,
            width=100.0,
            height=30.0,
            page=1,
            field_type=FieldType.TEXT,
            label="Full Name",
        )
        bbox2 = TemplateBbox(
            id="dob",
            x=10.0,
            y=60.0,
            width=100.0,
            height=30.0,
            page=1,
            field_type=FieldType.DATE,
            label="Date of Birth",
        )

        template = Template(
            id="tpl-002",
            name="Person Info Form",
            form_type="personal_info",
            bboxes=(bbox1, bbox2),
            created_at=now,
            updated_at=now,
        )
        assert len(template.bboxes) == 2
        assert template.bboxes[0].id == "name"
        assert template.bboxes[1].id == "dob"

    def test_valid_template_with_rules(self) -> None:
        """Test creating a template with rules."""
        from datetime import datetime, timezone

        from app.models.template import RuleType, Template, TemplateRule

        now = datetime.now(timezone.utc)
        rule1 = TemplateRule(
            field_id="name",
            rule_type=RuleType.REQUIRED,
            rule_config={"message": "Name is required"},
        )
        rule2 = TemplateRule(
            field_id="email",
            rule_type=RuleType.FORMAT,
            rule_config={"pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$"},
        )

        template = Template(
            id="tpl-003",
            name="Contact Form",
            form_type="contact",
            rules=(rule1, rule2),
            created_at=now,
            updated_at=now,
        )
        assert len(template.rules) == 2
        assert template.rules[0].rule_type == RuleType.REQUIRED
        assert template.rules[1].rule_type == RuleType.FORMAT

    def test_valid_template_full(self) -> None:
        """Test creating a fully populated template."""
        from datetime import datetime, timezone

        from app.models.template import FieldType, RuleType, Template, TemplateBbox, TemplateRule

        now = datetime.now(timezone.utc)
        bbox = TemplateBbox(
            id="ssn",
            x=10.0,
            y=20.0,
            width=100.0,
            height=30.0,
            page=1,
            field_type=FieldType.TEXT,
            label="Social Security Number",
        )
        rule = TemplateRule(
            field_id="ssn",
            rule_type=RuleType.PATTERN,
            rule_config={"regex": r"^\d{3}-\d{2}-\d{4}$"},
        )

        template = Template(
            id="tpl-full",
            tenant_id="tenant-456",
            name="Tax Form",
            form_type="tax",
            bboxes=(bbox,),
            rules=(rule,),
            embedding_id="emb-123",
            field_count=1,
            created_at=now,
            updated_at=now,
        )
        assert template.embedding_id == "emb-123"
        assert template.field_count == 1

    def test_template_empty_name_fails(self) -> None:
        """Test that empty name is rejected."""
        from datetime import datetime, timezone

        from app.models.template import Template

        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            Template(
                id="tpl-001",
                name="",
                form_type="test",
                created_at=now,
                updated_at=now,
            )

    def test_template_is_frozen(self) -> None:
        """Test that Template is immutable."""
        from datetime import datetime, timezone

        from app.models.template import Template

        now = datetime.now(timezone.utc)
        template = Template(
            id="tpl-001",
            name="Test",
            form_type="test",
            created_at=now,
            updated_at=now,
        )
        with pytest.raises(ValidationError):
            template.name = "New Name"  # type: ignore

    def test_template_serialization(self) -> None:
        """Test template can be serialized to dict/JSON."""
        from datetime import datetime, timezone

        from app.models.template import FieldType, RuleType, Template, TemplateBbox, TemplateRule

        now = datetime.now(timezone.utc)
        bbox = TemplateBbox(
            id="test", x=10.0, y=20.0, width=100.0, height=30.0, page=1, field_type=FieldType.TEXT
        )
        rule = TemplateRule(field_id="test", rule_type=RuleType.REQUIRED, rule_config={})
        template = Template(
            id="tpl-001",
            name="Test Form",
            form_type="test",
            bboxes=(bbox,),
            rules=(rule,),
            created_at=now,
            updated_at=now,
        )

        data = template.model_dump()
        assert data["id"] == "tpl-001"
        assert len(data["bboxes"]) == 1
        assert len(data["rules"]) == 1

        # Test JSON round-trip
        json_str = template.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["name"] == "Test Form"
        assert parsed["bboxes"][0]["id"] == "test"

    def test_template_deserialization(self) -> None:
        """Test template can be deserialized from dict."""
        from datetime import datetime, timezone

        from app.models.template import Template

        now = datetime.now(timezone.utc)
        data = {
            "id": "tpl-001",
            "name": "Test Form",
            "form_type": "test",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "bboxes": [
                {
                    "id": "name",
                    "x": 10.0,
                    "y": 20.0,
                    "width": 100.0,
                    "height": 30.0,
                    "page": 1,
                    "field_type": "text",
                }
            ],
            "rules": [
                {
                    "field_id": "name",
                    "rule_type": "required",
                    "rule_config": {},
                }
            ],
        }
        template = Template.model_validate(data)
        assert template.id == "tpl-001"
        assert len(template.bboxes) == 1
        assert len(template.rules) == 1


class TestTemplateCreate:
    """Tests for TemplateCreate request model."""

    def test_valid_create_request(self) -> None:
        """Test creating a valid template create request."""
        from app.models.template import TemplateCreate

        request = TemplateCreate(
            name="New Form",
            form_type="application",
        )
        assert request.name == "New Form"
        assert request.form_type == "application"
        assert request.bboxes == []
        assert request.rules == []

    def test_create_with_bboxes_and_rules(self) -> None:
        """Test create request with bboxes and rules."""
        from app.models.template import (
            FieldType,
            RuleType,
            TemplateBbox,
            TemplateCreate,
            TemplateRule,
        )

        bbox = TemplateBbox(
            id="field1", x=10.0, y=20.0, width=100.0, height=30.0, page=1, field_type=FieldType.TEXT
        )
        rule = TemplateRule(field_id="field1", rule_type=RuleType.REQUIRED, rule_config={})

        request = TemplateCreate(
            name="Form with Fields",
            form_type="form",
            bboxes=[bbox],
            rules=[rule],
        )
        assert len(request.bboxes) == 1
        assert len(request.rules) == 1


class TestTemplateMatch:
    """Tests for TemplateMatch response model."""

    def test_valid_match(self) -> None:
        """Test creating a valid template match result."""
        from app.models.template import TemplateMatch

        match = TemplateMatch(
            template_id="tpl-001",
            template_name="Test",
            form_type="test",
            similarity_score=0.95,
        )
        assert match.template_id == "tpl-001"
        assert match.similarity_score == 0.95

    def test_match_score_validation(self) -> None:
        """Test that score is between 0 and 1."""
        from app.models.template import TemplateMatch

        # Score > 1 should fail
        with pytest.raises(ValidationError):
            TemplateMatch(
                template_id="tpl-001",
                template_name="Test",
                form_type="test",
                similarity_score=1.5,
            )

        # Score < 0 should fail
        with pytest.raises(ValidationError):
            TemplateMatch(
                template_id="tpl-001",
                template_name="Test",
                form_type="test",
                similarity_score=-0.1,
            )


class TestTemplateResponse:
    """Tests for TemplateResponse model."""

    def test_valid_response(self) -> None:
        """Test creating a valid template response."""
        from datetime import datetime, timezone

        from app.models.template import TemplateResponse

        now = datetime.now(timezone.utc)
        response = TemplateResponse(
            id="tpl-001",
            name="Test Form",
            form_type="test",
            field_count=5,
            created_at=now,
            updated_at=now,
        )
        assert response.id == "tpl-001"
        assert response.field_count == 5


class TestTemplateListResponse:
    """Tests for TemplateListResponse model."""

    def test_valid_list_response(self) -> None:
        """Test creating a valid template list response."""
        from datetime import datetime, timezone

        from app.models.template import TemplateListResponse, TemplateResponse

        now = datetime.now(timezone.utc)
        item1 = TemplateResponse(
            id="tpl-001",
            name="Form 1",
            form_type="type1",
            field_count=3,
            created_at=now,
            updated_at=now,
        )
        item2 = TemplateResponse(
            id="tpl-002",
            name="Form 2",
            form_type="type2",
            field_count=5,
            created_at=now,
            updated_at=now,
        )

        response = TemplateListResponse(
            templates=(item1, item2),
            total=2,
        )
        assert len(response.templates) == 2
        assert response.total == 2

    def test_empty_list_response(self) -> None:
        """Test empty list response."""
        from app.models.template import TemplateListResponse

        response = TemplateListResponse(templates=(), total=0)
        assert response.templates == ()
        assert response.total == 0
