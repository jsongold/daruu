"""Decide Next use case.

This use case encapsulates the decision logic for determining
the next action in the pipeline based on job state and stage results.
"""

from dataclasses import dataclass
from typing import Sequence

from app.models import Issue, IssueSeverity, IssueType, JobContext, JobStatus
from app.models.orchestrator import (
    NextAction,
    OrchestratorConfig,
    PipelineStage,
    StageResult,
    get_next_stage,
)
from app.orchestrator.domain.rules import (
    calculate_improvement_rate,
)


@dataclass(frozen=True)
class DecisionContext:
    """Context for making a decision.

    Contains all information needed to decide the next action.
    """

    job: JobContext
    stage_result: StageResult | None
    previous_issues: list[Issue] | None


class DecideNextUseCase:
    """Use case for deciding the next pipeline action.

    This use case encapsulates the decision tree for:
    - When to continue to the next stage
    - When to retry a stage
    - When to ask for user input
    - When to mark as blocked or done

    The decision logic considers:
    - Issue count and severity
    - Confidence thresholds
    - Iteration limits
    - Improvement rates
    - Stage-specific retry logic
    """

    def __init__(self, config: OrchestratorConfig) -> None:
        """Initialize the use case.

        Args:
            config: Orchestrator configuration with thresholds.
        """
        self._config = config

    def execute(self, context: DecisionContext) -> NextAction:
        """Decide the next action based on context.

        Decision tree:
        1. Check if job is already done or failed
        2. Check max iterations (prevent infinite loops)
        3. Check stage failure
        4. Check termination condition (no issues, confidence met)
        5. Check critical issues (require user intervention)
        6. Check improvement rate (detect stagnation)
        7. Check low confidence (require verification)
        8. Check layout issues (retry Adjust)
        9. Check mapping issues (retry Map)
        10. Continue to next stage

        Args:
            context: Decision context with job, stage result, and history.

        Returns:
            NextAction indicating what to do next.
        """
        job = context.job
        stage_result = context.stage_result
        previous_issues = context.previous_issues

        current_stage = self._get_current_stage(job)

        # 1. Already done or failed
        if job.status == JobStatus.DONE:
            return NextAction(
                action="done",
                reason="Job is already complete",
                field_ids=[],
            )

        if job.status == JobStatus.FAILED:
            return NextAction(
                action="blocked",
                reason="Job has failed",
                field_ids=[],
            )

        # 2. Max iterations
        if job.iteration_count >= self._config.max_iterations:
            return NextAction(
                action="blocked",
                reason=f"Maximum iterations ({self._config.max_iterations}) reached",
                field_ids=self._get_issue_field_ids(job.issues),
            )

        # 3. Stage failure
        if stage_result is not None and not stage_result.success:
            return self._handle_stage_failure(job, stage_result)

        # 4. Termination condition (successful completion)
        termination_result = self._check_termination(job, current_stage)
        if termination_result is not None:
            return termination_result

        # 5. Critical issues
        critical_result = self._check_critical_issues(job)
        if critical_result is not None:
            return critical_result

        # 6. Improvement rate check (stagnation detection)
        if previous_issues is not None and job.iteration_count > 0:
            improvement_result = self._check_improvement_rate(job, previous_issues)
            if improvement_result is not None:
                return improvement_result

        # 7. Low confidence
        confidence_result = self._check_confidence(job)
        if confidence_result is not None:
            return confidence_result

        # 8. Layout issues (retry Adjust)
        layout_result = self._check_layout_issues(job, current_stage)
        if layout_result is not None:
            return layout_result

        # 9. Mapping issues (retry Map)
        mapping_result = self._check_mapping_issues(job, current_stage)
        if mapping_result is not None:
            return mapping_result

        # 10. Continue to next stage
        return self._continue_to_next_stage(current_stage)

    def _get_current_stage(self, job: JobContext) -> PipelineStage | None:
        """Get current pipeline stage from job context."""
        if job.current_stage is None:
            return None
        try:
            return PipelineStage(job.current_stage)
        except ValueError:
            return None

    def _check_termination(
        self,
        job: JobContext,
        current_stage: PipelineStage | None,
    ) -> NextAction | None:
        """Check if job meets termination conditions."""
        # Must be at REVIEW stage
        if current_stage != PipelineStage.REVIEW:
            return None

        # Check for any issues
        if job.issues:
            return None

        # Check confidence threshold
        if not self._all_fields_meet_confidence(job):
            return None

        # Check if user approval is required
        if self._config.require_user_approval:
            return NextAction(
                action="ask",
                reason="User approval required before completion",
                field_ids=[],
            )

        return NextAction(
            action="done",
            reason="All issues resolved and confidence threshold met",
            field_ids=[],
        )

    def _all_fields_meet_confidence(self, job: JobContext) -> bool:
        """Check if all fields meet confidence threshold."""
        for field in job.fields:
            if field.value is not None and field.confidence is not None:
                if field.confidence < self._config.confidence_threshold:
                    return False
        return True

    def _check_critical_issues(self, job: JobContext) -> NextAction | None:
        """Check for critical or high severity issues."""
        if not self._config.high_severity_requires_user:
            return None

        critical_issues = [
            issue
            for issue in job.issues
            if issue.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.ERROR)
        ]

        if not critical_issues:
            return None

        field_ids = [issue.field_id for issue in critical_issues]
        first_issue = critical_issues[0]

        if first_issue.severity == IssueSeverity.CRITICAL:
            return NextAction(
                action="manual",
                reason=f"Critical issue requires manual intervention: {first_issue.message}",
                field_ids=field_ids,
            )

        return NextAction(
            action="ask",
            reason=f"High severity issue requires user input: {first_issue.message}",
            field_ids=field_ids,
        )

    def _check_improvement_rate(
        self,
        job: JobContext,
        previous_issues: list[Issue],
    ) -> NextAction | None:
        """Check if improvement rate is below threshold."""
        improvement = calculate_improvement_rate(
            previous_issues,
            list(job.issues),
        )

        if improvement < self._config.min_improvement_rate:
            return NextAction(
                action="ask",
                reason=f"Improvement rate too low: {improvement:.2%}",
                field_ids=[issue.field_id for issue in job.issues if issue.field_id],
            )

        return None

    def _check_confidence(self, job: JobContext) -> NextAction | None:
        """Check for low confidence fields."""
        low_confidence_fields = []

        for field in job.fields:
            if field.value is not None and field.confidence is not None:
                if field.confidence < self._config.confidence_threshold:
                    low_confidence_fields.append(field.id)

        if not low_confidence_fields:
            return None

        return NextAction(
            action="ask",
            reason=f"Fields with confidence below threshold ({self._config.confidence_threshold})",
            field_ids=low_confidence_fields,
        )

    def _check_layout_issues(
        self,
        job: JobContext,
        current_stage: PipelineStage | None,
    ) -> NextAction | None:
        """Check for layout issues requiring Adjust retry."""
        layout_issues = [
            issue for issue in job.issues if issue.issue_type == IssueType.LAYOUT_ISSUE
        ]

        if not layout_issues:
            return None

        # Only retry if past ADJUST stage
        if current_stage in (
            PipelineStage.ADJUST,
            PipelineStage.FILL,
            PipelineStage.REVIEW,
        ):
            field_ids = [issue.field_id for issue in layout_issues]
            return NextAction(
                action="retry",
                stage=PipelineStage.ADJUST,
                reason="Layout issues detected (overflow/overlap), retrying Adjust stage",
                field_ids=field_ids,
            )

        return None

    def _check_mapping_issues(
        self,
        job: JobContext,
        current_stage: PipelineStage | None,
    ) -> NextAction | None:
        """Check for mapping issues requiring Map retry."""
        mapping_issues = [
            issue for issue in job.issues if issue.issue_type == IssueType.MAPPING_AMBIGUOUS
        ]

        if not mapping_issues:
            return None

        # Only retry if past MAP stage
        if current_stage in (
            PipelineStage.EXTRACT,
            PipelineStage.ADJUST,
            PipelineStage.FILL,
            PipelineStage.REVIEW,
        ):
            field_ids = [issue.field_id for issue in mapping_issues]
            return NextAction(
                action="retry",
                stage=PipelineStage.MAP,
                reason="Mapping ambiguities detected, retrying Map stage with additional evidence",
                field_ids=field_ids,
            )

        return None

    def _handle_stage_failure(
        self,
        job: JobContext,
        stage_result: StageResult,
    ) -> NextAction:
        """Handle a failed stage execution."""
        error_msg = stage_result.error_message or "Unknown error"

        # Check if this is a permanent error that shouldn't be retried
        if self._is_permanent_error(error_msg):
            return NextAction(
                action="blocked",
                reason=f"Stage {stage_result.stage.value} failed with permanent error: {error_msg}",
                field_ids=self._get_issue_field_ids(stage_result.issues),
            )

        if job.iteration_count < self._config.max_iterations - 1:
            return NextAction(
                action="retry",
                stage=stage_result.stage,
                reason=f"Stage {stage_result.stage.value} failed: {error_msg}",
                field_ids=self._get_issue_field_ids(stage_result.issues),
            )

        return NextAction(
            action="blocked",
            reason=f"Stage {stage_result.stage.value} failed after max retries: {error_msg}",
            field_ids=self._get_issue_field_ids(stage_result.issues),
        )

    def _is_permanent_error(self, error_message: str) -> bool:
        """Check if an error is permanent and should not be retried.

        Permanent errors are those that won't be resolved by retrying:
        - Corrupted or invalid PDF files
        - Missing required files
        - Invalid file formats
        - Authentication/authorization errors

        Args:
            error_message: The error message to check.

        Returns:
            True if the error is permanent and should not be retried.
        """
        error_lower = error_message.lower()

        # PDF corruption/invalidity errors
        permanent_indicators = [
            "corrupted",
            "corrupt",
            "invalid pdf",
            "not a valid pdf",
            "missing root object",
            "no /root object",
            "pdf file is corrupted",
            "pdf file is invalid",
            "cannot open pdf",
            "pdf is password protected",
            "file not found",
            "file does not exist",
            "invalid file format",
            "unsupported format",
            "authentication failed",
            "unauthorized",
            "forbidden",
            "permission denied",
        ]

        return any(indicator in error_lower for indicator in permanent_indicators)

    def _continue_to_next_stage(
        self,
        current_stage: PipelineStage | None,
    ) -> NextAction:
        """Continue to the next stage in the pipeline."""
        next_stage = get_next_stage(current_stage)

        if next_stage is None:
            return NextAction(
                action="continue",
                stage=PipelineStage.REVIEW,
                reason="Pipeline complete, proceeding to final review",
                field_ids=[],
            )

        return NextAction(
            action="continue",
            stage=next_stage,
            reason=f"Proceeding to {next_stage.value} stage",
            field_ids=[],
        )

    def _get_issue_field_ids(self, issues: Sequence[Issue]) -> list[str]:
        """Extract field IDs from issues."""
        return [issue.field_id for issue in issues]
