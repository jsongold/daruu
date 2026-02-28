"""Tests for label enrichment via ProximityFieldEnricher and compact JSON prompt.

Tests the proximity matching logic (_find_nearby_text, _enrich_fields_by_proximity)
and the compact JSON serialization in build_field_identification_prompt.
"""

import json

import pytest

from app.domain.models.form_context import FormFieldSpec, LabelCandidate
from app.models.acroform import AcroFormFieldInfo, AcroFormFieldsResponse, PageDimensions
from app.models.common import BBox
from app.services.form_context.enricher import ProximityFieldEnricher


class TestFindNearbyText:
    """Tests for ProximityFieldEnricher._find_nearby_text static method."""

    def _make_bbox(
        self,
        x: float = 100.0,
        y: float = 200.0,
        width: float = 150.0,
        height: float = 20.0,
        page: int = 1,
    ) -> BBox:
        return BBox(x=x, y=y, width=width, height=height, page=page)

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
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            self._make_block("法人名", x=50, y=195),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "法人名"
        assert result[0].confidence > 0.0

    def test_returns_empty_when_no_blocks_nearby(self):
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            self._make_block("Far Away", x=1000, y=1000),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 0

    def test_filters_by_page(self):
        bbox = self._make_bbox(x=100, y=200, page=1)
        blocks = [
            self._make_block("Same Page", x=105, y=190, page=1),
            self._make_block("Different Page", x=105, y=190, page=2),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Same Page"

    def test_returns_top_3_sorted_by_distance(self):
        bbox = self._make_bbox(x=100, y=200, width=100, height=20)
        # BBox center is at (150, 210)
        blocks = [
            self._make_block("Far", x=200, y=290, width=50, height=12),    # center (225,296) ~ 113px
            self._make_block("Close", x=130, y=205, width=50, height=12),  # center (155,211) ~ 5px
            self._make_block("Medium", x=180, y=250, width=50, height=12), # center (205,256) ~ 71px
            self._make_block("Closest", x=148, y=208, width=4, height=4),  # center (150,210) ~ 0px
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 3
        assert result[0].text == "Closest"
        assert result[1].text == "Close"
        assert result[2].text == "Medium"

    def test_skips_empty_text_blocks(self):
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            self._make_block("", x=105, y=195),
            self._make_block("   ", x=105, y=195),
            self._make_block("Valid", x=110, y=195),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"

    def test_deduplicates_same_text(self):
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            self._make_block("Name", x=50, y=195),
            self._make_block("Name", x=55, y=195),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Name"

    def test_confidence_decreases_with_distance(self):
        bbox = self._make_bbox(x=100, y=200, width=100, height=20)
        blocks = [
            self._make_block("Close", x=100, y=195, width=50, height=12),
            self._make_block("Far", x=200, y=280, width=50, height=12),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 2
        assert result[0].confidence > result[1].confidence

    def test_handles_block_without_bbox(self):
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            {"text": "No bbox", "page": 1},
            {"text": "Short bbox", "page": 1, "bbox": [100]},
            self._make_block("Valid", x=105, y=195),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"

    def test_no_page_filter_when_block_has_no_page(self):
        bbox = self._make_bbox(x=100, y=200, page=1)
        blocks = [
            self._make_block("NoPage", x=105, y=195, page=None),
        ]
        result = ProximityFieldEnricher._find_nearby_text(bbox, blocks)
        assert len(result) == 1


class TestEnrichFieldsWithLabels:
    """Tests for ProximityFieldEnricher.enrich (async) and _enrich_fields_by_proximity."""

    def test_skips_field_without_acroform_match(self):
        """Fields not found in AcroForm data are returned unchanged."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [{"text": "Label", "page": 1, "bbox": [100, 200, 50, 12]}]

            def get_acroform_fields(self, doc_id):
                return AcroFormFieldsResponse(
                    has_acroform=True,
                    page_dimensions=[PageDimensions(page=1, width=595, height=842)],
                    fields=[],  # no matching field
                    preview_scale=2,
                )

        enricher = ProximityFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1"),  # no AcroForm match
        )
        result = enricher._enrich_fields_by_proximity("doc1", fields)
        assert result[0].label_candidates == ()

    def test_enriches_field_with_nearby_text_using_raw_bbox(self):
        """Fields get enriched using raw AcroForm coordinates (PDF points)."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [
                    {"text": "Name", "page": 1, "bbox": [95, 195, 40, 12]},
                ]

            def get_acroform_fields(self, doc_id):
                return AcroFormFieldsResponse(
                    has_acroform=True,
                    page_dimensions=[PageDimensions(page=1, width=595, height=842)],
                    fields=[
                        AcroFormFieldInfo(
                            field_name="f1",
                            field_type="text",
                            bbox=BBox(x=100, y=200, width=150, height=20, page=1),
                        ),
                    ],
                    preview_scale=2,
                )

        enricher = ProximityFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(
                field_id="f1", label="f1",
                x=0.169, y=0.238, width=0.25, height=0.024, page=1,
            ),
        )
        result = enricher._enrich_fields_by_proximity("doc1", fields)
        assert len(result[0].label_candidates) == 1
        assert result[0].label_candidates[0].text == "Name"

    def test_handles_extract_text_blocks_failure(self):
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                raise RuntimeError("PDF parsing failed")

        enricher = ProximityFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = enricher._enrich_fields_by_proximity("doc1", fields)
        assert result is fields  # returns original on error

    def test_handles_get_acroform_fields_failure(self):
        """Enrichment gracefully degrades when AcroForm extraction fails."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [{"text": "Label", "page": 1, "bbox": [100, 200, 50, 12]}]

            def get_acroform_fields(self, doc_id):
                raise RuntimeError("AcroForm extraction failed")

        enricher = ProximityFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = enricher._enrich_fields_by_proximity("doc1", fields)
        # No raw_bbox_map entries, so fields are returned without enrichment
        assert result[0].label_candidates == ()

    def test_handles_get_acroform_fields_returns_none(self):
        """Enrichment handles None response from get_acroform_fields."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [{"text": "Label", "page": 1, "bbox": [100, 200, 50, 12]}]

            def get_acroform_fields(self, doc_id):
                return None

        enricher = ProximityFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = enricher._enrich_fields_by_proximity("doc1", fields)
        assert result[0].label_candidates == ()

    def test_coordinate_mismatch_no_longer_prevents_enrichment(self):
        """Regression test: normalized 0-1 coords from frontend don't affect enrichment.

        Previously, field.x/y (normalized 0-1 from frontend) were compared directly
        against text block bboxes (raw PDF points ~100-600), causing all distances
        to exceed the 150pt threshold. Now we use raw AcroForm bboxes instead.
        """
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                # Raw PDF points from PyMuPDF
                return [
                    {"text": "法人名（フリガナ）", "page": 1, "bbox": [102, 195, 148, 18]},
                    {"text": "法人名", "page": 1, "bbox": [102, 225, 80, 18]},
                ]

            def get_acroform_fields(self, doc_id):
                return AcroFormFieldsResponse(
                    has_acroform=True,
                    page_dimensions=[PageDimensions(page=1, width=595, height=842)],
                    fields=[
                        AcroFormFieldInfo(
                            field_name="Text1",
                            field_type="text",
                            bbox=BBox(x=100, y=200, width=200, height=20, page=1),
                        ),
                    ],
                    preview_scale=2,
                )

        enricher = ProximityFieldEnricher(document_service=FakeDocService())
        # Frontend sends normalized 0-1 coordinates — these should NOT be used
        fields = (
            FormFieldSpec(
                field_id="Text1", label="Text1",
                x=0.169, y=0.238, width=0.337, height=0.024, page=1,
            ),
        )
        result = enricher._enrich_fields_by_proximity("doc1", fields)
        # With the fix, raw AcroForm bbox (100, 200) is used for matching,
        # so the nearby text at (102, 195) IS found
        assert len(result[0].label_candidates) > 0
        texts = [c.text for c in result[0].label_candidates]
        assert "法人名（フリガナ）" in texts


class TestCompactFieldIdentificationPrompt:
    """Tests for compact JSON serialization in build_field_identification_prompt."""

    def test_compact_keys_used(self):
        """Verify abbreviated keys: id, t, p, b for fields; s, p, b for blocks."""
        from app.services.vision_autofill.prompts import build_field_identification_prompt

        fields = (
            FormFieldSpec(field_id="Text1", label="Text1", field_type="text", page=1),
        )
        text_blocks = [
            {"text": "法人名", "page": 1, "bbox": [100, 200, 50, 12]},
        ]
        raw_bbox_map = {
            "Text1": {"x": 150.0, "y": 200.0, "width": 200.0, "height": 20.0, "page": 1},
        }

        result = build_field_identification_prompt(fields, text_blocks, raw_bbox_map)

        # Should contain compact field keys
        assert '"id":"Text1"' in result
        assert '"t":"text"' in result
        assert '"p":1' in result
        # Should contain compact block keys
        assert '"s":"法人名"' in result
        # Should NOT contain verbose keys
        assert '"field_id"' not in result
        assert '"field_type"' not in result
        assert '"text":' not in result  # block text key is now "s"

    def test_label_omitted_when_equals_id(self):
        """Label key should be omitted when label == field_id."""
        from app.services.vision_autofill.prompts import build_field_identification_prompt

        fields = (
            FormFieldSpec(field_id="Text1", label="Text1", field_type="text", page=1),
        )
        raw_bbox_map = {}

        result = build_field_identification_prompt(fields, [], raw_bbox_map)
        assert '"l":' not in result

    def test_label_included_when_different_from_id(self):
        """Label key should be present when label != field_id."""
        from app.services.vision_autofill.prompts import build_field_identification_prompt

        fields = (
            FormFieldSpec(field_id="field_1", label="Company Name", field_type="text", page=1),
        )
        raw_bbox_map = {}

        result = build_field_identification_prompt(fields, [], raw_bbox_map)
        assert '"l":"Company Name"' in result

    def test_bbox_rounded_to_int(self):
        """Bbox values should be rounded to integers."""
        from app.services.vision_autofill.prompts import build_field_identification_prompt

        fields = (
            FormFieldSpec(field_id="Text1", label="Text1", field_type="text", page=1),
        )
        text_blocks = [
            {"text": "Label", "page": 1, "bbox": [100.7, 200.3, 50.9, 12.1]},
        ]
        raw_bbox_map = {
            "Text1": {"x": 150.5, "y": 200.8, "width": 200.2, "height": 20.9, "page": 1},
        }

        result = build_field_identification_prompt(fields, text_blocks, raw_bbox_map)
        # Field bbox: [150, 200, 200, 20]
        assert '"b":[150,200,200,20]' in result
        # Block bbox: [100, 200, 50, 12]
        assert '"b":[100,200,50,12]' in result

    def test_no_indent_in_output(self):
        """Output should use compact JSON with no indentation."""
        from app.services.vision_autofill.prompts import build_field_identification_prompt

        fields = (
            FormFieldSpec(field_id="Text1", label="Text1", field_type="text", page=1),
            FormFieldSpec(field_id="Text2", label="Text2", field_type="text", page=1),
        )
        text_blocks = [
            {"text": "A", "page": 1, "bbox": [100, 200, 50, 12]},
            {"text": "B", "page": 1, "bbox": [200, 300, 50, 12]},
        ]
        raw_bbox_map = {}

        result = build_field_identification_prompt(fields, text_blocks, raw_bbox_map)
        # Compact JSON should be a single line between ```json blocks
        json_sections = result.split("```json\n")
        for section in json_sections[1:]:
            json_str = section.split("\n```")[0]
            assert "\n" not in json_str
