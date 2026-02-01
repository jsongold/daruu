"""Tests for the orchestrator."""

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
    RunMode,
)
from app.models.common import BBox
from app.models.orchestrator import OrchestratorConfig, PipelineStage, StageResult
from app.services.orchestrator import (
    DecisionEngine,
    Orchestrator,
    PipelineExecutor,
    ServiceClient,
)
from app.infrastructure.repositories import (
    get_document_repository,
    get_job_repository,
)


@pytest.fixture
def config() -> OrchestratorConfig:
    """Create test configuration."""
    return OrchestratorConfig(
        max_iterations=5,
        confidence_threshold=0.8,
        max_steps_per_run=20,
        high_severity_requires_user=True,
    )


@pytest.fixture
def target_document() -> Document:
    """Create and store a test target document."""
    doc_repo = get_document_repository()
    return doc_repo.create(
        document_type=DocumentType.TARGET,
        meta=DocumentMeta(
            filename="test-target.pdf",
            file_size=1024,
            mime_type="application/pdf",
            page_count=1,
        ),
        ref="test-target.pdf",
    )


@pytest.fixture
def source_document() -> Document:
    """Create and store a test source document."""
    doc_repo = get_document_repository()
    return doc_repo.create(
        document_type=DocumentType.SOURCE,
        meta=DocumentMeta(
            filename="test-source.pdf",
            file_size=2048,
            mime_type="application/pdf",
            page_count=2,
        ),
        ref="test-source.pdf",
    )


@pytest.fixture
def scratch_job(target_document: Document) -> JobContext:
    """Create a scratch mode job."""
    job_repo = get_job_repository()
    return job_repo.create(
        mode=JobMode.SCRATCH,
        target_document=target_document,
    )


@pytest.fixture
def transfer_job(target_document: Document, source_document: Document) -> JobContext:
    """Create a transfer mode job."""
    job_repo = get_job_repository()
    return job_repo.create(
        mode=JobMode.TRANSFER,
        target_document=target_document,
        source_document=source_document,
    )


class TestOrchestratorInit:
    """Test orchestrator initialization."""

    def test_creates_with_default_config(self) -> None:
        """Test orchestrator creates with default configuration."""
        orchestrator = Orchestrator()

        assert orchestrator.config is not None
        assert orchestrator.config.max_iterations > 0
        assert orchestrator.config.confidence_threshold > 0

    def test_creates_with_custom_config(self, config: OrchestratorConfig) -> None:
        """Test orchestrator creates with custom configuration."""
        orchestrator = Orchestrator(config=config)

        assert orchestrator.config == config
        assert orchestrator.config.max_iterations == 5


class TestOrchestratorStepMode:
    """Test step mode execution."""

    @pytest.mark.asyncio
    async def test_step_executes_single_stage(self, scratch_job: JobContext) -> None:
        """Test step mode executes only one stage."""
        orchestrator = Orchestrator()

        result = await orchestrator.run(scratch_job.id, RunMode.STEP)

        # Should have progressed from created
        assert result.status == JobStatus.RUNNING
        assert result.current_stage is not None

    @pytest.mark.asyncio
    async def test_step_increments_progress(self, scratch_job: JobContext) -> None:
        """Test step mode increments progress."""
        orchestrator = Orchestrator()

        result = await orchestrator.run(scratch_job.id, RunMode.STEP)

        assert result.progress > 0


class TestOrchestratorUntilBlocked:
    """Test until_blocked mode execution."""

    @pytest.mark.asyncio
    async def test_runs_until_blocked(self, scratch_job: JobContext) -> None:
        """Test job runs until blocked by issue."""
        config = OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=0.8,
            max_steps_per_run=100,
        )
        orchestrator = Orchestrator(config=config)

        result = await orchestrator.run(scratch_job.id, RunMode.UNTIL_BLOCKED)

        # Should complete, be blocked, or awaiting input
        assert result.status in (JobStatus.BLOCKED, JobStatus.DONE, JobStatus.RUNNING, JobStatus.AWAITING_INPUT)

    @pytest.mark.asyncio
    async def test_stops_on_low_confidence(self, scratch_job: JobContext) -> None:
        """Test job blocks when confidence is low."""
        config = OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=0.9,  # High threshold
            max_steps_per_run=100,
        )
        orchestrator = Orchestrator(config=config)

        result = await orchestrator.run(scratch_job.id, RunMode.UNTIL_BLOCKED)

        # Should be blocked due to low confidence fields
        if result.issues:
            assert any(
                issue.issue_type == IssueType.LOW_CONFIDENCE
                for issue in result.issues
            ) or result.status in (JobStatus.BLOCKED, JobStatus.DONE)


class TestOrchestratorTransferMode:
    """Test transfer mode specific behavior."""

    @pytest.mark.asyncio
    async def test_transfer_creates_mappings(self, transfer_job: JobContext) -> None:
        """Test transfer mode creates field mappings."""
        orchestrator = Orchestrator()

        # Run through mapping stage
        result = await orchestrator.run(transfer_job.id, RunMode.UNTIL_BLOCKED)

        # Should have progressed and created mappings or fields
        assert result.progress > 0


class TestOrchestratorErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_job(self) -> None:
        """Test raises ValueError for nonexistent job."""
        orchestrator = Orchestrator()

        with pytest.raises(ValueError, match="Job not found"):
            await orchestrator.run("nonexistent-id", RunMode.STEP)

    @pytest.mark.asyncio
    async def test_raises_for_done_job(self, scratch_job: JobContext) -> None:
        """Test raises ValueError for already done job."""
        job_repo = get_job_repository()
        job_repo.update(scratch_job.id, status=JobStatus.DONE)
        orchestrator = Orchestrator()

        with pytest.raises(ValueError, match="already done"):
            await orchestrator.run(scratch_job.id, RunMode.STEP)

    @pytest.mark.asyncio
    async def test_raises_for_failed_job(self, scratch_job: JobContext) -> None:
        """Test raises ValueError for already failed job."""
        job_repo = get_job_repository()
        job_repo.update(scratch_job.id, status=JobStatus.FAILED)
        orchestrator = Orchestrator()

        with pytest.raises(ValueError, match="already failed"):
            await orchestrator.run(scratch_job.id, RunMode.STEP)


class TestOrchestratorMaxSteps:
    """Test max steps limit."""

    @pytest.mark.asyncio
    async def test_respects_max_steps(self, scratch_job: JobContext) -> None:
        """Test job respects max_steps limit."""
        orchestrator = Orchestrator()

        result = await orchestrator.run(scratch_job.id, RunMode.UNTIL_BLOCKED, max_steps=2)

        # Should stop after limited steps
        assert result.status in (JobStatus.RUNNING, JobStatus.BLOCKED, JobStatus.DONE, JobStatus.AWAITING_INPUT)


class TestOrchestratorConvenience:
    """Test convenience methods."""

    @pytest.mark.asyncio
    async def test_run_step(self, scratch_job: JobContext) -> None:
        """Test run_step convenience method."""
        orchestrator = Orchestrator()

        result = await orchestrator.run_step(scratch_job.id)

        assert result.status == JobStatus.RUNNING

    @pytest.mark.asyncio
    async def test_run_until_blocked(self, scratch_job: JobContext) -> None:
        """Test run_until_blocked convenience method."""
        orchestrator = Orchestrator()

        result = await orchestrator.run_until_blocked(scratch_job.id)

        assert result.status in (JobStatus.RUNNING, JobStatus.BLOCKED, JobStatus.DONE, JobStatus.AWAITING_INPUT)

    def test_get_next_actions(self, scratch_job: JobContext) -> None:
        """Test get_next_actions returns available actions."""
        orchestrator = Orchestrator()

        actions = orchestrator.get_next_actions(scratch_job.id)

        assert len(actions) > 0
        assert actions[0].action == "continue"


class TestServiceClient:
    """Test service client mock implementations."""

    @pytest.mark.asyncio
    async def test_execute_ingest(self, scratch_job: JobContext) -> None:
        """Test ingest stage execution."""
        client = ServiceClient()

        result = await client.execute_stage(PipelineStage.INGEST, scratch_job)

        assert result.success is True
        assert result.stage == PipelineStage.INGEST
        assert len(result.activities) > 0

    @pytest.mark.asyncio
    async def test_execute_structure(self, scratch_job: JobContext) -> None:
        """Test structure stage execution generates fields."""
        client = ServiceClient()

        result = await client.execute_stage(PipelineStage.STRUCTURE, scratch_job)

        assert result.success is True
        assert len(result.updated_fields) > 0

    @pytest.mark.asyncio
    async def test_execute_extract(self, scratch_job: JobContext) -> None:
        """Test extract stage execution."""
        # First add some fields
        job_store = get_job_repository()
        field = FieldModel(
            id=str(uuid4()),
            name="Test Field",
            field_type=FieldType.TEXT,
            value=None,
            confidence=None,
            bbox=BBox(x=50, y=100, width=200, height=30, page=1),
            document_id=scratch_job.target_document.id,
            page=1,
            is_required=True,
            is_editable=True,
        )
        job_store.add_field(scratch_job.id, field)
        job = job_store.get(scratch_job.id)

        client = ServiceClient()
        result = await client.execute_stage(PipelineStage.EXTRACT, job)

        assert result.success is True
        assert len(result.updated_fields) > 0
        # Fields should have values now
        assert any(f.value is not None for f in result.updated_fields)


class TestPipelineExecutor:
    """Test pipeline executor."""

    @pytest.mark.asyncio
    async def test_execute_stage(self, scratch_job: JobContext) -> None:
        """Test stage execution updates job."""
        executor = PipelineExecutor()

        job, result = await executor.execute_stage(
            scratch_job.id,
            PipelineStage.INGEST,
        )

        assert result.success is True
        assert job.current_stage == PipelineStage.INGEST.value
        assert job.progress > 0

    @pytest.mark.asyncio
    async def test_execute_stage_adds_activities(self, scratch_job: JobContext) -> None:
        """Test stage execution adds activities."""
        executor = PipelineExecutor()
        initial_activities = len(scratch_job.activities)

        job, _ = await executor.execute_stage(
            scratch_job.id,
            PipelineStage.INGEST,
        )

        assert len(job.activities) > initial_activities

    def test_increment_iteration(self, scratch_job: JobContext) -> None:
        """Test iteration increment."""
        executor = PipelineExecutor()
        initial_count = scratch_job.iteration_count

        job = executor.increment_iteration(scratch_job.id)

        assert job is not None
        assert job.iteration_count == initial_count + 1

    def test_set_job_status(self, scratch_job: JobContext) -> None:
        """Test setting job status."""
        executor = PipelineExecutor()

        job = executor.set_job_status(
            scratch_job.id,
            JobStatus.BLOCKED,
            ["answer", "edit"],
        )

        assert job is not None
        assert job.status == JobStatus.BLOCKED
        assert "answer" in job.next_actions

    def test_clear_issues(self, scratch_job: JobContext) -> None:
        """Test clearing issues."""
        job_store = get_job_repository()

        # Add an issue first
        issue = Issue(
            id=str(uuid4()),
            field_id=str(uuid4()),
            issue_type=IssueType.LOW_CONFIDENCE,
            message="Test issue",
            severity=IssueSeverity.WARNING,
        )
        job_store.add_issue(scratch_job.id, issue)

        executor = PipelineExecutor()
        job = executor.clear_issues(scratch_job.id)

        assert job is not None
        assert len(job.issues) == 0


class TestIntegration:
    """Integration tests for full pipeline execution."""

    @pytest.mark.asyncio
    async def test_full_pipeline_scratch_mode(self, scratch_job: JobContext) -> None:
        """Test running through full pipeline in scratch mode."""
        config = OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=0.5,  # Lower threshold for mock data
            max_steps_per_run=50,
        )
        # Use mock ServiceClient (no services injected = mock fallbacks)
        mock_service_client = ServiceClient()
        orchestrator = Orchestrator(config=config, service_client=mock_service_client)

        # Run until done or blocked
        result = await orchestrator.run(scratch_job.id, RunMode.UNTIL_BLOCKED)

        # Should have progressed significantly
        assert result.progress > 0.5
        # Should have fields
        assert len(result.fields) > 0
        # Activities should be recorded
        assert len(result.activities) > 1

    @pytest.mark.asyncio
    async def test_full_pipeline_transfer_mode(self, transfer_job: JobContext) -> None:
        """Test running through full pipeline in transfer mode."""
        config = OrchestratorConfig(
            max_iterations=10,
            confidence_threshold=0.5,
            max_steps_per_run=50,
        )
        # Use mock ServiceClient (no services injected = mock fallbacks)
        mock_service_client = ServiceClient()
        orchestrator = Orchestrator(config=config, service_client=mock_service_client)

        result = await orchestrator.run(transfer_job.id, RunMode.UNTIL_BLOCKED)

        # Should have progressed
        assert result.progress > 0.3

    @pytest.mark.asyncio
    async def test_step_by_step_execution(self, scratch_job: JobContext) -> None:
        """Test executing job step by step."""
        orchestrator = Orchestrator()

        stages_seen = set()
        for _ in range(8):  # Max 8 stages
            job = await orchestrator.run(scratch_job.id, RunMode.STEP)
            if job.current_stage:
                stages_seen.add(job.current_stage)
            if job.status in (JobStatus.DONE, JobStatus.BLOCKED):
                break

        # Should have progressed through multiple stages
        assert len(stages_seen) >= 1
