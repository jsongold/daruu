"""Tests for label enrichment in FormContextBuilder.

Tests the _enrich_fields_with_labels and _find_nearby_text methods
which use proximity matching to attach nearby PDF text to form fields.
"""

import pytest

from app.domain.models.form_context import FormFieldSpec, LabelCandidate
from app.services.form_context.builder import FormContextBuilder


class TestFindNearbyText:
    """Tests for FormContextBuilder._find_nearby_text static method."""

    def _make_field(
        self,
        x: float = 100.0,
        y: float = 200.0,
        width: float = 150.0,
        height: float = 20.0,
        page: int | None = 1,
    ) -> FormFieldSpec:
        return FormFieldSpec(
            field_id="Text1",
            label="Text1",
            field_type="text",
            x=x,
            y=y,
            width=width,
            height=height,
            page=page,
        )

    def _make_block(
        self,
        text: str,
        x: float,
        y: float,
        width: float = 50.0,
        height: float = 12.0,
        page: int | None = 1,
    ) -> dict:
        return {
            "id": f"block_{text}",
            "text": text,
            "page": page,
            "bbox": [x, y, width, height],
            "font_name": "Arial",
            "font_size": 10,
        }

    def test_finds_nearby_label(self):
        field = self._make_field(x=100, y=200)
        blocks = [
            self._make_block("法人名", x=50, y=195),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 1
        assert result[0].text == "法人名"
        assert result[0].confidence > 0.0

    def test_returns_empty_when_no_blocks_nearby(self):
        field = self._make_field(x=100, y=200)
        blocks = [
            self._make_block("Far Away", x=1000, y=1000),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 0

    def test_filters_by_page(self):
        field = self._make_field(x=100, y=200, page=1)
        blocks = [
            self._make_block("Same Page", x=105, y=190, page=1),
            self._make_block("Different Page", x=105, y=190, page=2),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 1
        assert result[0].text == "Same Page"

    def test_returns_top_3_sorted_by_distance(self):
        field = self._make_field(x=100, y=200, width=100, height=20)
        # Field center is at (150, 210)
        blocks = [
            self._make_block("Far", x=200, y=290, width=50, height=12),    # center (225,296) ~ 113px
            self._make_block("Close", x=130, y=205, width=50, height=12),  # center (155,211) ~ 5px
            self._make_block("Medium", x=180, y=250, width=50, height=12), # center (205,256) ~ 71px
            self._make_block("Closest", x=148, y=208, width=4, height=4),  # center (150,210) ~ 0px
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 3
        assert result[0].text == "Closest"
        assert result[1].text == "Close"
        assert result[2].text == "Medium"

    def test_skips_empty_text_blocks(self):
        field = self._make_field(x=100, y=200)
        blocks = [
            self._make_block("", x=105, y=195),
            self._make_block("   ", x=105, y=195),
            self._make_block("Valid", x=110, y=195),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"

    def test_deduplicates_same_text(self):
        field = self._make_field(x=100, y=200)
        blocks = [
            self._make_block("Name", x=50, y=195),
            self._make_block("Name", x=55, y=195),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 1
        assert result[0].text == "Name"

    def test_confidence_decreases_with_distance(self):
        field = self._make_field(x=100, y=200, width=100, height=20)
        blocks = [
            self._make_block("Close", x=100, y=195, width=50, height=12),
            self._make_block("Far", x=200, y=280, width=50, height=12),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 2
        assert result[0].confidence > result[1].confidence

    def test_handles_block_without_bbox(self):
        field = self._make_field(x=100, y=200)
        blocks = [
            {"text": "No bbox", "page": 1},
            {"text": "Short bbox", "page": 1, "bbox": [100]},
            self._make_block("Valid", x=105, y=195),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"

    def test_no_page_filter_when_field_has_no_page(self):
        field = self._make_field(x=100, y=200, page=None)
        blocks = [
            self._make_block("Page1", x=105, y=195, page=1),
            self._make_block("Page2", x=110, y=195, page=2),
        ]
        result = FormContextBuilder._find_nearby_text(field, blocks)
        assert len(result) == 2


class TestEnrichFieldsWithLabels:
    """Tests for FormContextBuilder._enrich_fields_with_labels."""

    def test_skips_enrichment_when_no_document_service(self):
        builder = FormContextBuilder(
            data_source_repo=None,
            extraction_service=None,
            document_service=None,
        )
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = builder._enrich_fields_with_labels("doc1", fields)
        assert result is fields  # unchanged

    def test_skips_field_without_coordinates(self):
        class FakeDocService:
            def extract_text_blocks(self, doc_id):
                return [{"text": "Label", "page": 1, "bbox": [100, 200, 50, 12]}]

        builder = FormContextBuilder(
            data_source_repo=None,
            extraction_service=None,
            document_service=FakeDocService(),
        )
        fields = (
            FormFieldSpec(field_id="f1", label="f1"),  # no x/y
        )
        result = builder._enrich_fields_with_labels("doc1", fields)
        assert result[0].label_candidates == ()

    def test_enriches_field_with_nearby_text(self):
        class FakeDocService:
            def extract_text_blocks(self, doc_id):
                return [
                    {"text": "Name", "page": 1, "bbox": [95, 195, 40, 12]},
                ]

        builder = FormContextBuilder(
            data_source_repo=None,
            extraction_service=None,
            document_service=FakeDocService(),
        )
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200, width=150, height=20, page=1),
        )
        result = builder._enrich_fields_with_labels("doc1", fields)
        assert len(result[0].label_candidates) == 1
        assert result[0].label_candidates[0].text == "Name"

    def test_handles_extract_text_blocks_failure(self):
        class FakeDocService:
            def extract_text_blocks(self, doc_id):
                raise RuntimeError("PDF parsing failed")

        builder = FormContextBuilder(
            data_source_repo=None,
            extraction_service=None,
            document_service=FakeDocService(),
        )
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = builder._enrich_fields_with_labels("doc1", fields)
        assert result is fields  # returns original on error
