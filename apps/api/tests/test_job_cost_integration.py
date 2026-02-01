"""Integration tests for job cost tracking."""

import pytest
from datetime import datetime, timezone

from app.models import (
    JobContext,
    JobMode,
    JobStatus,
    CostSummaryModel,
    CostBreakdown,
)
from app.models.document import Document, DocumentMeta, DocumentType
from app.models.cost import CostTracker, LLMUsage, tracker_to_pydantic


class TestJobContextCostIntegration:
    """Tests for cost tracking in JobContext."""

    @pytest.fixture
    def sample_document(self) -> Document:
        """Create a sample document for testing."""
        return Document(
            id="doc-123",
            ref="/uploads/doc-123/test.pdf",
            document_type=DocumentType.TARGET,
            meta=DocumentMeta(
                page_count=3,
                file_size=102400,
                mime_type="application/pdf",
                filename="test.pdf",
            ),
            created_at=datetime.now(timezone.utc),
        )

    def test_job_context_has_cost_field(self, sample_document: Document) -> None:
        """Test that JobContext includes the cost field."""
        job = JobContext(
            id="job-123",
            mode=JobMode.SCRATCH,
            status=JobStatus.CREATED,
            target_document=sample_document,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert hasattr(job, "cost")
        assert isinstance(job.cost, CostSummaryModel)

    def test_job_context_with_default_cost(self, sample_document: Document) -> None:
        """Test that JobContext has zero cost by default."""
        job = JobContext(
            id="job-123",
            mode=JobMode.SCRATCH,
            status=JobStatus.CREATED,
            target_document=sample_document,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        assert job.cost.llm_tokens_input == 0
        assert job.cost.llm_tokens_output == 0
        assert job.cost.llm_calls == 0
        assert job.cost.ocr_pages_processed == 0
        assert job.cost.estimated_cost_usd == 0.0

    def test_job_context_with_cost_data(self, sample_document: Document) -> None:
        """Test that JobContext can be created with cost data."""
        cost = CostSummaryModel(
            llm_tokens_input=5000,
            llm_tokens_output=2500,
            llm_calls=3,
            ocr_pages_processed=10,
            estimated_cost_usd=0.05,
            breakdown=CostBreakdown(llm_cost_usd=0.04, ocr_cost_usd=0.01),
            model_name="gpt-4o-mini",
        )

        job = JobContext(
            id="job-456",
            mode=JobMode.TRANSFER,
            status=JobStatus.RUNNING,
            target_document=sample_document,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            cost=cost,
        )

        assert job.cost.llm_tokens_input == 5000
        assert job.cost.llm_tokens_output == 2500
        assert job.cost.llm_calls == 3
        assert job.cost.ocr_pages_processed == 10
        assert job.cost.estimated_cost_usd == 0.05

    def test_job_context_serialization_with_cost(self, sample_document: Document) -> None:
        """Test that JobContext with cost serializes correctly."""
        cost = CostSummaryModel(
            llm_tokens_input=1000,
            llm_tokens_output=500,
            llm_calls=2,
            ocr_pages_processed=5,
            estimated_cost_usd=0.02,
            breakdown=CostBreakdown(llm_cost_usd=0.015, ocr_cost_usd=0.005),
            model_name="gpt-4o-mini",
        )

        job = JobContext(
            id="job-789",
            mode=JobMode.SCRATCH,
            status=JobStatus.DONE,
            target_document=sample_document,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            progress=1.0,
            cost=cost,
        )

        # Serialize to dict
        job_dict = job.model_dump(mode="json")

        assert "cost" in job_dict
        assert job_dict["cost"]["llm_tokens_input"] == 1000
        assert job_dict["cost"]["llm_tokens_output"] == 500
        assert job_dict["cost"]["llm_calls"] == 2
        assert job_dict["cost"]["ocr_pages_processed"] == 5
        assert job_dict["cost"]["estimated_cost_usd"] == 0.02
        assert job_dict["cost"]["breakdown"]["llm_cost_usd"] == 0.015
        assert job_dict["cost"]["breakdown"]["ocr_cost_usd"] == 0.005

    def test_tracker_to_pydantic_for_job(self, sample_document: Document) -> None:
        """Test converting CostTracker to use in JobContext."""
        # Simulate agent usage tracking
        tracker = CostTracker.create(model_name="gpt-4o-mini")

        usage1 = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            agent_name="FieldLabellingAgent",
            operation="link_labels_to_boxes",
        )
        usage2 = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=800,
            output_tokens=400,
            agent_name="MappingAgent",
            operation="resolve_mapping",
        )

        tracker = tracker.add_llm_usage(usage1)
        tracker = tracker.add_llm_usage(usage2)
        tracker = tracker.add_ocr_pages(3)

        # Convert to Pydantic model for JobContext
        cost_model = tracker_to_pydantic(tracker)

        # Create job with this cost
        job = JobContext(
            id="job-999",
            mode=JobMode.TRANSFER,
            status=JobStatus.DONE,
            target_document=sample_document,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            cost=cost_model,
        )

        assert job.cost.llm_tokens_input == 1800
        assert job.cost.llm_tokens_output == 900
        assert job.cost.llm_calls == 2
        assert job.cost.ocr_pages_processed == 3
        assert job.cost.estimated_cost_usd > 0

    def test_job_context_immutability_with_cost(self, sample_document: Document) -> None:
        """Test that JobContext with cost is still immutable."""
        job = JobContext(
            id="job-imm",
            mode=JobMode.SCRATCH,
            status=JobStatus.CREATED,
            target_document=sample_document,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Job should be frozen
        with pytest.raises(Exception):  # Pydantic raises ValidationError
            job.cost = CostSummaryModel.empty()  # type: ignore
