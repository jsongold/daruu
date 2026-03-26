"""Tests for cost tracking functionality."""

from datetime import datetime, timezone

import pytest
from app.config import DEFAULT_MODEL
from app.models.common import CostBreakdown, CostSummaryModel
from app.models.cost import (
    DEFAULT_LLM_PRICING,
    DEFAULT_OCR_COST_PER_PAGE,
    CostSummary,
    CostTracker,
    LLMUsage,
    tracker_to_pydantic,
)


class TestLLMUsage:
    """Tests for LLMUsage dataclass."""

    def test_create_usage_record(self) -> None:
        """Test creating an LLMUsage record."""
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            agent_name="TestAgent",
            operation="test_operation",
        )

        assert usage.model == "gpt-4o-mini"
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.agent_name == "TestAgent"
        assert usage.operation == "test_operation"
        assert usage.timestamp is not None
        assert usage.timestamp <= datetime.now(timezone.utc)

    def test_usage_is_immutable(self) -> None:
        """Test that LLMUsage is immutable."""
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=100,
            output_tokens=50,
            agent_name="TestAgent",
            operation="test",
        )

        with pytest.raises(AttributeError):
            usage.input_tokens = 200  # type: ignore


class TestCostTracker:
    """Tests for CostTracker dataclass."""

    def test_create_empty_tracker(self) -> None:
        """Test creating an empty cost tracker."""
        tracker = CostTracker.create(model_name="gpt-4o-mini")

        assert tracker.llm_tokens_input == 0
        assert tracker.llm_tokens_output == 0
        assert tracker.llm_calls == 0
        assert tracker.ocr_pages_processed == 0
        assert tracker.estimated_cost_usd == 0.0
        assert tracker.llm_usage_records == ()
        assert tracker.model_name == "gpt-4o-mini"

    def test_add_llm_usage(self) -> None:
        """Test adding LLM usage to tracker."""
        tracker = CostTracker.create()
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            agent_name="TestAgent",
            operation="test",
        )

        new_tracker = tracker.add_llm_usage(usage)

        # Original tracker unchanged (immutable)
        assert tracker.llm_tokens_input == 0
        assert tracker.llm_calls == 0

        # New tracker has updated values
        assert new_tracker.llm_tokens_input == 1000
        assert new_tracker.llm_tokens_output == 500
        assert new_tracker.llm_calls == 1
        assert len(new_tracker.llm_usage_records) == 1
        assert new_tracker.estimated_cost_usd > 0

    def test_add_multiple_llm_usages(self) -> None:
        """Test adding multiple LLM usages accumulates correctly."""
        tracker = CostTracker.create()

        usage1 = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            agent_name="Agent1",
            operation="op1",
        )
        usage2 = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=2000,
            output_tokens=1000,
            agent_name="Agent2",
            operation="op2",
        )

        tracker = tracker.add_llm_usage(usage1)
        tracker = tracker.add_llm_usage(usage2)

        assert tracker.llm_tokens_input == 3000
        assert tracker.llm_tokens_output == 1500
        assert tracker.llm_calls == 2
        assert len(tracker.llm_usage_records) == 2

    def test_add_ocr_pages(self) -> None:
        """Test adding OCR page count."""
        tracker = CostTracker.create()

        new_tracker = tracker.add_ocr_pages(10)

        assert tracker.ocr_pages_processed == 0  # Original unchanged
        assert new_tracker.ocr_pages_processed == 10
        assert new_tracker.estimated_cost_usd == 10 * DEFAULT_OCR_COST_PER_PAGE

    def test_merge_trackers(self) -> None:
        """Test merging two cost trackers."""
        tracker1 = CostTracker.create()
        tracker2 = CostTracker.create()

        usage1 = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            agent_name="Agent1",
            operation="op1",
        )
        usage2 = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=2000,
            output_tokens=1000,
            agent_name="Agent2",
            operation="op2",
        )

        tracker1 = tracker1.add_llm_usage(usage1).add_ocr_pages(5)
        tracker2 = tracker2.add_llm_usage(usage2).add_ocr_pages(3)

        merged = tracker1.merge(tracker2)

        assert merged.llm_tokens_input == 3000
        assert merged.llm_tokens_output == 1500
        assert merged.llm_calls == 2
        assert merged.ocr_pages_processed == 8
        assert len(merged.llm_usage_records) == 2

    def test_cost_calculation_gpt4o_mini(self) -> None:
        """Test cost calculation for gpt-4o-mini model."""
        tracker = CostTracker.create(model_name="gpt-4o-mini")
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=1_000_000,  # 1M tokens
            agent_name="Test",
            operation="test",
        )

        tracker = tracker.add_llm_usage(usage)

        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        expected_cost = 0.15 + 0.60
        assert abs(tracker.estimated_cost_usd - expected_cost) < 0.001

    def test_cost_calculation_gpt4o(self) -> None:
        """Test cost calculation for gpt-4o model."""
        tracker = CostTracker.create(model_name="gpt-4o")
        usage = LLMUsage.create(
            model="gpt-4o",
            input_tokens=1_000_000,  # 1M tokens
            output_tokens=1_000_000,  # 1M tokens
            agent_name="Test",
            operation="test",
        )

        tracker = tracker.add_llm_usage(usage)

        # gpt-4o: $2.50/1M input, $10.00/1M output
        expected_cost = 2.50 + 10.00
        assert abs(tracker.estimated_cost_usd - expected_cost) < 0.001

    def test_calculate_llm_cost_only(self) -> None:
        """Test calculating LLM cost component."""
        tracker = CostTracker.create(model_name="gpt-4o-mini")
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=100_000,
            output_tokens=50_000,
            agent_name="Test",
            operation="test",
        )

        tracker = tracker.add_llm_usage(usage).add_ocr_pages(10)

        # LLM cost only (not OCR)
        llm_cost = tracker.calculate_llm_cost()
        # gpt-4o-mini: (100k/1M)*0.15 + (50k/1M)*0.60 = 0.015 + 0.03 = 0.045
        expected_llm_cost = 0.015 + 0.03
        assert abs(llm_cost - expected_llm_cost) < 0.0001

    def test_calculate_ocr_cost_only(self) -> None:
        """Test calculating OCR cost component."""
        tracker = CostTracker.create()
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=100_000,
            output_tokens=50_000,
            agent_name="Test",
            operation="test",
        )

        tracker = tracker.add_llm_usage(usage).add_ocr_pages(100)

        ocr_cost = tracker.calculate_ocr_cost()
        expected_ocr_cost = 100 * DEFAULT_OCR_COST_PER_PAGE
        assert abs(ocr_cost - expected_ocr_cost) < 0.0001

    def test_to_summary_dict(self) -> None:
        """Test converting tracker to summary dictionary."""
        tracker = CostTracker.create(model_name="gpt-4o-mini")
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=500,
            agent_name="Test",
            operation="test",
        )

        tracker = tracker.add_llm_usage(usage).add_ocr_pages(5)
        summary = tracker.to_summary_dict()

        assert summary["llm_tokens_input"] == 1000
        assert summary["llm_tokens_output"] == 500
        assert summary["llm_calls"] == 1
        assert summary["ocr_pages_processed"] == 5
        assert "estimated_cost_usd" in summary
        assert "breakdown" in summary
        assert "llm_cost_usd" in summary["breakdown"]
        assert "ocr_cost_usd" in summary["breakdown"]
        assert summary["model_name"] == "gpt-4o-mini"

    def test_tracker_is_immutable(self) -> None:
        """Test that CostTracker is immutable."""
        tracker = CostTracker.create()

        with pytest.raises(AttributeError):
            tracker.llm_tokens_input = 100  # type: ignore


class TestCostSummary:
    """Tests for CostSummary dataclass."""

    def test_from_tracker(self) -> None:
        """Test creating CostSummary from CostTracker."""
        tracker = CostTracker.create(model_name="gpt-4o")
        usage = LLMUsage.create(
            model="gpt-4o",
            input_tokens=5000,
            output_tokens=2000,
            agent_name="Test",
            operation="test",
        )
        tracker = tracker.add_llm_usage(usage).add_ocr_pages(3)

        summary = CostSummary.from_tracker(tracker)

        assert summary.llm_tokens_input == 5000
        assert summary.llm_tokens_output == 2000
        assert summary.llm_calls == 1
        assert summary.ocr_pages_processed == 3
        assert summary.model_name == "gpt-4o"
        assert summary.llm_cost_usd > 0
        assert summary.ocr_cost_usd > 0
        assert summary.estimated_cost_usd == tracker.estimated_cost_usd


class TestTrackerToPydantic:
    """Tests for tracker_to_pydantic conversion function."""

    def test_convert_empty_tracker(self) -> None:
        """Test converting an empty tracker."""
        tracker = CostTracker.create()
        pydantic_model = tracker_to_pydantic(tracker)

        assert isinstance(pydantic_model, CostSummaryModel)
        assert pydantic_model.llm_tokens_input == 0
        assert pydantic_model.llm_tokens_output == 0
        assert pydantic_model.llm_calls == 0
        assert pydantic_model.ocr_pages_processed == 0
        assert pydantic_model.estimated_cost_usd == 0.0
        assert isinstance(pydantic_model.breakdown, CostBreakdown)

    def test_convert_tracker_with_usage(self) -> None:
        """Test converting a tracker with usage data."""
        tracker = CostTracker.create(model_name="gpt-4o-mini")
        usage = LLMUsage.create(
            model="gpt-4o-mini",
            input_tokens=10000,
            output_tokens=5000,
            agent_name="TestAgent",
            operation="test_op",
        )
        tracker = tracker.add_llm_usage(usage).add_ocr_pages(7)

        pydantic_model = tracker_to_pydantic(tracker)

        assert pydantic_model.llm_tokens_input == 10000
        assert pydantic_model.llm_tokens_output == 5000
        assert pydantic_model.llm_calls == 1
        assert pydantic_model.ocr_pages_processed == 7
        assert pydantic_model.model_name == "gpt-4o-mini"
        assert pydantic_model.breakdown.llm_cost_usd == tracker.calculate_llm_cost()
        assert pydantic_model.breakdown.ocr_cost_usd == tracker.calculate_ocr_cost()

    def test_pydantic_model_is_frozen(self) -> None:
        """Test that the Pydantic model is immutable."""
        tracker = CostTracker.create()
        pydantic_model = tracker_to_pydantic(tracker)

        with pytest.raises(Exception):  # Pydantic raises ValidationError
            pydantic_model.llm_tokens_input = 100  # type: ignore


class TestCostSummaryModel:
    """Tests for CostSummaryModel Pydantic model."""

    def test_empty_factory(self) -> None:
        """Test creating empty cost summary model."""
        model = CostSummaryModel.empty()

        assert model.llm_tokens_input == 0
        assert model.llm_tokens_output == 0
        assert model.llm_calls == 0
        assert model.ocr_pages_processed == 0
        assert model.estimated_cost_usd == 0.0
        assert model.breakdown.llm_cost_usd == 0.0
        assert model.breakdown.ocr_cost_usd == 0.0
        assert model.model_name == DEFAULT_MODEL

    def test_model_serialization(self) -> None:
        """Test that the model serializes to JSON correctly."""
        model = CostSummaryModel(
            llm_tokens_input=1000,
            llm_tokens_output=500,
            llm_calls=5,
            ocr_pages_processed=10,
            estimated_cost_usd=0.05,
            breakdown=CostBreakdown(llm_cost_usd=0.03, ocr_cost_usd=0.02),
            model_name="gpt-4o-mini",
        )

        json_data = model.model_dump(mode="json")

        assert json_data["llm_tokens_input"] == 1000
        assert json_data["llm_tokens_output"] == 500
        assert json_data["llm_calls"] == 5
        assert json_data["ocr_pages_processed"] == 10
        assert json_data["estimated_cost_usd"] == 0.05
        assert json_data["breakdown"]["llm_cost_usd"] == 0.03
        assert json_data["breakdown"]["ocr_cost_usd"] == 0.02
        assert json_data["model_name"] == "gpt-4o-mini"


class TestDefaultPricing:
    """Tests for default pricing constants."""

    def test_pricing_structure(self) -> None:
        """Test that pricing dictionary has expected structure."""
        assert "gpt-4o" in DEFAULT_LLM_PRICING
        assert "gpt-4o-mini" in DEFAULT_LLM_PRICING

        for model, pricing in DEFAULT_LLM_PRICING.items():
            assert "input_per_1m" in pricing
            assert "output_per_1m" in pricing
            assert pricing["input_per_1m"] > 0
            assert pricing["output_per_1m"] > 0

    def test_ocr_cost_is_reasonable(self) -> None:
        """Test that OCR cost per page is reasonable."""
        assert DEFAULT_OCR_COST_PER_PAGE > 0
        assert DEFAULT_OCR_COST_PER_PAGE < 0.1  # Less than 10 cents per page


class TestOCRRegions:
    """Tests for OCR region tracking."""

    def test_add_ocr_regions(self) -> None:
        """Test adding OCR regions to tracker."""
        from app.models.cost import DEFAULT_OCR_COST_PER_REGION

        tracker = CostTracker.create()
        new_tracker = tracker.add_ocr_regions(10)

        assert tracker.ocr_regions_processed == 0  # Original unchanged
        assert new_tracker.ocr_regions_processed == 10
        expected_cost = 10 * DEFAULT_OCR_COST_PER_REGION
        assert abs(new_tracker.estimated_cost_usd - expected_cost) < 0.0001

    def test_combined_ocr_cost(self) -> None:
        """Test combined OCR page and region cost."""
        from app.models.cost import DEFAULT_OCR_COST_PER_REGION

        tracker = CostTracker.create()
        tracker = tracker.add_ocr_pages(5).add_ocr_regions(20)

        expected_page_cost = 5 * DEFAULT_OCR_COST_PER_PAGE
        expected_region_cost = 20 * DEFAULT_OCR_COST_PER_REGION
        expected_total = expected_page_cost + expected_region_cost

        assert tracker.calculate_ocr_cost() == pytest.approx(expected_total, abs=0.0001)


class TestStorageTracking:
    """Tests for storage bytes tracking."""

    def test_add_storage_upload(self) -> None:
        """Test adding storage upload bytes."""
        from app.models.cost import DEFAULT_STORAGE_UPLOAD_COST_PER_GB

        tracker = CostTracker.create()
        # Add 1 GB of uploads
        one_gb = 1024 * 1024 * 1024
        new_tracker = tracker.add_storage_upload(one_gb)

        assert tracker.storage_bytes_uploaded == 0
        assert new_tracker.storage_bytes_uploaded == one_gb
        expected_cost = DEFAULT_STORAGE_UPLOAD_COST_PER_GB
        assert abs(new_tracker.estimated_cost_usd - expected_cost) < 0.0001

    def test_add_storage_download(self) -> None:
        """Test adding storage download bytes."""
        from app.models.cost import DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB

        tracker = CostTracker.create()
        # Add 2 GB of downloads
        two_gb = 2 * 1024 * 1024 * 1024
        new_tracker = tracker.add_storage_download(two_gb)

        assert tracker.storage_bytes_downloaded == 0
        assert new_tracker.storage_bytes_downloaded == two_gb
        expected_cost = 2 * DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB
        assert abs(new_tracker.estimated_cost_usd - expected_cost) < 0.0001

    def test_calculate_storage_cost(self) -> None:
        """Test storage cost calculation."""
        from app.models.cost import (
            DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB,
            DEFAULT_STORAGE_UPLOAD_COST_PER_GB,
        )

        tracker = CostTracker.create()
        one_gb = 1024 * 1024 * 1024
        tracker = tracker.add_storage_upload(one_gb).add_storage_download(one_gb)

        expected = DEFAULT_STORAGE_UPLOAD_COST_PER_GB + DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB
        assert tracker.calculate_storage_cost() == pytest.approx(expected, abs=0.0001)

    def test_storage_in_summary_dict(self) -> None:
        """Test that storage is included in summary dict."""
        tracker = CostTracker.create()
        one_mb = 1024 * 1024
        tracker = tracker.add_storage_upload(one_mb).add_storage_download(one_mb * 2)

        summary = tracker.to_summary_dict()
        assert summary["storage_bytes_uploaded"] == one_mb
        assert summary["storage_bytes_downloaded"] == one_mb * 2
        assert "storage_cost_usd" in summary["breakdown"]


class TestMergeWithNewFields:
    """Tests for merging trackers with new fields."""

    def test_merge_with_ocr_regions(self) -> None:
        """Test merging trackers with OCR regions."""
        tracker1 = CostTracker.create().add_ocr_regions(5)
        tracker2 = CostTracker.create().add_ocr_regions(10)

        merged = tracker1.merge(tracker2)
        assert merged.ocr_regions_processed == 15

    def test_merge_with_storage(self) -> None:
        """Test merging trackers with storage bytes."""
        one_mb = 1024 * 1024
        tracker1 = CostTracker.create().add_storage_upload(one_mb)
        tracker2 = CostTracker.create().add_storage_download(one_mb * 2)

        merged = tracker1.merge(tracker2)
        assert merged.storage_bytes_uploaded == one_mb
        assert merged.storage_bytes_downloaded == one_mb * 2

    def test_merge_all_fields(self) -> None:
        """Test merging trackers with all fields populated."""
        usage1 = LLMUsage.create("gpt-4o-mini", 100, 50, "Agent1", "op1")
        usage2 = LLMUsage.create("gpt-4o-mini", 200, 100, "Agent2", "op2")

        tracker1 = (
            CostTracker.create()
            .add_llm_usage(usage1)
            .add_ocr_pages(5)
            .add_ocr_regions(10)
            .add_storage_upload(1000)
        )
        tracker2 = (
            CostTracker.create()
            .add_llm_usage(usage2)
            .add_ocr_pages(3)
            .add_ocr_regions(5)
            .add_storage_download(2000)
        )

        merged = tracker1.merge(tracker2)

        assert merged.llm_tokens_input == 300
        assert merged.llm_tokens_output == 150
        assert merged.llm_calls == 2
        assert merged.ocr_pages_processed == 8
        assert merged.ocr_regions_processed == 15
        assert merged.storage_bytes_uploaded == 1000
        assert merged.storage_bytes_downloaded == 2000


class TestCostConfig:
    """Tests for CostConfig."""

    def test_cost_config_defaults(self) -> None:
        """Test CostConfig default values."""
        from app.config import CostConfig

        config = CostConfig()

        assert config.llm_input_cost_per_1k == 0.00015
        assert config.llm_output_cost_per_1k == 0.0006
        assert config.ocr_cost_per_page == 0.0015
        assert config.ocr_cost_per_region == 0.0003
        assert config.storage_upload_cost_per_gb == 0.02
        assert config.storage_download_cost_per_gb == 0.01
        assert config.max_cost_per_job is None
        assert config.warn_cost_threshold is None

    def test_cost_config_with_budget(self) -> None:
        """Test CostConfig with budget limits."""
        from app.config import CostConfig

        config = CostConfig(max_cost_per_job=1.0, warn_cost_threshold=0.5)

        assert config.max_cost_per_job == 1.0
        assert config.warn_cost_threshold == 0.5

    def test_get_model_pricing(self) -> None:
        """Test getting model-specific pricing."""
        from app.config import CostConfig

        config = CostConfig()

        gpt4o_pricing = config.get_model_pricing("gpt-4o")
        assert gpt4o_pricing["input_per_1m"] == 2.50
        assert gpt4o_pricing["output_per_1m"] == 10.00

        gpt4o_mini_pricing = config.get_model_pricing("gpt-4o-mini")
        assert gpt4o_mini_pricing["input_per_1m"] == 0.15
        assert gpt4o_mini_pricing["output_per_1m"] == 0.60

    def test_get_model_pricing_unknown_model(self) -> None:
        """Test fallback pricing for unknown model."""
        from app.config import CostConfig

        config = CostConfig()
        unknown_pricing = config.get_model_pricing("unknown-model")

        # Should fallback to default pricing calculated from per-1k rates
        assert unknown_pricing["input_per_1m"] == config.llm_input_cost_per_1k * 1000
        assert unknown_pricing["output_per_1m"] == config.llm_output_cost_per_1k * 1000


class TestCostTrackingUtilities:
    """Tests for cost tracking utilities."""

    def test_budget_exceeded_error(self) -> None:
        """Test BudgetExceededError exception."""
        from app.services.cost_tracking import BudgetExceededError

        error = BudgetExceededError(
            current_cost=1.5,
            budget_limit=1.0,
            operation="test_op",
        )

        assert error.current_cost == 1.5
        assert error.budget_limit == 1.0
        assert error.operation == "test_op"
        assert "Budget exceeded" in str(error)

    def test_check_budget_within_limit(self) -> None:
        """Test check_budget when within limits."""
        from app.services.cost_tracking import check_budget

        tracker = CostTracker.create()

        within_budget, warning = check_budget(tracker, "test", max_cost=1.0)
        assert within_budget is True
        assert warning is None

    def test_check_budget_exceeded(self) -> None:
        """Test check_budget when budget is exceeded."""
        from app.services.cost_tracking import BudgetExceededError, check_budget

        # Create a tracker with significant cost
        usage = LLMUsage.create("gpt-4o", 1_000_000, 1_000_000, "Test", "test")
        tracker = CostTracker.create(model_name="gpt-4o").add_llm_usage(usage)

        with pytest.raises(BudgetExceededError):
            check_budget(tracker, "test", max_cost=0.01)

    def test_check_budget_warning_threshold(self) -> None:
        """Test check_budget warning threshold."""
        from app.services.cost_tracking import check_budget

        usage = LLMUsage.create("gpt-4o-mini", 100_000, 50_000, "Test", "test")
        tracker = CostTracker.create().add_llm_usage(usage)

        # Set warning threshold lower than current cost
        within_budget, warning = check_budget(tracker, "test", max_cost=10.0, warn_threshold=0.001)
        assert within_budget is True
        assert warning is not None
        assert "warning" in warning.lower()

    def test_format_cost(self) -> None:
        """Test cost formatting utility."""
        from app.services.cost_tracking import format_cost

        assert format_cost(0.001234) == "$0.001234"
        assert format_cost(0.05) == "$0.0500"
        assert format_cost(1.50) == "$1.50"
        assert format_cost(123.45) == "$123.45"

    def test_format_bytes(self) -> None:
        """Test bytes formatting utility."""
        from app.services.cost_tracking import format_bytes

        assert format_bytes(500) == "500 B"
        assert format_bytes(1024) == "1.0 KB"
        assert format_bytes(1024 * 1024) == "1.0 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"

    def test_estimate_token_count(self) -> None:
        """Test token count estimation."""
        from app.services.cost_tracking import estimate_token_count

        # 100 characters at 4 chars/token = 25 tokens
        assert estimate_token_count("a" * 100) == 25

        # Custom chars_per_token
        assert estimate_token_count("a" * 100, chars_per_token=2.0) == 50

    def test_cost_tracking_context(self) -> None:
        """Test CostTrackingContext usage."""
        from app.services.cost_tracking import track_costs

        tracker = CostTracker.create()

        with track_costs(tracker, "test_op", "TestAgent") as ctx:
            ctx.record_llm_usage("gpt-4o-mini", 1000, 500)
            ctx.record_ocr_pages(5)
            ctx.record_ocr_regions(10)
            ctx.record_storage_upload(1024)
            ctx.record_storage_download(2048)

        new_tracker = ctx.finalize()

        assert new_tracker.llm_tokens_input == 1000
        assert new_tracker.llm_tokens_output == 500
        assert new_tracker.llm_calls == 1
        assert new_tracker.ocr_pages_processed == 5
        assert new_tracker.ocr_regions_processed == 10
        assert new_tracker.storage_bytes_uploaded == 1024
        assert new_tracker.storage_bytes_downloaded == 2048
        assert new_tracker.estimated_cost_usd > 0
