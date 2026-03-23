"""Tests for StructuralResolver — Python-only field identification."""

import pytest

from app.domain.models.form_context import FormFieldSpec
from app.services.form_context.structural_resolver import (
    StructuralResolver,
    StructuralResolverResult,
    _split_field_id,
)


class TestSplitFieldId:
    """Tests for _split_field_id helper."""

    def test_underscore_separated(self):
        assert _split_field_id("employee_name") == ["employee", "name"]

    def test_camel_case(self):
        assert _split_field_id("employeeName") == ["employee", "name"]

    def test_hyphen_separated(self):
        assert _split_field_id("date-of-birth") == ["date", "of", "birth"]

    def test_mixed(self):
        assert _split_field_id("company_addressLine1") == ["company", "address", "line"]

    def test_single_word(self):
        assert _split_field_id("name") == ["name"]

    def test_all_caps(self):
        result = _split_field_id("ID")
        assert result == ["id"]


class TestResolveFieldIds:
    """Tests for StructuralResolver.resolve_field_ids."""

    def test_semantic_field_id(self):
        fields = (
            FormFieldSpec(field_id="employee_name", label="employee_name"),
            FormFieldSpec(field_id="companyAddress", label="companyAddress"),
        )
        result = StructuralResolver.resolve_field_ids(fields)
        assert "employee_name" in result["labels"]
        assert "companyAddress" in result["labels"]
        assert result["labels"]["employee_name"] == "Employee Name"
        assert result["labels"]["companyAddress"] == "Company Address"

    def test_non_semantic_field_id(self):
        fields = (
            FormFieldSpec(field_id="Text1", label="Text1"),
            FormFieldSpec(field_id="Field3", label="Field3"),
            FormFieldSpec(field_id="Check1", label="Check1"),
        )
        result = StructuralResolver.resolve_field_ids(fields)
        assert len(result["labels"]) == 0

    def test_single_word_not_resolved(self):
        """Single-word IDs need 2+ meaningful words."""
        fields = (
            FormFieldSpec(field_id="name", label="name"),
        )
        result = StructuralResolver.resolve_field_ids(fields)
        assert len(result["labels"]) == 0

    def test_confidence_is_0_8(self):
        fields = (
            FormFieldSpec(field_id="date_of_birth", label="date_of_birth"),
        )
        result = StructuralResolver.resolve_field_ids(fields)
        assert result["confidence"]["date_of_birth"] == 0.8


class TestResolveByTableStructure:
    """Tests for StructuralResolver.resolve_by_table_structure."""

    def test_returns_empty_when_no_pdf_bytes(self):
        class FakeDocService:
            def get_pdf_bytes(self, doc_id):
                return None

            def get_acroform_fields(self, doc_id):
                return None

        resolver = StructuralResolver(document_service=FakeDocService())
        fields = (FormFieldSpec(field_id="f1", label="f1", page=1),)
        result = resolver.resolve_by_table_structure("doc1", fields)
        assert len(result["labels"]) == 0

    def test_returns_empty_when_no_page_info(self):
        class FakeDocService:
            def get_pdf_bytes(self, doc_id):
                return b"%PDF-fake"

            def get_acroform_fields(self, doc_id):
                return None

        resolver = StructuralResolver(document_service=FakeDocService())
        fields = (FormFieldSpec(field_id="f1", label="f1"),)  # no page
        result = resolver.resolve_by_table_structure("doc1", fields)
        assert len(result["labels"]) == 0


class TestResolveIntegration:
    """Tests for StructuralResolver.resolve orchestration."""

    def test_field_id_resolution_runs_first(self):
        class FakeDocService:
            def get_pdf_bytes(self, doc_id):
                return None

            def get_acroform_fields(self, doc_id):
                return None

        resolver = StructuralResolver(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="employee_name", label="employee_name"),
            FormFieldSpec(field_id="Text1", label="Text1", page=1),
        )
        result = resolver.resolve("doc1", fields)

        assert "employee_name" in result.field_labels
        assert result.field_labels["employee_name"] == "Employee Name"
        assert result.resolution_method["employee_name"] == "field_id"
        assert "Text1" in result.unresolved_field_ids

    def test_all_unresolved_when_no_semantics(self):
        class FakeDocService:
            def get_pdf_bytes(self, doc_id):
                return None

            def get_acroform_fields(self, doc_id):
                return None

        resolver = StructuralResolver(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="Text1", label="Text1"),
            FormFieldSpec(field_id="Text2", label="Text2"),
        )
        result = resolver.resolve("doc1", fields)
        assert len(result.field_labels) == 0
        assert set(result.unresolved_field_ids) == {"Text1", "Text2"}

    def test_result_dataclass_immutable(self):
        result = StructuralResolverResult(
            field_labels={"f1": "Name"},
            unresolved_field_ids=("f2",),
            confidence={"f1": 0.8},
            resolution_method={"f1": "field_id"},
        )
        with pytest.raises(AttributeError):
            result.field_labels = {}
