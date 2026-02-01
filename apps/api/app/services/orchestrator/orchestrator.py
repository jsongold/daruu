"""Main orchestrator for pipeline execution and control.

This module provides the central orchestration logic that:
- Executes the full pipeline sequence by calling Services
- Controls branching and loop decisions
- Manages job state transitions
- Handles different run modes (step, until_blocked, until_done)

Service vs Agent Architecture:
- Orchestrator (UseCase layer) calls Services (not Agents directly)
- Services may internally use Agents (FieldLabellingAgent, etc.)
- Services may internally use other Services (OcrService, etc.)
- Orchestrator doesn't know about Agent implementation details
"""

from datetime import datetime, timezone
from time import time
from typing import Any
from uuid import uuid4

from app.config import get_settings
from app.models import (
    Activity,
    ActivityAction,
    JobContext,
    JobStatus,
    RunMode,
)
from app.models.orchestrator import (
    NextAction,
    OrchestratorConfig,
    PipelineStage,
    StageResult,
)
from app.services.orchestrator.decision_engine import DecisionEngine
from app.services.orchestrator.pipeline_executor import PipelineExecutor
from app.services.orchestrator.service_client import ServiceClient
from app.services.orchestrator.factories import (
    create_adjust_service_port,
    create_extract_service_port,
    create_fill_service_port,
    create_ingest_service_port,
    create_mapping_service_port,
    create_review_service_port,
    create_structure_labelling_service_port,
)
from app.repositories import EventPublisher, JobRepository
from app.infrastructure.repositories import (
    get_event_publisher,
    get_job_repository,
)
from app.infrastructure.observability import (
    get_tracer,
    get_logger,
    metrics,
    set_span_attribute,
    with_job_context,
)


class Orchestrator:
    """Main orchestrator for controlling pipeline execution.

    This class is the central coordinator (UseCase layer) responsible for:
    - Running jobs through the pipeline stages by calling Services
    - Making decisions about branching and retries
    - Managing state transitions
    - Publishing events for real-time updates

    Service vs Agent Architecture:
    - Orchestrator calls Services (not Agents directly)
    - Services may internally use Agents (FieldLabellingAgent, ValueExtractionAgent, MappingAgent)
    - Services may internally use other Services (OcrService, PdfWriteService, etc.)
    - Orchestrator only knows about Service contracts (input/output), not implementation details

    The orchestrator follows these principles:
    - Single writer for JobContext updates
    - Immutable data patterns (never mutate, always create new)
    - Comprehensive error handling
    - Clear separation of concerns (decision logic in DecisionEngine)
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        job_repository: JobRepository | None = None,
        event_publisher: EventPublisher | None = None,
        service_client: ServiceClient | None = None,
    ) -> None:
        """Initialize the orchestrator.

        Args:
            config: Configuration for orchestration behavior.
            job_repository: Repository for persisting job state.
            event_publisher: Publisher for real-time events.
            service_client: Client for calling pipeline services.
        """
        settings = get_settings()
        self._config = config or OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=settings.default_confidence_threshold,
            max_steps_per_run=settings.max_steps_per_run,
        )
        self._job_repository = job_repository or get_job_repository()
        self._event_publisher = event_publisher or get_event_publisher()
        # Create service client with all real services if not provided
        if service_client is None:
            self._service_client = ServiceClient(
                ingest_service=create_ingest_service_port(),
                structure_labelling_service=create_structure_labelling_service_port(),
                mapping_service=create_mapping_service_port(),
                extract_service=create_extract_service_port(),
                adjust_service=create_adjust_service_port(),
                fill_service=create_fill_service_port(),
                review_service=create_review_service_port(),
            )
        else:
            self._service_client = service_client
        self._decision_engine = DecisionEngine(self._config)
        self._pipeline_executor = PipelineExecutor(
            service_client=self._service_client,
            job_repository=self._job_repository,
        )

    @property
    def config(self) -> OrchestratorConfig:
        """Get the orchestrator configuration."""
        return self._config

    @property
    def decision_engine(self) -> DecisionEngine:
        """Get the decision engine."""
        return self._decision_engine

    async def run(
        self,
        job_id: str,
        run_mode: RunMode,
        max_steps: int | None = None,
    ) -> JobContext:
        """Run a job with the specified mode.

        Args:
            job_id: ID of the job to run.
            run_mode: How to run the job (step, until_blocked, until_done).
            max_steps: Optional maximum steps to execute.

        Returns:
            Updated job context after running.

        Raises:
            ValueError: If job not found or cannot be run.
        """
        tracer = get_tracer("orchestrator")
        logger = get_logger("orchestrator", job_id=job_id)
        job_start_time = time()

        with tracer.start_as_current_span("orchestrator.run") as span:
            span.set_attribute("job.id", job_id)
            span.set_attribute("run_mode", run_mode.value)

            # Set job context for all nested logging
            with with_job_context(job_id):
                logger.info(
                    "Pipeline run started",
                    run_mode=run_mode.value,
                    max_steps=max_steps,
                )
                metrics.active_jobs.inc()

                try:
                    job = self._job_repository.get(job_id)
                    if job is None:
                        logger.error("Job not found", job_id=job_id)
                        raise ValueError(f"Job not found: {job_id}")

                    if job.status in (JobStatus.DONE, JobStatus.FAILED):
                        logger.warning(
                            "Job already in terminal state",
                            status=job.status.value,
                        )
                        raise ValueError(f"Job is already {job.status.value}")

                    # Set job to running
                    job = self._set_job_running(job_id)
                    if job is None:
                        raise ValueError(f"Failed to update job status: {job_id}")

                    await self._publish_event(job_id, "job_started", {"run_mode": run_mode.value})

                    # Execute based on run mode
                    steps_limit = max_steps or self._config.max_steps_per_run
                    steps_executed = 0
                    span.set_attribute("steps_limit", steps_limit)

                    while steps_executed < steps_limit:
                        # Get current job state
                        job = self._job_repository.get(job_id)
                        if job is None:
                            raise ValueError(f"Job lost during processing: {job_id}")

                        # Decide next action
                        stage_result = None
                        next_action = self._decision_engine.decide_next_action(job, stage_result)

                        # Check if we should stop
                        if not self._should_continue(run_mode, next_action, job, steps_executed):
                            break

                        # Execute the next action
                        job, stage_result = await self._execute_action(job_id, next_action)
                        steps_executed += 1

                        # Log step completion
                        logger.info(
                            "Step completed",
                            step=steps_executed,
                            stage=next_action.stage.value if next_action.stage else None,
                            action=next_action.action,
                            progress=job.progress,
                        )

                        # Publish step event
                        await self._publish_event(job_id, "step_completed", {
                            "step": steps_executed,
                            "stage": next_action.stage.value if next_action.stage else None,
                            "action": next_action.action,
                            "progress": job.progress,
                        })

                        # Re-evaluate after stage execution
                        next_action = self._decision_engine.decide_next_action(job, stage_result)

                        # Apply action result to job state
                        job = self._apply_action_result(job_id, next_action)
                        if job is None:
                            raise ValueError(f"Failed to apply action result: {job_id}")

                        # Check if we're done or blocked
                        if next_action.action in ("done", "blocked", "ask", "manual"):
                            break

                        # For step mode, execute only one stage
                        if run_mode == RunMode.STEP:
                            break

                    # Get final job state
                    job = self._job_repository.get(job_id)
                    if job is None:
                        raise ValueError(f"Job lost after processing: {job_id}")

                    # Record job completion metrics
                    job_duration = time() - job_start_time
                    job_mode = job.mode.value if job.mode else "unknown"
                    metrics.record_job_completion(job.status.value, job_mode, job_duration)

                    span.set_attribute("steps_executed", steps_executed)
                    span.set_attribute("final_status", job.status.value)
                    span.set_attribute("final_progress", job.progress)

                    logger.info(
                        "Pipeline run completed",
                        status=job.status.value,
                        steps_executed=steps_executed,
                        progress=job.progress,
                        duration_seconds=job_duration,
                    )

                    # Publish completion event
                    await self._publish_event(job_id, "run_completed", {
                        "status": job.status.value,
                        "steps_executed": steps_executed,
                        "progress": job.progress,
                    })

                    return job

                except Exception as e:
                    logger.exception("Pipeline run failed", error=str(e))
                    span.set_attribute("error", True)
                    span.set_attribute("error.message", str(e))
                    metrics.record_error("pipeline_error", "orchestrator")
                    raise

                finally:
                    metrics.active_jobs.dec()

    def _set_job_running(self, job_id: str) -> JobContext | None:
        """Set job status to running."""
        return self._job_repository.update(job_id, status=JobStatus.RUNNING)

    def _should_continue(
        self,
        run_mode: RunMode,
        next_action: NextAction,
        job: JobContext,
        steps_executed: int,
    ) -> bool:
        """Determine if execution should continue.

        Args:
            run_mode: Current run mode.
            next_action: Decided next action.
            job: Current job state.
            steps_executed: Steps executed so far.

        Returns:
            True if execution should continue.
        """
        # Stop if action is terminal
        if next_action.action in ("done", "blocked"):
            return False

        # Stop if action requires user input and not in until_done mode
        if next_action.action in ("ask", "manual") and run_mode != RunMode.UNTIL_DONE:
            return False

        # Stop if job is in terminal state
        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            return False

        # Check step limit
        if not self._decision_engine.should_continue_run(job, next_action, steps_executed):
            return False

        return True

    async def _execute_action(
        self,
        job_id: str,
        next_action: NextAction,
    ) -> tuple[JobContext, StageResult | None]:
        """Execute the decided action.

        Args:
            job_id: ID of the job.
            next_action: Action to execute.

        Returns:
            Tuple of (updated job, stage result if applicable).
        """
        logger = get_logger("orchestrator", job_id=job_id)

        if next_action.action == "continue" and next_action.stage is not None:
            # Execute the next stage
            logger.info(
                "Executing stage",
                stage=next_action.stage.value,
                action=next_action.action,
            )
            return await self._pipeline_executor.execute_stage(job_id, next_action.stage)

        if next_action.action == "retry" and next_action.stage is not None:
            # Record retry metric
            metrics.record_retry(next_action.stage.value, next_action.reason)
            logger.info(
                "Executing retry",
                stage=next_action.stage.value,
                reason=next_action.reason,
                field_ids=next_action.field_ids,
            )

            # Increment iteration count and retry
            self._pipeline_executor.increment_iteration(job_id)

            # Clear issues related to the retry fields
            if next_action.field_ids:
                self._pipeline_executor.clear_issues(job_id, next_action.field_ids)

            # Execute retry sequence (Adjust->Fill->Review or Map->Extract)
            # Per PRD:
            # - layout_issue -> Adjust -> Fill -> Review
            # - mapping_ambiguous -> Map -> Extract
            job, results = await self._pipeline_executor.execute_retry_sequence(
                job_id,
                next_action.stage,
                next_action.reason,
            )

            # Return the last stage result (or None if no results)
            last_result = results[-1] if results else None
            return job, last_result

        # For ask/manual/blocked/done actions, no stage execution needed
        logger.info(
            "Action does not require stage execution",
            action=next_action.action,
            reason=next_action.reason,
        )
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")
        return job, None

    def _apply_action_result(
        self,
        job_id: str,
        next_action: NextAction,
    ) -> JobContext | None:
        """Apply the action result to job state.

        Args:
            job_id: ID of the job.
            next_action: The action that was decided.

        Returns:
            Updated job context.
        """
        # Status mapping per PRD:
        # - done: Job complete
        # - blocked: Cannot proceed (critical issues, max iterations)
        # - ask: Awaiting user input (low confidence, ambiguous mapping)
        # - manual: Requires manual intervention (critical issues)
        status_map = {
            "done": JobStatus.DONE,
            "blocked": JobStatus.BLOCKED,
            "ask": JobStatus.AWAITING_INPUT,  # User can provide input
            "manual": JobStatus.BLOCKED,  # Requires manual resolution
        }

        # Available actions for each state
        next_actions_map = {
            "done": ["download", "export", "restart"],
            "blocked": ["retry", "cancel"],
            "ask": ["submit_answer", "skip", "run"],
            "manual": ["resolve_manually", "edit", "cancel"],
            "continue": ["pause", "cancel"],
            "retry": ["pause", "cancel"],
        }

        if next_action.action in status_map:
            return self._pipeline_executor.set_job_status(
                job_id,
                status_map[next_action.action],
                next_actions_map.get(next_action.action, []),
            )

        # For continue/retry actions, keep running status
        return self._job_repository.get(job_id)

    async def _publish_event(
        self,
        job_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish an event to subscribers.

        Args:
            job_id: ID of the job.
            event_type: Type of event.
            data: Event data.
        """
        await self._event_publisher.publish(job_id, {
            "event": event_type,
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        })

    async def run_step(self, job_id: str) -> JobContext:
        """Execute a single pipeline step.

        Convenience method for step-by-step execution.

        Args:
            job_id: ID of the job.

        Returns:
            Updated job context.
        """
        return await self.run(job_id, RunMode.STEP)

    async def run_until_blocked(self, job_id: str) -> JobContext:
        """Run until blocked or done.

        Convenience method for running until user input is needed.

        Args:
            job_id: ID of the job.

        Returns:
            Updated job context.
        """
        return await self.run(job_id, RunMode.UNTIL_BLOCKED)

    async def run_until_done(self, job_id: str) -> JobContext:
        """Run until done (may auto-answer questions).

        Convenience method for fully automated execution.
        Note: In production, this would use LLM to auto-answer questions.

        Args:
            job_id: ID of the job.

        Returns:
            Updated job context.
        """
        return await self.run(job_id, RunMode.UNTIL_DONE)

    def get_next_actions(self, job_id: str) -> list[NextAction]:
        """Get available next actions for a job.

        Args:
            job_id: ID of the job.

        Returns:
            List of available next actions.

        Raises:
            ValueError: If job not found.
        """
        job = self._job_repository.get(job_id)
        if job is None:
            raise ValueError(f"Job not found: {job_id}")

        next_action = self._decision_engine.decide_next_action(job, None)
        return [next_action]
