"""Tests for selecting the autofill field enricher from configuration."""

from types import SimpleNamespace

from app.routes import autofill_pipeline
from app.services.form_context import DirectionalFieldEnricher, LLMFieldEnricher


class _DummyRepo:
    pass


class _DummyDocumentService:
    pass


class _DummyExtractionService:
    pass


def _build_service_with_enricher(field_enricher: str, llm_client: object | None):
    autofill_pipeline._pipeline_service = None

    autofill_pipeline.get_settings = lambda: SimpleNamespace(field_enricher=field_enricher)
    autofill_pipeline.get_prompt_attempt_repository = lambda: object()

    import app.services.llm as llm_module

    original_get_llm_client = llm_module.get_llm_client
    llm_module.get_llm_client = lambda: llm_client
    try:
        return autofill_pipeline.get_pipeline_service(
            data_source_repo=_DummyRepo(),
            extraction_service=_DummyExtractionService(),
            document_service=_DummyDocumentService(),
        )
    finally:
        llm_module.get_llm_client = original_get_llm_client
        autofill_pipeline._pipeline_service = None


def test_uses_llm_v2_enricher_when_configured_and_llm_available():
    service = _build_service_with_enricher("llm_v2", object())
    assert isinstance(service._context_builder._enricher, LLMFieldEnricher)


def test_falls_back_to_directional_when_llm_v2_but_no_llm_client():
    service = _build_service_with_enricher("llm_v2", None)
    assert isinstance(service._context_builder._enricher, DirectionalFieldEnricher)


def test_uses_directional_by_default():
    service = _build_service_with_enricher("directional", object())
    assert isinstance(service._context_builder._enricher, DirectionalFieldEnricher)
