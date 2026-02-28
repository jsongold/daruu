"""Protocol compliance tests for the To-Be autofill architecture.

Verifies that all service implementations satisfy their
corresponding Protocol interfaces at runtime using isinstance().
"""

import pytest

from app.domain.protocols import (
    CorrectionTrackerProtocol,
    FillPlannerProtocol,
    FormContextBuilderProtocol,
    FormRendererProtocol,
    RuleAnalyzerProtocol,
)
from app.services.correction_tracker import CorrectionTrackerStub
from app.services.fill_planner import FillPlanner
from app.services.form_context import FormContextBuilder
from app.services.form_renderer import FormRenderer
from app.services.rule_analyzer import RuleAnalyzerStub


# ============================================================================
# Fixtures
# ============================================================================


class _FakeDataSourceRepo:
    """Minimal fake for DataSourceRepository."""

    def list_by_conversation(self, conversation_id: str):
        return []

    def update_extracted_data(self, source_id, data):
        pass


class _FakeExtractionService:
    """Minimal fake for TextExtractionService."""

    pass


class _FakeEnricher:
    """Minimal fake for FieldEnricher protocol."""

    async def enrich(self, document_id, fields):
        return fields


class _FakeFillService:
    """Minimal fake for FillService."""

    pass


# ============================================================================
# Protocol compliance: isinstance checks
# ============================================================================


class TestFormContextBuilderCompliance:
    """FormContextBuilder must satisfy FormContextBuilderProtocol."""

    def test_isinstance(self) -> None:
        builder = FormContextBuilder(
            data_source_repo=_FakeDataSourceRepo(),
            extraction_service=_FakeExtractionService(),
            enricher=_FakeEnricher(),
        )
        assert isinstance(builder, FormContextBuilderProtocol)

    def test_has_build_method(self) -> None:
        assert hasattr(FormContextBuilder, "build")
        assert callable(getattr(FormContextBuilder, "build"))


class TestFillPlannerCompliance:
    """FillPlanner must satisfy FillPlannerProtocol."""

    def test_isinstance_with_llm(self) -> None:
        planner = FillPlanner(llm_client=object())
        assert isinstance(planner, FillPlannerProtocol)

    def test_isinstance_without_llm(self) -> None:
        planner = FillPlanner(llm_client=None)
        assert isinstance(planner, FillPlannerProtocol)

    def test_has_plan_method(self) -> None:
        assert hasattr(FillPlanner, "plan")
        assert callable(getattr(FillPlanner, "plan"))


class TestFormRendererCompliance:
    """FormRenderer must satisfy FormRendererProtocol."""

    def test_isinstance(self) -> None:
        renderer = FormRenderer(fill_service=_FakeFillService())
        assert isinstance(renderer, FormRendererProtocol)

    def test_has_render_method(self) -> None:
        assert hasattr(FormRenderer, "render")
        assert callable(getattr(FormRenderer, "render"))


class TestRuleAnalyzerStubCompliance:
    """RuleAnalyzerStub must satisfy RuleAnalyzerProtocol."""

    def test_isinstance(self) -> None:
        analyzer = RuleAnalyzerStub()
        assert isinstance(analyzer, RuleAnalyzerProtocol)

    def test_has_analyze_method(self) -> None:
        assert hasattr(RuleAnalyzerStub, "analyze")
        assert callable(getattr(RuleAnalyzerStub, "analyze"))


class TestCorrectionTrackerStubCompliance:
    """CorrectionTrackerStub must satisfy CorrectionTrackerProtocol."""

    def test_isinstance(self) -> None:
        tracker = CorrectionTrackerStub()
        assert isinstance(tracker, CorrectionTrackerProtocol)

    def test_has_record_method(self) -> None:
        assert hasattr(CorrectionTrackerStub, "record")
        assert callable(getattr(CorrectionTrackerStub, "record"))

    def test_has_list_corrections_method(self) -> None:
        assert hasattr(CorrectionTrackerStub, "list_corrections")
        assert callable(getattr(CorrectionTrackerStub, "list_corrections"))


# ============================================================================
# Stub behavior tests
# ============================================================================


class TestRuleAnalyzerStubBehavior:
    """RuleAnalyzerStub should return empty list."""

    @pytest.mark.asyncio
    async def test_analyze_returns_empty(self) -> None:
        analyzer = RuleAnalyzerStub()
        result = await analyzer.analyze(rule_docs=("doc1",))
        assert result == []


class TestCorrectionTrackerStubBehavior:
    """CorrectionTrackerStub should be no-op."""

    @pytest.mark.asyncio
    async def test_record_is_noop(self) -> None:
        from app.domain.models.correction_record import (
            CorrectionCategory,
            CorrectionRecord,
        )

        tracker = CorrectionTrackerStub()
        record = CorrectionRecord(
            document_id="doc1",
            field_id="field1",
            corrected_value="new_value",
            category=CorrectionCategory.WRONG_VALUE,
        )
        await tracker.record(record)  # Should not raise

    @pytest.mark.asyncio
    async def test_list_corrections_returns_empty(self) -> None:
        tracker = CorrectionTrackerStub()
        result = await tracker.list_corrections("doc1")
        assert result == []


# ============================================================================
# Domain model immutability tests
# ============================================================================


class TestDomainModelImmutability:
    """Domain models should be frozen (immutable)."""

    def test_form_context_frozen(self) -> None:
        from app.domain.models.form_context import FormContext, FormFieldSpec

        ctx = FormContext(
            document_id="doc1",
            conversation_id="conv1",
            fields=(FormFieldSpec(field_id="f1", label="Name"),),
        )
        with pytest.raises(Exception):
            ctx.document_id = "changed"

    def test_fill_plan_frozen(self) -> None:
        from app.domain.models.fill_plan import (
            FieldFillAction,
            FillActionType,
            FillPlan,
        )

        plan = FillPlan(
            document_id="doc1",
            actions=(
                FieldFillAction(
                    field_id="f1",
                    action=FillActionType.FILL,
                    value="test",
                ),
            ),
        )
        with pytest.raises(Exception):
            plan.document_id = "changed"

    def test_render_report_frozen(self) -> None:
        from app.domain.models.render_report import RenderReport

        report = RenderReport(success=True)
        with pytest.raises(Exception):
            report.success = False
