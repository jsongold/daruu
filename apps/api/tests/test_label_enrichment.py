"""Tests for label enrichment via DirectionalFieldEnricher and compact JSON prompt.

Tests the directional matching logic (compute_directional_labels, DirectionalFieldEnricher)
and the compact JSON serialization in build_field_identification_prompt.
"""

import pytest

from app.domain.models.form_context import FormFieldSpec, LabelCandidate
from app.models.acroform import AcroFormFieldInfo, AcroFormFieldsResponse, PageDimensions
from app.models.common import BBox
from app.services.form_context.enricher import (
    DirectionalFieldEnricher,
    NearbyLabel,
    compute_directional_labels,
)


class TestDirectionalLabels:
    """Tests for compute_directional_labels standalone function."""

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

    def test_finds_left_label(self):
        """Text to the left of the field is found."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        # Block right edge (50+50=100) == field left (100), Y-centers close
        blocks = [
            self._make_block("法人名", x=40, y=198, width=50, height=12),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "法人名"
        assert result[0].direction == "left"

    def test_finds_above_label(self):
        """Text above the field is found."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        # Block bottom (170+12=182) < field top (200), X-centers within tolerance
        blocks = [
            self._make_block("Name", x=120, y=170, width=50, height=12),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Name"
        assert result[0].direction == "above"

    def test_finds_right_label(self):
        """Text to the right of the field is found."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        # Block left (260) >= field right (250), Y-centers close
        blocks = [
            self._make_block("万円", x=260, y=200, width=20, height=12),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "万円"
        assert result[0].direction == "right"

    def test_rejects_below_text(self):
        """Text below the field is NOT found (no 'below' direction)."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        # Block is below: block_y=230 > field_bottom=220
        blocks = [
            self._make_block("Below Label", x=100, y=230, width=50, height=12),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 0

    def test_distance_threshold(self):
        """Blocks beyond max_distance are excluded."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        # Left block far away: block right edge=30, field left=100 -> dist=70 > 50
        blocks = [
            self._make_block("Too Far", x=0, y=200, width=30, height=12),
        ]
        result = compute_directional_labels(bbox, blocks, max_distance=50.0)
        assert len(result) == 0

    def test_y_tolerance_for_left(self):
        """Left blocks with Y-center diff exceeding tolerance are excluded."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        # Y-center of field: 210, Y-center of block: 200+50=250 -> diff=40 > 15
        blocks = [
            self._make_block("Bad Y", x=40, y=244, width=50, height=12),
        ]
        result = compute_directional_labels(bbox, blocks, y_tolerance=15.0)
        assert len(result) == 0

    def test_single_char_exclusion(self):
        """Single-character text blocks are excluded (min_text_length=2)."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        blocks = [
            self._make_block("X", x=40, y=198, width=10, height=12),  # single char
            self._make_block("名前", x=40, y=198, width=30, height=12),  # 2 chars
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "名前"

    def test_page_filtering(self):
        """Blocks on different pages are excluded."""
        bbox = self._make_bbox(x=100, y=200, page=1)
        blocks = [
            self._make_block("Same Page", x=40, y=198, width=50, height=12, page=1),
            self._make_block("Diff Page", x=40, y=198, width=50, height=12, page=2),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Same Page"

    def test_deduplication_by_sorting(self):
        """Results are sorted by distance — closest first."""
        bbox = self._make_bbox(x=100, y=200, width=150, height=20)
        blocks = [
            self._make_block("Far Left", x=30, y=198, width=20, height=12),  # dist=50
            self._make_block("Near Left", x=80, y=198, width=20, height=12),  # dist=0
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 2
        assert result[0].text == "Near Left"
        assert result[1].text == "Far Left"

    def test_handles_block_without_bbox(self):
        """Blocks without bbox or with short bbox are skipped."""
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            {"text": "No bbox", "page": 1},
            {"text": "Short bbox", "page": 1, "bbox": [100]},
            self._make_block("Valid", x=40, y=198, width=50, height=12),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"

    def test_no_page_filter_when_block_has_no_page(self):
        """Blocks without page info pass page filter."""
        bbox = self._make_bbox(x=100, y=200, page=1)
        blocks = [
            self._make_block("NoPage", x=40, y=198, width=50, height=12, page=None),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1

    def test_skips_empty_text_blocks(self):
        """Empty and whitespace-only blocks are excluded."""
        bbox = self._make_bbox(x=100, y=200)
        blocks = [
            self._make_block("", x=40, y=198),
            self._make_block("   ", x=40, y=198),
            self._make_block("Valid", x=40, y=198, width=50, height=12),
        ]
        result = compute_directional_labels(bbox, blocks)
        assert len(result) == 1
        assert result[0].text == "Valid"


class TestEnrichFieldsWithLabels:
    """Tests for DirectionalFieldEnricher.enrich (async) and _enrich_fields_directionally."""

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

        enricher = DirectionalFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1"),  # no AcroForm match
        )
        result = enricher._enrich_fields_directionally("doc1", fields)
        assert result[0].label_candidates == ()

    def test_enriches_field_with_left_label_using_raw_bbox(self):
        """Fields get enriched using raw AcroForm coordinates (PDF points)."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [
                    # Block right edge (80+40=120) <= field left (150), Y-centers close
                    {"text": "Name", "page": 1, "bbox": [80, 198, 40, 12]},
                ]

            def get_acroform_fields(self, doc_id):
                return AcroFormFieldsResponse(
                    has_acroform=True,
                    page_dimensions=[PageDimensions(page=1, width=595, height=842)],
                    fields=[
                        AcroFormFieldInfo(
                            field_name="f1",
                            field_type="text",
                            bbox=BBox(x=150, y=200, width=150, height=20, page=1),
                        ),
                    ],
                    preview_scale=2,
                )

        enricher = DirectionalFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(
                field_id="f1", label="f1",
                x=0.169, y=0.238, width=0.25, height=0.024, page=1,
            ),
        )
        result = enricher._enrich_fields_directionally("doc1", fields)
        assert len(result[0].label_candidates) == 1
        assert result[0].label_candidates[0].text == "Name"

    def test_handles_extract_text_blocks_failure(self):
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                raise RuntimeError("PDF parsing failed")

        enricher = DirectionalFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = enricher._enrich_fields_directionally("doc1", fields)
        assert result is fields  # returns original on error

    def test_handles_get_acroform_fields_failure(self):
        """Enrichment gracefully degrades when AcroForm extraction fails."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [{"text": "Label", "page": 1, "bbox": [100, 200, 50, 12]}]

            def get_acroform_fields(self, doc_id):
                raise RuntimeError("AcroForm extraction failed")

        enricher = DirectionalFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = enricher._enrich_fields_directionally("doc1", fields)
        # No raw_bbox_map entries, so fields are returned without enrichment
        assert result[0].label_candidates == ()

    def test_handles_get_acroform_fields_returns_none(self):
        """Enrichment handles None response from get_acroform_fields."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [{"text": "Label", "page": 1, "bbox": [100, 200, 50, 12]}]

            def get_acroform_fields(self, doc_id):
                return None

        enricher = DirectionalFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(field_id="f1", label="f1", x=100, y=200),
        )
        result = enricher._enrich_fields_directionally("doc1", fields)
        assert result[0].label_candidates == ()

    def test_directional_enrichment_finds_above_label(self):
        """Regression test: directional matching finds labels above fields."""
        class FakeDocService:
            def extract_text_blocks(self, doc_id, pages=None):
                return [
                    # Above: block bottom (180+12=192) < field top (200),
                    # X-center diff within tolerance
                    {"text": "法人名（フリガナ）", "page": 1, "bbox": [102, 180, 148, 12]},
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

        enricher = DirectionalFieldEnricher(document_service=FakeDocService())
        fields = (
            FormFieldSpec(
                field_id="Text1", label="Text1",
                x=0.169, y=0.238, width=0.337, height=0.024, page=1,
            ),
        )
        result = enricher._enrich_fields_directionally("doc1", fields)
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
