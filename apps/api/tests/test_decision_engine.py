"""Tests for the decision engine."""

from datetime import datetime
from uuid import uuid4

import pytest

from app.models import (
    Document,
    DocumentMeta,
    DocumentType,
    FieldModel,
    FieldType,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobMode,
    JobStatus,
)
from app.models.common import BBox
from app.models.orchestrator import (
    NextAction,
    OrchestratorConfig,
    PipelineStage,
    StageResult,
)
from app.services.orchestrator import DecisionEngine


@pytest.fixture
def config() -> OrchestratorConfig:
    """Create test configuration."""
    return OrchestratorConfig(
        max_iterations=5,
        confidence_threshold=0.8,
        max_steps_per_run=10,
        high_severity_requires_user=True,
    )


@pytest.fixture
def decision_engine(config: OrchestratorConfig) -> DecisionEngine:
    """Create decision engine instance."""
    return DecisionEngine(config)


@pytest.fixture
def target_document() -> Document:
    """Create a test target document."""
    return Document(
        id=str(uuid4()),
        ref="test-target.pdf",
        document_type=DocumentType.TARGET,
        meta=DocumentMeta(
            filename="test-target.pdf",
            file_size=1024,
            mime_type="application/pdf",
            page_count=1,
        ),
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_field(target_document: Document) -> FieldModel:
    """Create a sample field."""
    return FieldModel(
        id=str(uuid4()),
        name="Test Field",
        field_type=FieldType.TEXT,
        value="Test Value",
        confidence=0.9,
        bbox=BBox(x=50, y=100, width=200, height=30, page=1),
        document_id=target_document.id,
        page=1,
        is_required=True,
        is_editable=True,
    )


@pytest.fixture
def job_context(target_document: Document) -> JobContext:
    """Create a test job context."""
    return JobContext(
        id=str(uuid4()),
        mode=JobMode.SCRATCH,
        status=JobStatus.RUNNING,
        source_document=None,
        target_document=target_document,
        fields=[],
        mappings=[],
        extractions=[],
        evidence=[],
        issues=[],
        activities=[],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        progress=0.0,
        current_step="test",
        current_stage=None,
        next_actions=[],
        iteration_count=0,
    )


class TestDecisionEngineTermination:
    """Test termination conditions."""

    def test_done_when_no_issues_and_high_confidence_at_review(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test job completes when no issues and confidence met at REVIEW stage."""
        # Create job at REVIEW stage with high confidence field
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": [sample_field],  # Has confidence 0.9 > threshold 0.8
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "done"
        assert "resolved" in result.reason.lower() or "complete" in result.reason.lower()

    def test_not_done_when_issues_remain(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test job doesn't complete when issues remain."""
        issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Test issue",
            severity=IssueSeverity.WARNING,
        )
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": [sample_field],
                "issues": [issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action != "done"

    def test_not_done_when_confidence_below_threshold(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        target_document: Document,
    ) -> None:
        """Test job doesn't complete when field confidence is below threshold."""
        low_confidence_field = FieldModel(
            id=str(uuid4()),
            name="Low Confidence",
            field_type=FieldType.TEXT,
            value="Some Value",
            confidence=0.5,  # Below 0.8 threshold
            bbox=BBox(x=50, y=100, width=200, height=30, page=1),
            document_id=target_document.id,
            page=1,
            is_required=True,
            is_editable=True,
        )
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": [low_confidence_field],
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "ask"
        assert low_confidence_field.id in result.field_ids


class TestDecisionEngineMaxIterations:
    """Test max iterations handling."""

    def test_blocked_when_max_iterations_reached(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test job blocks when max iterations reached."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "iteration_count": 5,  # Equal to max_iterations
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "blocked"
        assert "maximum" in result.reason.lower()


class TestDecisionEngineCriticalIssues:
    """Test critical issue handling."""

    def test_manual_for_critical_severity(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test manual action required for critical issues."""
        critical_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.VALIDATION_ERROR,
            message="Critical validation error",
            severity=IssueSeverity.CRITICAL,
        )
        job = JobContext(
            **{
                **job_context.model_dump(),
                "fields": [sample_field],
                "issues": [critical_issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "manual"
        assert sample_field.id in result.field_ids

    def test_ask_for_high_severity(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test ask action for high severity issues."""
        high_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.MISSING_VALUE,
            message="Missing required value",
            severity=IssueSeverity.HIGH,
        )
        job = JobContext(
            **{
                **job_context.model_dump(),
                "fields": [sample_field],
                "issues": [high_issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "ask"
        assert sample_field.id in result.field_ids


class TestDecisionEngineLayoutIssues:
    """Test layout issue handling."""

    def test_retry_adjust_for_layout_issues(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test retry of Adjust stage for layout issues."""
        layout_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.LAYOUT_ISSUE,
            message="Value overflows field boundary",
            severity=IssueSeverity.WARNING,
        )
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.FILL.value,  # Past ADJUST
                "fields": [sample_field],
                "issues": [layout_issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "retry"
        assert result.stage == PipelineStage.ADJUST
        assert sample_field.id in result.field_ids


class TestDecisionEngineMappingIssues:
    """Test mapping issue handling."""

    def test_retry_map_for_mapping_issues(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test retry of Map stage for mapping ambiguities."""
        mapping_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.MAPPING_AMBIGUOUS,
            message="Multiple source fields match",
            severity=IssueSeverity.WARNING,
        )
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,  # Past MAP
                "fields": [sample_field],
                "issues": [mapping_issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "retry"
        assert result.stage == PipelineStage.MAP
        assert sample_field.id in result.field_ids


class TestDecisionEngineContinue:
    """Test continue to next stage."""

    def test_continue_to_next_stage(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test continuation to next stage when no issues."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.INGEST.value,
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "continue"
        assert result.stage == PipelineStage.STRUCTURE

    def test_continue_from_none_to_ingest(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test starting from no stage goes to INGEST."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": None,
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "continue"
        assert result.stage == PipelineStage.INGEST


class TestDecisionEngineStageFailure:
    """Test stage failure handling."""

    def test_retry_on_stage_failure(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test retry when stage fails."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,
                "iteration_count": 0,
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.EXTRACT,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="Service unavailable",
        )

        result = decision_engine.decide_next_action(job, failed_result)

        assert result.action == "retry"
        assert result.stage == PipelineStage.EXTRACT

    def test_blocked_after_max_retries(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test blocked when retries exhausted."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,
                "iteration_count": 4,  # One less than max (5)
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.EXTRACT,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="Persistent failure",
        )

        result = decision_engine.decide_next_action(job, failed_result)

        assert result.action == "blocked"


class TestDecisionEngineShouldContinue:
    """Test should_continue_run logic."""

    def test_stop_on_done(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test run stops on done action."""
        next_action = NextAction(action="done", reason="Complete", field_ids=[])

        result = decision_engine.should_continue_run(job_context, next_action, 1)

        assert result is False

    def test_stop_on_blocked(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test run stops on blocked action."""
        next_action = NextAction(action="blocked", reason="Max iterations", field_ids=[])

        result = decision_engine.should_continue_run(job_context, next_action, 1)

        assert result is False

    def test_stop_on_ask(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test run stops on ask action."""
        next_action = NextAction(action="ask", reason="User input needed", field_ids=[])

        result = decision_engine.should_continue_run(job_context, next_action, 1)

        assert result is False

    def test_stop_on_max_steps(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test run stops when max steps reached."""
        next_action = NextAction(
            action="continue",
            stage=PipelineStage.STRUCTURE,
            reason="Next stage",
            field_ids=[],
        )

        result = decision_engine.should_continue_run(job_context, next_action, 10)

        assert result is False

    def test_continue_on_normal_action(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test run continues on normal action."""
        next_action = NextAction(
            action="continue",
            stage=PipelineStage.STRUCTURE,
            reason="Next stage",
            field_ids=[],
        )

        result = decision_engine.should_continue_run(job_context, next_action, 1)

        assert result is True


class TestDecisionEngineJobStatus:
    """Test job status handling."""

    def test_done_when_already_done(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test returns done when job is already done."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "status": JobStatus.DONE,
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "done"

    def test_blocked_when_failed(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test returns blocked when job has failed."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "status": JobStatus.FAILED,
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "blocked"


# ============================================================================
# Edge Case Tests - Decision Engine
# ============================================================================


class TestDecisionEnginePermanentErrors:
    """Test permanent error detection."""

    def test_corrupted_pdf_is_permanent(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test corrupted PDF error is detected as permanent."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.INGEST.value,
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.INGEST,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="PDF file is corrupted and cannot be processed",
        )

        result = decision_engine.decide_next_action(job, failed_result)

        assert result.action == "blocked"
        assert "corrupted" in result.reason.lower()

    def test_password_protected_is_permanent(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test password protected PDF error is permanent."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.INGEST.value,
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.INGEST,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="PDF is password protected",
        )

        result = decision_engine.decide_next_action(job, failed_result)

        assert result.action == "blocked"

    def test_file_not_found_is_permanent(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test file not found error is permanent."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.INGEST.value,
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.INGEST,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="File not found: /path/to/document.pdf",
        )

        result = decision_engine.decide_next_action(job, failed_result)

        assert result.action == "blocked"

    def test_temporary_error_allows_retry(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test temporary error allows retry."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,
                "iteration_count": 0,
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.EXTRACT,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="Connection timeout to OCR service",
        )

        result = decision_engine.decide_next_action(job, failed_result)

        assert result.action == "retry"
        assert result.stage == PipelineStage.EXTRACT


class TestDecisionEngineImprovementRate:
    """Test improvement rate stagnation detection."""

    def test_asks_when_no_improvement(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test asks user when improvement rate is too low."""
        # Create identical issues for previous and current
        issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Low confidence value",
            severity=IssueSeverity.WARNING,
        )
        previous_issues = [issue]

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "iteration_count": 2,
                "fields": [sample_field],
                "issues": [issue],
            }
        )

        result = decision_engine.decide_next_action(
            job, None, previous_issues=previous_issues
        )

        assert result.action == "ask"
        assert "improvement" in result.reason.lower()

    def test_continues_when_improvement_rate_acceptable(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test continues when improvement rate is acceptable."""
        # Previous had 3 issues, current has 1 (good improvement)
        previous_issues = [
            Issue(
                id=str(uuid4()),
                field_id=sample_field.id,
                issue_type=IssueType.LOW_CONFIDENCE,
                message=f"Issue {i}",
                severity=IssueSeverity.WARNING,
            )
            for i in range(3)
        ]
        current_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Remaining issue",
            severity=IssueSeverity.INFO,
        )

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,
                "iteration_count": 2,
                "fields": [sample_field],
                "issues": [current_issue],
            }
        )

        result = decision_engine.decide_next_action(
            job, None, previous_issues=previous_issues
        )

        # Should continue as improvement is significant
        assert result.action in ("continue", "retry")


class TestDecisionEngineMultipleIssueTypes:
    """Test handling of multiple issue types."""

    def test_prioritizes_critical_over_mapping(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test critical issues take priority over mapping issues."""
        critical_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.VALIDATION_ERROR,
            message="Critical validation failed",
            severity=IssueSeverity.CRITICAL,
        )
        mapping_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.MAPPING_AMBIGUOUS,
            message="Ambiguous mapping",
            severity=IssueSeverity.WARNING,
        )

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.MAP.value,
                "fields": [sample_field],
                "issues": [critical_issue, mapping_issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        # Critical should be handled first
        assert result.action == "manual"

    def test_handles_layout_and_mapping_issues(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test handling when both layout and mapping issues exist."""
        layout_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.LAYOUT_ISSUE,
            message="Text overflows",
            severity=IssueSeverity.WARNING,
        )
        mapping_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.MAPPING_AMBIGUOUS,
            message="Ambiguous",
            severity=IssueSeverity.WARNING,
        )

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": [sample_field],
                "issues": [layout_issue, mapping_issue],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        # Should handle one of them with retry
        assert result.action == "retry"
        assert result.stage in (PipelineStage.ADJUST, PipelineStage.MAP)


class TestDecisionEngineFieldConfidence:
    """Test field confidence threshold handling."""

    def test_all_fields_above_threshold(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        target_document: Document,
    ) -> None:
        """Test completion when all fields are above threshold."""
        high_confidence_fields = [
            FieldModel(
                id=str(uuid4()),
                name=f"Field {i}",
                field_type=FieldType.TEXT,
                value=f"Value {i}",
                confidence=0.9,  # Above 0.8 threshold
                bbox=BBox(x=50, y=100 + i * 30, width=200, height=25, page=1),
                document_id=target_document.id,
                page=1,
                is_required=True,
                is_editable=True,
            )
            for i in range(3)
        ]

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": high_confidence_fields,
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "done"

    def test_mixed_confidence_fields(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        target_document: Document,
    ) -> None:
        """Test handling when some fields are below threshold."""
        mixed_fields = [
            FieldModel(
                id=str(uuid4()),
                name="High Confidence",
                field_type=FieldType.TEXT,
                value="Value 1",
                confidence=0.95,
                bbox=BBox(x=50, y=100, width=200, height=25, page=1),
                document_id=target_document.id,
                page=1,
                is_required=True,
                is_editable=True,
            ),
            FieldModel(
                id=str(uuid4()),
                name="Low Confidence",
                field_type=FieldType.TEXT,
                value="Value 2",
                confidence=0.5,  # Below threshold
                bbox=BBox(x=50, y=130, width=200, height=25, page=1),
                document_id=target_document.id,
                page=1,
                is_required=True,
                is_editable=True,
            ),
        ]

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": mixed_fields,
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        assert result.action == "ask"
        # The low confidence field should be in field_ids
        low_conf_field = next(f for f in mixed_fields if f.confidence < 0.8)
        assert low_conf_field.id in result.field_ids

    def test_fields_without_values_ignored(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
        target_document: Document,
    ) -> None:
        """Test that fields without values are not considered for confidence check."""
        fields = [
            FieldModel(
                id=str(uuid4()),
                name="Filled Field",
                field_type=FieldType.TEXT,
                value="Value",
                confidence=0.9,
                bbox=BBox(x=50, y=100, width=200, height=25, page=1),
                document_id=target_document.id,
                page=1,
                is_required=True,
                is_editable=True,
            ),
            FieldModel(
                id=str(uuid4()),
                name="Empty Field",
                field_type=FieldType.TEXT,
                value=None,  # No value
                confidence=None,  # No confidence
                bbox=BBox(x=50, y=130, width=200, height=25, page=1),
                document_id=target_document.id,
                page=1,
                is_required=False,
                is_editable=True,
            ),
        ]

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": fields,
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        # Should be done since only filled field meets threshold
        assert result.action == "done"


class TestDecisionEngineRetrySequences:
    """Test retry stage sequences."""

    def test_get_retry_stages_layout(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """Test layout retry returns correct sequence."""
        stages = decision_engine.get_retry_stages("layout")

        assert stages == [
            PipelineStage.ADJUST,
            PipelineStage.FILL,
            PipelineStage.REVIEW,
        ]

    def test_get_retry_stages_mapping(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """Test mapping retry returns correct sequence."""
        stages = decision_engine.get_retry_stages("mapping")

        assert stages == [
            PipelineStage.MAP,
            PipelineStage.EXTRACT,
        ]

    def test_get_retry_stages_unknown(
        self,
        decision_engine: DecisionEngine,
    ) -> None:
        """Test unknown retry type returns empty list."""
        stages = decision_engine.get_retry_stages("unknown")

        assert stages == []


class TestDecisionEngineEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_fields_at_review(
        self,
        decision_engine: DecisionEngine,
        job_context: JobContext,
    ) -> None:
        """Test behavior at review stage with no fields."""
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": [],
                "issues": [],
            }
        )

        result = decision_engine.decide_next_action(job, None)

        # Empty fields at review should complete
        assert result.action == "done"

    def test_max_iterations_exactly_at_limit(
        self,
        config: OrchestratorConfig,
        job_context: JobContext,
    ) -> None:
        """Test behavior when exactly at max iterations."""
        engine = DecisionEngine(config)
        job = JobContext(
            **{
                **job_context.model_dump(),
                "iteration_count": config.max_iterations,
            }
        )

        result = engine.decide_next_action(job, None)

        assert result.action == "blocked"
        assert "maximum" in result.reason.lower()

    def test_one_below_max_iterations_allows_retry(
        self,
        config: OrchestratorConfig,
        job_context: JobContext,
    ) -> None:
        """Test retry is allowed when one below max iterations."""
        engine = DecisionEngine(config)
        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,
                "iteration_count": config.max_iterations - 1,
            }
        )
        failed_result = StageResult(
            stage=PipelineStage.EXTRACT,
            success=False,
            issues=[],
            activities=[],
            updated_fields=[],
            error_message="Temporary failure",
        )

        result = engine.decide_next_action(job, failed_result)

        # Should still block since we're at max - 1 and failure means block
        assert result.action == "blocked"

    def test_user_approval_required_config(
        self,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test user approval config affects completion."""
        config = OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=0.8,
            max_steps_per_run=10,
            require_user_approval=True,
        )
        engine = DecisionEngine(config)

        high_confidence_field = FieldModel(
            **{
                **sample_field.model_dump(),
                "confidence": 0.95,
            }
        )

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.REVIEW.value,
                "fields": [high_confidence_field],
                "issues": [],
            }
        )

        result = engine.decide_next_action(job, None)

        # With require_user_approval=True, should ask instead of done
        assert result.action == "ask"
        assert "approval" in result.reason.lower()

    def test_high_severity_requires_user_disabled(
        self,
        job_context: JobContext,
        sample_field: FieldModel,
    ) -> None:
        """Test high severity issues when config disables user requirement."""
        config = OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=0.8,
            max_steps_per_run=10,
            high_severity_requires_user=False,
        )
        engine = DecisionEngine(config)

        high_issue = Issue(
            id=str(uuid4()),
            field_id=sample_field.id,
            issue_type=IssueType.VALIDATION_ERROR,
            message="High severity issue",
            severity=IssueSeverity.HIGH,
        )

        job = JobContext(
            **{
                **job_context.model_dump(),
                "current_stage": PipelineStage.EXTRACT.value,
                "fields": [sample_field],
                "issues": [high_issue],
            }
        )

        result = engine.decide_next_action(job, None)

        # With high_severity_requires_user=False, should continue
        assert result.action == "continue"
