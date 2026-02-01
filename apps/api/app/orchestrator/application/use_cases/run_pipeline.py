"""Run Pipeline use case.

This use case handles the execution of the document processing pipeline.
It coordinates service calls, handles state transitions, and manages
the execution loop based on the run mode.
"""

from dataclasses import dataclass
from typing import Sequence

from app.models import Issue, JobContext, JobStatus, RunMode
from app.models.orchestrator import NextAction, OrchestratorConfig, PipelineStage, StageResult
from app.repositories import JobRepository
from app.orchestrator.application.ports.service_gateway import ServiceGateway
from app.orchestrator.domain.rules import (
    TerminationAction,
    check_termination,
)


@dataclass(frozen=True)
class RunPipelineResult:
    """Result of running the pipeline."""

    job_context: JobContext
    steps_executed: int
    terminated: bool
    termination_reason: str | None


class RunPipelineUseCase:
    """Use case for running the document processing pipeline.

    This use case encapsulates the logic for:
    - Executing pipeline stages in sequence
    - Handling branching and retries
    - Managing termination conditions
    - Tracking improvement rates

    The use case depends on port interfaces (ServiceGateway, JobRepository)
    rather than concrete implementations, enabling easy testing and
    flexibility in deployment configurations.
    """

    def __init__(
        self,
        config: OrchestratorConfig,
        service_gateway: ServiceGateway,
        job_repository: JobRepository,
    ) -> None:
        """Initialize the use case.

        Args:
            config: Orchestrator configuration.
            service_gateway: Gateway for calling pipeline services.
            job_repository: Repository for job persistence.
        """
        self._config = config
        self._service_gateway = service_gateway
        self._job_repository = job_repository
        self._previous_issues: list[Issue] | None = None

    async def execute(
        self,
        job_id: str,
        run_mode: RunMode,
        max_steps: int | None = None,
    ) -> RunPipelineResult:
        """Execute the pipeline for a job.

        Args:
            job_id: ID of the job to run.
            run_mode: How to run the job (step, until_blocked, until_done).
            max_steps: Optional maximum steps to execute.

        Returns:
            RunPipelineResult with final job state and execution info.

        Raises:
            ValueError: If job not found or cannot be run.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            raise ValueError(f"Job is already {job.status.value}")

        # Initialize state tracking
        self._previous_issues = list(job.issues)
        steps_limit = max_steps or self._config.max_steps_per_run
        steps_executed = 0
        termination_reason: str | None = None

        # Execute pipeline loop
        while steps_executed < steps_limit:
            job = self._job_repository.get(job_id)
            if job is None:
                raise ValueError(f"Job lost during processing: {job_id}")

            # Check termination conditions
            termination = check_termination(
                job,
                self._config,
                self._previous_issues,
            )

            if termination.should_terminate:
                termination_reason = termination.reason
                # Apply termination action
                job = self._apply_termination(job_id, termination.action)
                break

            # Execute next stage
            current_stage = self._get_current_stage(job)
            next_stage = self._get_next_stage(current_stage)

            if next_stage is None:
                # Pipeline complete
                termination_reason = "Pipeline completed"
                job = self._apply_termination(job_id, TerminationAction.DONE)
                break

            # Execute the stage
            result = await self._execute_stage(job, next_stage)
            job = self._apply_stage_result(job_id, result)
            steps_executed += 1

            # Update issue tracking for improvement rate calculation
            self._previous_issues = list(job.issues)

            # Check run mode for early exit
            if run_mode == RunMode.STEP:
                break

            if run_mode == RunMode.UNTIL_BLOCKED:
                if job.status == JobStatus.BLOCKED:
                    termination_reason = "Job blocked, waiting for user input"
                    break

        # Get final job state
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job lost after processing: {job_id}")

        return RunPipelineResult(
            job_context=job,
            steps_executed=steps_executed,
            terminated=termination_reason is not None,
            termination_reason=termination_reason,
        )

    def _get_current_stage(self, job: JobContext) -> PipelineStage | None:
        """Get current pipeline stage from job context."""
        if job.current_stage is None:
            return None
        try:
            return PipelineStage(job.current_stage)
        except ValueError:
            return None

    def _get_next_stage(self, current_stage: PipelineStage | None) -> PipelineStage | None:
        """Get the next stage in the pipeline."""
        from app.models.orchestrator import get_next_stage
        return get_next_stage(current_stage)

    async def _execute_stage(
        self,
        job: JobContext,
        stage: PipelineStage,
    ) -> StageResult:
        """Execute a pipeline stage via the service gateway."""
        stage_methods = {
            PipelineStage.INGEST: self._service_gateway.call_ingest,
            PipelineStage.STRUCTURE: self._service_gateway.call_structure,
            PipelineStage.LABELLING: self._service_gateway.call_labelling,
            PipelineStage.MAP: self._service_gateway.call_map,
            PipelineStage.EXTRACT: self._service_gateway.call_extract,
            PipelineStage.ADJUST: self._service_gateway.call_adjust,
            PipelineStage.FILL: self._service_gateway.call_fill,
            PipelineStage.REVIEW: self._service_gateway.call_review,
        }

        method = stage_methods.get(stage)
        if method is None:
            return StageResult(
                stage=stage,
                success=False,
                issues=[],
                activities=[],
                updated_fields=[],
                error_message=f"Unknown stage: {stage.value}",
            )

        # Update job to show current stage
        self._job_repository.update(
            job.id,
            current_stage=stage.value,
            status=JobStatus.RUNNING,
        )

        return await method(job)

    def _apply_stage_result(
        self,
        job_id: str,
        result: StageResult,
    ) -> JobContext:
        """Apply stage result to job state."""
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        # Add activities
        for activity in result.activities:
            self._job_repository.add_activity(job_id, activity)

        # Add issues
        for issue in result.issues:
            self._job_repository.add_issue(job_id, issue)

        # Handle field updates
        existing_field_ids = {f.id for f in job.fields}
        for field in result.updated_fields:
            if field.id in existing_field_ids:
                updates = {}
                if field.value is not None:
                    updates["value"] = field.value
                if field.confidence is not None:
                    updates["confidence"] = field.confidence
                if updates:
                    self._job_repository.update_field(job_id, field.id, **updates)
            else:
                self._job_repository.add_field(job_id, field)

        # Update progress
        progress = self._calculate_progress(result.stage)
        updated_job = self._job_repository.update(
            job_id,
            progress=progress,
            current_step=f"completed_{result.stage.value}",
        )

        if updated_job is None:
            raise ValueError(f"Failed to update job: {job_id}")

        return updated_job

    def _apply_termination(
        self,
        job_id: str,
        action: TerminationAction,
    ) -> JobContext:
        """Apply termination action to job state."""
        status_map = {
            TerminationAction.DONE: JobStatus.DONE,
            TerminationAction.BLOCKED: JobStatus.BLOCKED,
            TerminationAction.ASK: JobStatus.BLOCKED,
            TerminationAction.MANUAL: JobStatus.BLOCKED,
        }

        next_actions_map = {
            TerminationAction.DONE: ["download", "export"],
            TerminationAction.BLOCKED: ["run"],
            TerminationAction.ASK: ["answer", "run"],
            TerminationAction.MANUAL: ["edit", "run"],
        }

        status = status_map.get(action, JobStatus.RUNNING)
        next_actions = next_actions_map.get(action, ["run"])

        updated_job = self._job_repository.update(
            job_id,
            status=status,
            next_actions=next_actions,
        )

        if updated_job is None:
            raise ValueError(f"Failed to update job: {job_id}")

        return updated_job

    def _calculate_progress(self, stage: PipelineStage) -> float:
        """Calculate progress based on completed stage."""
        stage_progress = {
            PipelineStage.INGEST: 0.10,
            PipelineStage.STRUCTURE: 0.20,
            PipelineStage.LABELLING: 0.30,
            PipelineStage.MAP: 0.45,
            PipelineStage.EXTRACT: 0.60,
            PipelineStage.ADJUST: 0.75,
            PipelineStage.FILL: 0.90,
            PipelineStage.REVIEW: 1.0,
        }
        return stage_progress.get(stage, 0.0)
