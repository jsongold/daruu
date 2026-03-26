"""Decision engine for pipeline branching and loop control.

Implements the branching logic from PRD:
- issues.severity >= high OR confidence < threshold -> Ask or Manual (blocked)
- layout_issue (overflow/overlap) -> Re-run Adjust/Fill/Review
- mapping_ambiguous -> Re-run Mapping/Extract
- Termination: Issue == 0 AND confidence >= threshold AND user approval if needed
- Infinite loop prevention: max_iterations, improvement rate threshold
"""

from typing import Sequence

from app.models import (
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobStatus,
)
from app.models.orchestrator import (
    ACROFORM_SCRATCH_SKIP_STAGES,
    ACROFORM_TRANSFER_SKIP_STAGES,
    NextAction,
    OrchestratorConfig,
    PipelineStage,
    StageResult,
    get_next_stage,
)
from app.services.orchestrator.domain.rules import calculate_improvement_rate


class DecisionEngine:
    """Engine for making pipeline control decisions.

    This class encapsulates all decision logic per PRD:
    - Basic sequence: Ingest -> Structure/Labelling -> Mapping -> Extract -> Adjust -> Fill -> Review
    - Branch on issues.severity >= high OR confidence < threshold -> ask/manual (blocked)
    - Branch on layout_issue -> Re-run Adjust/Fill/Review
    - Branch on mapping_ambiguous -> Re-run Mapping/Extract (with additional evidence)
    - Termination: Issue == 0 AND confidence >= threshold (and user approval if needed)
    - Infinite loop prevention: max_iterations, improvement rate threshold
    """

    def __init__(self, config: OrchestratorConfig) -> None:
        """Initialize the decision engine.

        Args:
            config: Configuration for decision thresholds and limits.
        """
        self._config = config
        self._previous_issues: list[Issue] | None = None

    @property
    def config(self) -> OrchestratorConfig:
        """Get the orchestrator configuration."""
        return self._config

    def set_previous_issues(self, issues: list[Issue]) -> None:
        """Set previous issues for improvement rate tracking.

        Call this before decide_next_action when retrying stages
        to enable stagnation detection.

        Args:
            issues: Issues from the previous iteration.
        """
        self._previous_issues = issues

    def clear_previous_issues(self) -> None:
        """Clear previous issues tracking."""
        self._previous_issues = None

    def decide_next_action(
        self,
        job: JobContext,
        stage_result: StageResult | None,
        previous_issues: list[Issue] | None = None,
    ) -> NextAction:
        """Determine the next action based on job state and stage result.

        Decision tree (per PRD):
        1. Check job status (already done/failed) -> done/blocked
        2. Check max iterations -> blocked (infinite loop prevention)
        3. Check stage failure -> retry or blocked
        4. Check termination condition (Issue==0 AND confidence>=threshold) -> done
        5. Check severity>=high issues -> ask/manual (blocked per PRD)
        6. Check improvement rate -> ask (if stagnating)
        7. Check confidence < threshold -> ask
        8. Check layout_issue (overflow/overlap) -> retry Adjust/Fill/Review
        9. Check mapping_ambiguous -> retry Mapping/Extract
        10. Otherwise -> continue to next stage

        Args:
            job: Current job context.
            stage_result: Result from the last executed stage, if any.
            previous_issues: Issues from previous iteration for improvement tracking.

        Returns:
            NextAction indicating what to do next.
        """
        issues_for_comparison = previous_issues or self._previous_issues
        current_stage = self._get_current_stage(job)

        # 1. Check if job is already done or failed
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

        # 2. Check max iterations to prevent infinite loops
        if job.iteration_count >= self._config.max_iterations:
            return NextAction(
                action="blocked",
                reason=f"Maximum iterations ({self._config.max_iterations}) reached",
                field_ids=self._get_issue_field_ids(job.issues),
            )

        # 3. Check for stage failure
        if stage_result is not None and not stage_result.success:
            return self._handle_stage_failure(job, stage_result)

        # 4. Check termination condition (PRD: Issue==0 AND confidence>=threshold)
        termination_result = self._check_termination(job, current_stage)
        if termination_result is not None:
            return termination_result

        # 5. Check for severity >= high issues (PRD: -> ask/manual, blocked)
        severity_result = self._check_high_severity_issues(job)
        if severity_result is not None:
            return severity_result

        # 5.5 Check improvement rate (stagnation detection for infinite loop prevention)
        if issues_for_comparison is not None and job.iteration_count > 0:
            improvement_result = self._check_improvement_rate(job, issues_for_comparison)
            if improvement_result is not None:
                return improvement_result

        # 6. Check for confidence < threshold (PRD: -> ask)
        confidence_result = self._check_low_confidence(job)
        if confidence_result is not None:
            return confidence_result

        # 7. Check for layout issues (PRD: -> retry Adjust/Fill/Review)
        layout_result = self._check_layout_issues(job, current_stage)
        if layout_result is not None:
            return layout_result

        # 8. Check for mapping ambiguous issues (PRD: -> retry Mapping/Extract)
        mapping_result = self._check_mapping_issues(job, current_stage)
        if mapping_result is not None:
            return mapping_result

        # 9. Otherwise continue to next stage
        return self._continue_to_next_stage(job, current_stage)

    def _get_current_stage(self, job: JobContext) -> PipelineStage | None:
        """Get the current pipeline stage from job context."""
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
        """Check if job meets termination conditions.

        PRD Termination: Issue==0 AND confidence>=threshold AND at terminal stage
        Terminal stages vary by configuration:
        - Normal flow: REVIEW
        - AcroForm + TRANSFER: EXTRACT
        - AcroForm + SCRATCH: LABELLING

        If require_user_approval is set, asks for user confirmation first.
        """
        # Determine terminal stage based on AcroForm presence and job mode
        terminal_stage = self._get_terminal_stage(job)

        # Must be at terminal stage to consider termination
        if current_stage != terminal_stage:
            return None

        # Check for any issues (excluding layout issues for AcroForm since those stages are skipped)
        active_issues = job.issues
        if self._job_has_acroform(job):
            active_issues = [
                issue for issue in job.issues if issue.issue_type != IssueType.LAYOUT_ISSUE
            ]

        if active_issues:
            return None

        # Check confidence threshold for all fields
        # Skip confidence check only for SCRATCH + AcroForm (no extraction happens)
        from app.models.job import JobMode

        skip_confidence_check = self._job_has_acroform(job) and job.mode == JobMode.SCRATCH
        if not skip_confidence_check:
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

    def _get_terminal_stage(self, job: JobContext) -> PipelineStage:
        """Determine the terminal stage based on job configuration.

        Returns:
            The stage at which the pipeline should terminate.
        """
        if not self._job_has_acroform(job):
            return PipelineStage.REVIEW

        from app.models.job import JobMode

        if job.mode == JobMode.SCRATCH:
            # SCRATCH + AcroForm: ends at LABELLING
            return PipelineStage.LABELLING
        else:
            # TRANSFER + AcroForm: ends at EXTRACT
            return PipelineStage.EXTRACT

    def _all_fields_meet_confidence(self, job: JobContext) -> bool:
        """Check if all fields meet the confidence threshold."""
        for field in job.fields:
            if field.value is not None and field.confidence is not None:
                if field.confidence < self._config.confidence_threshold:
                    return False
        return True

    def _check_high_severity_issues(self, job: JobContext) -> NextAction | None:
        """Check for severity >= high issues.

        Per PRD: issues.severity >= high -> Ask or Manual (blocked)
        """
        if not self._config.high_severity_requires_user:
            return None

        # Find issues with severity >= high (including CRITICAL, HIGH, ERROR)
        high_severity_issues = [
            issue
            for issue in job.issues
            if issue.severity in (IssueSeverity.CRITICAL, IssueSeverity.HIGH, IssueSeverity.ERROR)
        ]

        if not high_severity_issues:
            return None

        field_ids = [issue.field_id for issue in high_severity_issues]
        first_issue = high_severity_issues[0]

        # CRITICAL issues require manual intervention (blocked)
        if first_issue.severity == IssueSeverity.CRITICAL:
            return NextAction(
                action="manual",
                reason=f"Critical issue requires manual intervention: {first_issue.message}",
                field_ids=field_ids,
            )

        # HIGH/ERROR issues ask for user input (blocked per PRD)
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
        """Check if improvement rate is below threshold.

        Part of infinite loop prevention per PRD.
        If improvement rate is below min_improvement_rate, asks for user input.

        Args:
            job: Current job context.
            previous_issues: Issues from the previous iteration.

        Returns:
            NextAction if improvement is too low, None otherwise.
        """
        improvement = calculate_improvement_rate(
            previous_issues,
            list(job.issues),
        )

        if improvement < self._config.min_improvement_rate:
            return NextAction(
                action="ask",
                reason=f"Improvement rate too low ({improvement:.2%}), unable to resolve automatically",
                field_ids=[issue.field_id for issue in job.issues],
            )

        return None

    def _check_low_confidence(self, job: JobContext) -> NextAction | None:
        """Check for confidence < threshold.

        Per PRD: confidence < threshold -> ask
        """
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
        """Check for layout issues (overflow/overlap).

        Per PRD: layout_issue -> Re-run Adjust/Fill/Review

        Note: When AcroForm is present, layout issues are ignored because
        Adjust/Fill/Review stages are skipped (AcroForm defines the layout).
        """
        # Skip layout issue handling for AcroForm documents
        if self._job_has_acroform(job):
            return None

        layout_issues = [
            issue for issue in job.issues if issue.issue_type == IssueType.LAYOUT_ISSUE
        ]

        if not layout_issues:
            return None

        # Only retry Adjust if we're past the ADJUST stage
        # This prevents infinite loops by only retrying when we've already done Adjust
        if current_stage in (
            PipelineStage.ADJUST,
            PipelineStage.FILL,
            PipelineStage.REVIEW,
        ):
            field_ids = [issue.field_id for issue in layout_issues]
            return NextAction(
                action="retry",
                stage=PipelineStage.ADJUST,
                reason="Layout issues detected (overflow/overlap), re-running Adjust/Fill/Review",
                field_ids=field_ids,
            )

        return None

    def _check_mapping_issues(
        self,
        job: JobContext,
        current_stage: PipelineStage | None,
    ) -> NextAction | None:
        """Check for mapping ambiguous issues.

        Per PRD: mapping_ambiguous -> Re-run Mapping/Extract (with additional evidence/OCR)
        """
        mapping_issues = [
            issue for issue in job.issues if issue.issue_type == IssueType.MAPPING_AMBIGUOUS
        ]

        if not mapping_issues:
            return None

        # Only retry Map if we're past the MAP stage
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
                reason="Mapping ambiguities detected, re-running Mapping/Extract with additional evidence",
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

        # Check if we should retry the same stage (if not at max iterations)
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
        job: JobContext,
        current_stage: PipelineStage | None,
    ) -> NextAction:
        """Continue to the next stage in the pipeline.

        Per PRD sequence: Ingest -> Structure/Labelling -> Mapping -> Extract -> Adjust -> Fill -> Review

        Pipeline variations based on AcroForm and job mode:
        - Normal (no AcroForm): Full pipeline
        - AcroForm + TRANSFER: Skip Adjust/Fill/Review (ends at EXTRACT)
        - AcroForm + SCRATCH: Skip Map/Extract/Adjust/Fill/Review (ends at LABELLING)
        """
        # Determine stages to skip based on AcroForm presence and job mode
        skip_stages = self._get_skip_stages(job)

        next_stage = get_next_stage(current_stage, skip_stages=skip_stages)

        if next_stage is None:
            # At end of pipeline
            if skip_stages:
                # AcroForm path: done (fields already defined by AcroForm)
                return NextAction(
                    action="done",
                    reason="Pipeline complete (AcroForm mode - fields already defined)",
                    field_ids=[],
                )
            # Normal path: go to REVIEW for final check
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

    def _get_skip_stages(self, job: JobContext) -> set[PipelineStage] | None:
        """Determine which stages to skip based on job configuration.

        Returns:
            Set of stages to skip, or None if no stages should be skipped.
        """
        if not self._job_has_acroform(job):
            return None

        # AcroForm is present - determine skip stages based on mode
        from app.models.job import JobMode

        if job.mode == JobMode.SCRATCH:
            # SCRATCH + AcroForm: No source to map/extract from
            # Pipeline: INGEST -> STRUCTURE -> LABELLING -> done
            return ACROFORM_SCRATCH_SKIP_STAGES
        else:
            # TRANSFER + AcroForm: Can extract from source, but no layout adjustment needed
            # Pipeline: INGEST -> STRUCTURE -> LABELLING -> MAP -> EXTRACT -> done
            return ACROFORM_TRANSFER_SKIP_STAGES

    def _job_has_acroform(self, job: JobContext) -> bool:
        """Check if the job's target document has AcroForm fields.

        Returns:
            True if target document has AcroForm, False otherwise.
        """
        if job.target_document and job.target_document.meta:
            return getattr(job.target_document.meta, "has_acroform", False)
        return False

    def _get_issue_field_ids(self, issues: Sequence[Issue]) -> list[str | None]:
        """Extract field IDs from a list of issues.

        Note: None values are filtered by NextAction's validator.
        """
        return [issue.field_id for issue in issues]

    def should_continue_run(
        self,
        job: JobContext,
        next_action: NextAction,
        steps_executed: int,
    ) -> bool:
        """Determine if the run should continue.

        Args:
            job: Current job context.
            next_action: The decided next action.
            steps_executed: Number of steps executed so far in this run.

        Returns:
            True if the run should continue, False otherwise.
        """
        # Stop conditions
        if next_action.action in ("done", "blocked", "ask", "manual"):
            return False

        if steps_executed >= self._config.max_steps_per_run:
            return False

        if job.status in (JobStatus.DONE, JobStatus.FAILED, JobStatus.BLOCKED):
            return False

        return True

    def get_retry_stages(self, retry_type: str) -> list[PipelineStage]:
        """Get the sequence of stages to re-run for a retry type.

        Per PRD:
        - layout_issue -> Adjust, Fill, Review
        - mapping_ambiguous -> Map, Extract

        Args:
            retry_type: Type of retry ("layout" or "mapping")

        Returns:
            List of stages to re-run in order.
        """
        if retry_type == "layout":
            return [
                PipelineStage.ADJUST,
                PipelineStage.FILL,
                PipelineStage.REVIEW,
            ]
        elif retry_type == "mapping":
            return [
                PipelineStage.MAP,
                PipelineStage.EXTRACT,
            ]
        else:
            return []
