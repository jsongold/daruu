"""Tests for the Prompt V2-backed LLM field enricher helpers."""

import pytest

from app.domain.models.form_context import FormFieldSpec
from app.models.acroform import AcroFormFieldInfo, AcroFormFieldsResponse, PageDimensions
from app.models.common import BBox
from app.services.form_context.enricher import LLMFieldEnricher, _build_fields_with_candidates


def test_build_fields_with_candidates_uses_ivb_coords_and_directional_scores():
    fields = [
        FormFieldSpec(field_id="Text1", label="Name", field_type="text", page=1),
    ]
    page_blocks = [
        {"text": "氏名", "page": 1, "bbox": [90, 198, 40, 12]},
        {"text": "住所", "page": 1, "bbox": [300, 198, 40, 12]},
    ]
    raw_bbox_map = {
        "Text1": {"x": 150.0, "y": 200.0, "width": 120.0, "height": 20.0, "page": 1},
    }

    result = _build_fields_with_candidates(fields, page_blocks, raw_bbox_map)

    assert len(result) == 1
    field = result[0]
    assert field.field_id == "Text1"
    assert field.bbox_ivb[0] < field.bbox_ivb[2]
    assert field.bbox_ivb[1] < field.bbox_ivb[3]
    assert [candidate.text for candidate in field.candidates] == ["氏名", "住所"]
    assert field.candidates[0].direction == "left"
    assert field.candidates[1].direction == "right"


def test_build_fields_with_candidates_skips_fields_missing_raw_bbox():
    fields = [
        FormFieldSpec(field_id="Text1", label="Name", field_type="text", page=1),
    ]

    result = _build_fields_with_candidates(fields, [], {})

    assert result == []


@pytest.mark.asyncio
async def test_llm_field_enricher_stores_prompt_attempt():
    class FakeDocService:
        def get_acroform_fields(self, doc_id):
            return AcroFormFieldsResponse(
                has_acroform=True,
                page_dimensions=[PageDimensions(page=1, width=595, height=842)],
                fields=[
                    AcroFormFieldInfo(
                        field_name="Text1",
                        field_type="text",
                        bbox=BBox(x=150, y=200, width=120, height=20, page=1),
                    ),
                ],
                preview_scale=2,
            )

        def extract_text_blocks_for_page(self, doc_id, page):
            return [{"text": "氏名", "page": 1, "bbox": [90, 198, 40, 12]}]

    class FakeLLMClient:
        model = "gpt-test"

        async def complete(self, messages):
            class Response:
                content = (
                    '[{"field_id":"Text1","label":"氏名",'
                    '"semantic_key":"applicant_name","confidence":88}]'
                )

            return Response()

    class FakePromptAttemptRepo:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return None

    repo = FakePromptAttemptRepo()
    enricher = LLMFieldEnricher(
        llm_client=FakeLLMClient(),
        document_service=FakeDocService(),
        prompt_attempt_repo=repo,
    )

    fields = (FormFieldSpec(field_id="Text1", label="Text1", field_type="text", page=1),)
    result = await enricher.enrich("doc-1", "conv-1", fields)

    assert result[0].label_candidates[0].text == "氏名"
    assert len(repo.calls) == 1
    assert repo.calls[0]["conversation_id"] == "conv-1"
    assert repo.calls[0]["document_id"] == "doc-1"
    assert repo.calls[0]["metadata"]["kind"] == "field_enrichment_v2"
