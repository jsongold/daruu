"""Pipeline executor for running individual pipeline stages.

This module handles the execution of pipeline stages and applies
the results to the job context in an immutable way.

Service vs Agent Architecture:
- PipelineExecutor calls ServiceClient to execute stages
- ServiceClient calls Services (not Agents directly)
- Services may internally use Agents (FieldLabellingAgent, etc.)
- Services may internally use other Services (OcrService, etc.)

Pipeline Sequence (per PRD):
Ingest -> Structure/Labelling -> Mapping -> Extract -> Adjust -> Fill -> Review
"""

from datetime import datetime, timezone
from time import time
from typing import Any
from uuid import uuid4

from app.config import get_pipeline_progress_config
from app.infrastructure.observability import (
    get_logger,
    get_tracer,
    metrics,
)
from app.infrastructure.repositories import get_job_repository
from app.models import (
    Activity,
    ActivityAction,
    JobContext,
    JobStatus,
)
from app.models.orchestrator import (
    NextAction,
    PipelineStage,
    StageResult,
    get_next_stage,
)
from app.orchestrator.service_client import ServiceClient
from app.repositories import JobRepository


class PipelineExecutor:
    """Executor for pipeline stages.

    This class is responsible for:
    - Calling the appropriate service for each stage
    - Applying stage results to the job context
    - Managing stage transitions
    - Tracking activities and issues
    - Handling retry sequences for layout and mapping issues

    Pipeline Sequence:
    Ingest -> Structure/Labelling -> Mapping -> Extract -> Adjust -> Fill -> Review

    Retry Sequences:
    - layout_issue -> Re-run Adjust -> Fill -> Review
    - mapping_ambiguous -> Re-run Mapping -> Extract
    """

    def __init__(
        self,
        service_client: ServiceClient | None = None,
        job_repository: JobRepository | None = None,
    ) -> None:
        """Initialize the pipeline executor.

        Args:
            service_client: Client for calling pipeline services.
            job_repository: Repository for persisting job state.
        """
        self._service_client = service_client or ServiceClient()
        self._job_repository = job_repository or get_job_repository()

    @property
    def service_client(self) -> ServiceClient:
        """Get the service client."""
        return self._service_client

    async def execute_stage(
        self,
        job_id: str,
        stage: PipelineStage,
    ) -> tuple[JobContext, StageResult]:
        """Execute a pipeline stage for a job.

        Args:
            job_id: ID of the job.
            stage: The pipeline stage to execute.

        Returns:
            Tuple of (updated job context, stage result).

        Raises:
            ValueError: If job not found.
        """
        tracer = get_tracer("pipeline")
        logger = get_logger("pipeline_executor", job_id=job_id)
        stage_start_time = time()

        with tracer.start_as_current_span(f"pipeline.stage.{stage.value}") as span:
            span.set_attribute("job.id", job_id)
            span.set_attribute("pipeline.stage", stage.value)

            logger.info("Stage execution started", stage=stage.value)

            job = self._job_repository.get(job_id)
            if job is None:
                logger.error("Job not found for stage execution", stage=stage.value)
                raise ValueError(f"Job not found: {job_id}")

            # Add activity for stage start
            self._add_stage_started_activity(job_id, stage)

            # Update job status to show current stage
            job = self._update_current_stage(job_id, stage)
            if job is None:
                raise ValueError(f"Failed to update job stage: {job_id}")

            # Execute the stage via service client
            try:
                result = await self._service_client.execute_stage(stage, job)
            except Exception as e:
                # Record failure metrics
                stage_duration = time() - stage_start_time
                metrics.record_stage_execution(stage.value, "failure", stage_duration)
                metrics.record_error("stage_execution", stage.value)
                logger.exception(
                    "Stage execution failed",
                    stage=stage.value,
                    error=str(e),
                    duration_seconds=stage_duration,
                )
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                raise

            # Record stage metrics
            stage_duration = time() - stage_start_time
            status = "success" if result.success else "failure"
            metrics.record_stage_execution(stage.value, status, stage_duration)

            # Record issues
            for issue in result.issues:
                metrics.record_issue(issue.issue_type.value, issue.severity.value)

            span.set_attribute("result.success", result.success)
            span.set_attribute("result.issues_count", len(result.issues))
            span.set_attribute("result.updated_fields_count", len(result.updated_fields))
            span.set_attribute("duration_seconds", stage_duration)

            logger.info(
                "Stage execution completed",
                stage=stage.value,
                success=result.success,
                issues_count=len(result.issues),
                updated_fields_count=len(result.updated_fields),
                duration_seconds=stage_duration,
            )

            # Apply stage result to job
            job = self._apply_stage_result(job_id, result)
            if job is None:
                raise ValueError(f"Failed to apply stage result: {job_id}")

            # Add activity for stage completion
            self._add_stage_completed_activity(job_id, stage, result)

            return job, result

    async def execute_retry_sequence(
        self,
        job_id: str,
        start_stage: PipelineStage,
        reason: str,
    ) -> tuple[JobContext, list[StageResult]]:
        """Execute a sequence of stages for retry.

        Per PRD:
        - layout_issue -> Adjust -> Fill -> Review
        - mapping_ambiguous -> Map -> Extract

        Args:
            job_id: ID of the job.
            start_stage: The first stage in the retry sequence.
            reason: Reason for the retry.

        Returns:
            Tuple of (updated job context, list of stage results).

        Raises:
            ValueError: If job not found.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        # Add activity for retry start
        self.add_activity(
            job_id,
            ActivityAction.RETRY_STARTED,
            details={"stage": start_stage.value, "reason": reason},
        )

        # Determine stages to execute based on start stage
        stages_to_execute = self._get_retry_sequence(start_stage)

        results: list[StageResult] = []
        for stage in stages_to_execute:
            job, result = await self.execute_stage(job_id, stage)
            results.append(result)

            # Stop if stage failed
            if not result.success:
                break

        return job, results

    def _get_retry_sequence(self, start_stage: PipelineStage) -> list[PipelineStage]:
        """Get the sequence of stages to execute for a retry.

        Args:
            start_stage: The starting stage for the retry.

        Returns:
            List of stages to execute in order.
        """
        if start_stage == PipelineStage.ADJUST:
            # Layout issue retry: Adjust -> Fill -> Review
            return [
                PipelineStage.ADJUST,
                PipelineStage.FILL,
                PipelineStage.REVIEW,
            ]
        elif start_stage == PipelineStage.MAP:
            # Mapping issue retry: Map -> Extract
            return [
                PipelineStage.MAP,
                PipelineStage.EXTRACT,
            ]
        else:
            # Single stage retry
            return [start_stage]

    def _add_stage_started_activity(
        self,
        job_id: str,
        stage: PipelineStage,
    ) -> None:
        """Add activity for stage start."""
        action_mapping = {
            PipelineStage.INGEST: ActivityAction.JOB_STARTED,
            PipelineStage.STRUCTURE: ActivityAction.EXTRACTION_STARTED,
            PipelineStage.LABELLING: ActivityAction.EXTRACTION_STARTED,
            PipelineStage.MAP: ActivityAction.MAPPING_CREATED,
            PipelineStage.EXTRACT: ActivityAction.EXTRACTION_STARTED,
            PipelineStage.ADJUST: ActivityAction.RENDERING_STARTED,
            PipelineStage.FILL: ActivityAction.RENDERING_STARTED,
            PipelineStage.REVIEW: ActivityAction.EXTRACTION_COMPLETED,
        }

        action = action_mapping.get(stage, ActivityAction.EXTRACTION_STARTED)

        self._job_repository.add_activity(
            job_id,
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=action,
                details={"stage": stage.value, "status": "started"},
            ),
        )

    def _add_stage_completed_activity(
        self,
        job_id: str,
        stage: PipelineStage,
        result: StageResult,
    ) -> None:
        """Add activity for stage completion."""
        if result.success:
            action = ActivityAction.EXTRACTION_COMPLETED
            if stage == PipelineStage.FILL:
                action = ActivityAction.RENDERING_COMPLETED
            elif stage == PipelineStage.REVIEW:
                action = (
                    ActivityAction.JOB_COMPLETED
                    if not result.issues
                    else ActivityAction.QUESTION_ASKED
                )
            elif stage == PipelineStage.MAP:
                action = ActivityAction.MAPPING_CREATED
        else:
            action = ActivityAction.ERROR_OCCURRED

        details = {
            "stage": stage.value,
            "status": "completed" if result.success else "failed",
            "issues_count": len(result.issues),
            "fields_updated": len(result.updated_fields),
        }

        if result.error_message:
            details["error"] = result.error_message

        self._job_repository.add_activity(
            job_id,
            Activity(
                id=str(uuid4()),
                timestamp=datetime.now(timezone.utc),
                action=action,
                details=details,
            ),
        )

    def _update_current_stage(
        self,
        job_id: str,
        stage: PipelineStage,
    ) -> JobContext | None:
        """Update the current stage in the job context."""
        return self._job_repository.update(
            job_id,
            current_stage=stage.value,
            current_step=f"executing_{stage.value}",
            status=JobStatus.RUNNING,
        )

    def _apply_stage_result(
        self,
        job_id: str,
        result: StageResult,
    ) -> JobContext | None:
        """Apply a stage result to the job context.

        This method handles:
        - Adding new fields from the stage
        - Updating existing fields with new values
        - Adding new issues
        - Recording activities
        - Updating progress

        Args:
            job_id: ID of the job.
            result: Result from the stage execution.

        Returns:
            Updated job context, or None if job not found.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        # Add activities from stage result
        for activity in result.activities:
            self._job_repository.add_activity(job_id, activity)

        # Add new issues from stage result
        for issue in result.issues:
            self._job_repository.add_issue(job_id, issue)

        # Handle field updates
        self._apply_field_updates(job_id, result, job)

        # Update progress based on stage
        progress = self._calculate_progress(result.stage)

        # Get updated job
        job = self._job_repository.update(
            job_id,
            progress=progress,
            current_step=f"completed_{result.stage.value}",
        )

        return job

    def _apply_field_updates(
        self,
        job_id: str,
        result: StageResult,
        job: JobContext,
    ) -> None:
        """Apply field updates from the stage result.

        Fields can be:
        - New fields (added during structure stage)
        - Updated fields (values/confidence changed during extract)

        Args:
            job_id: ID of the job.
            result: Stage result containing updated fields.
            job: Current job context.
        """
        existing_field_ids = {f.id for f in job.fields}

        for field in result.updated_fields:
            if field.id in existing_field_ids:
                # Update existing field
                updates: dict[str, Any] = {}
                if field.value is not None:
                    updates["value"] = field.value
                if field.confidence is not None:
                    updates["confidence"] = field.confidence
                if updates:
                    self._job_repository.update_field(job_id, field.id, **updates)
            else:
                # Add new field
                self._job_repository.add_field(job_id, field)

    def _calculate_progress(self, stage: PipelineStage) -> float:
        """Calculate progress based on completed stage.

        Progress is distributed across all stages per PRD pipeline:
        Ingest(10%) -> Structure(20%) -> Labelling(30%) -> Map(45%) ->
        Extract(60%) -> Adjust(75%) -> Fill(90%) -> Review(100%)

        Args:
            stage: The completed stage.

        Returns:
            Progress value between 0.0 and 1.0.
        """
        progress_config = get_pipeline_progress_config()
        return progress_config.get_progress(stage.value)

    def apply_next_action(
        self,
        job_id: str,
        next_action: NextAction,
    ) -> JobContext | None:
        """Apply a next action decision to the job.

        Updates job status and next_actions based on the decision.

        Args:
            job_id: ID of the job.
            next_action: The decided next action.

        Returns:
            Updated job context, or None if job not found.
        """
        action_to_status = {
            "done": JobStatus.DONE,
            "blocked": JobStatus.BLOCKED,
            "ask": JobStatus.AWAITING_INPUT,
            "manual": JobStatus.BLOCKED,
            "continue": JobStatus.RUNNING,
            "retry": JobStatus.RUNNING,
        }

        status = action_to_status.get(next_action.action, JobStatus.RUNNING)

        # Build next_actions list based on the action
        next_actions: list[str] = []
        if next_action.action == "ask":
            next_actions = ["submit_answer", "skip", "cancel"]
        elif next_action.action == "manual":
            next_actions = ["resolve_manually", "cancel"]
        elif next_action.action == "blocked":
            next_actions = ["retry", "cancel"]
        elif next_action.action in ("continue", "retry"):
            next_actions = ["pause", "cancel"]
        elif next_action.action == "done":
            next_actions = ["download", "restart"]

        # Add activity for the action
        self.add_activity(
            job_id,
            ActivityAction.QUESTION_ASKED
            if next_action.action == "ask"
            else ActivityAction.JOB_COMPLETED,
            details={
                "action": next_action.action,
                "reason": next_action.reason,
                "affected_fields": next_action.field_ids,
            },
        )

        return self._job_repository.update(
            job_id,
            status=status,
            next_actions=next_actions,
        )

    def set_job_status(
        self,
        job_id: str,
        status: JobStatus,
        next_actions: list[str] | None = None,
    ) -> JobContext | None:
        """Set the job status and next actions.

        Args:
            job_id: ID of the job.
            status: New job status.
            next_actions: Optional list of available next actions.

        Returns:
            Updated job context, or None if job not found.
        """
        updates: dict[str, Any] = {"status": status}
        if next_actions is not None:
            updates["next_actions"] = next_actions

        return self._job_repository.update(job_id, **updates)

    def increment_iteration(self, job_id: str) -> JobContext | None:
        """Increment the iteration counter for a job.

        Used when retrying stages to track loop count.

        Args:
            job_id: ID of the job.

        Returns:
            Updated job context, or None if job not found.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            return None

        return self._job_repository.update(
            job_id,
            iteration_count=job.iteration_count + 1,
        )

    def clear_issues(
        self,
        job_id: str,
        field_ids: list[str] | None = None,
        issue_types: list[str] | None = None,
    ) -> JobContext | None:
        """Clear issues from a job.

        Args:
            job_id: ID of the job.
            field_ids: If provided, only clear issues for these fields.
                      If None, clear all issues.
            issue_types: If provided, only clear issues of these types.

        Returns:
            Updated job context, or None if job not found.
        """
        if field_ids is None and issue_types is None:
            self._job_repository.clear_issues(job_id)
        else:
            # Clear issues for specific fields or types
            job = self._job_repository.get(job_id)
            if job is None:
                return None

            for issue in job.issues:
                should_remove = False
                if field_ids and issue.field_id in field_ids:
                    should_remove = True
                if issue_types and issue.issue_type.value in issue_types:
                    should_remove = True
                if should_remove:
                    self._job_repository.remove_issue(job_id, issue.id)

        return self._job_repository.get(job_id)

    def add_activity(
        self,
        job_id: str,
        action: ActivityAction,
        details: dict[str, Any] | None = None,
        field_id: str | None = None,
    ) -> JobContext | None:
        """Add an activity record to the job.

        Args:
            job_id: ID of the job.
            action: Type of activity action.
            details: Optional additional details.
            field_id: Optional related field ID.

        Returns:
            Updated job context, or None if job not found.
        """
        activity = Activity(
            id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            action=action,
            details=details or {},
            field_id=field_id,
        )

        return self._job_repository.add_activity(job_id, activity)

    def get_next_stage_in_sequence(
        self,
        current_stage: PipelineStage | None,
    ) -> PipelineStage | None:
        """Get the next stage in the standard pipeline sequence.

        Per PRD: Ingest -> Structure -> Labelling -> Map -> Extract -> Adjust -> Fill -> Review

        Args:
            current_stage: The current stage, or None if not started.

        Returns:
            The next stage, or None if at the end of the pipeline.
        """
        return get_next_stage(current_stage)
