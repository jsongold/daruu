"""Cost tracking models for LLM and OCR usage.

This module provides immutable dataclasses for tracking costs associated
with LLM API calls and OCR processing in the daru-pdf pipeline.

All models use frozen=True to enforce immutability - creating new instances
for updates rather than mutating existing state.
"""

from dataclasses import dataclass, replace
from datetime import datetime, timezone


# Default pricing per 1M tokens (USD) - configurable via environment
DEFAULT_LLM_PRICING = {
    "gpt-4o": {
        "input_per_1m": 2.50,
        "output_per_1m": 10.00,
    },
    "gpt-4o-mini": {
        "input_per_1m": 0.15,
        "output_per_1m": 0.60,
    },
    "gpt-4-turbo": {
        "input_per_1m": 10.00,
        "output_per_1m": 30.00,
    },
    "gpt-3.5-turbo": {
        "input_per_1m": 0.50,
        "output_per_1m": 1.50,
    },
}

# Default OCR cost estimate per page (USD)
DEFAULT_OCR_COST_PER_PAGE = 0.0015  # Approximate cost based on cloud OCR services

# Default OCR cost estimate per region (USD)
DEFAULT_OCR_COST_PER_REGION = 0.0003  # Cost for targeted region OCR

# Default storage costs per GB (USD)
DEFAULT_STORAGE_UPLOAD_COST_PER_GB = 0.02
DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB = 0.01


@dataclass(frozen=True)
class LLMUsage:
    """Token usage from a single LLM API call.

    Immutable record of tokens consumed in an LLM request.
    Used to aggregate costs across multiple agent calls.

    Attributes:
        model: Model identifier (e.g., "gpt-4o-mini")
        input_tokens: Number of prompt/input tokens
        output_tokens: Number of completion/output tokens
        timestamp: When the call was made
        agent_name: Name of the agent that made the call
        operation: Description of the operation (e.g., "resolve_candidates")
    """

    model: str
    input_tokens: int
    output_tokens: int
    timestamp: datetime
    agent_name: str
    operation: str

    @classmethod
    def create(
        cls,
        model: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: str,
        operation: str,
    ) -> "LLMUsage":
        """Create a new LLMUsage record with current timestamp.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            agent_name: Name of the calling agent
            operation: Description of the operation

        Returns:
            New LLMUsage instance
        """
        return cls(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=datetime.now(timezone.utc),
            agent_name=agent_name,
            operation=operation,
        )


@dataclass(frozen=True)
class CostTracker:
    """Tracks cumulative costs for LLM and OCR usage in a job.

    Immutable cost accumulator - use add_* methods to create new instances
    with updated values. Never mutates existing state.

    Attributes:
        llm_tokens_input: Total input tokens across all LLM calls
        llm_tokens_output: Total output tokens across all LLM calls
        llm_calls: Number of LLM API calls made
        ocr_pages_processed: Number of pages processed by OCR
        ocr_regions_processed: Number of regions processed by targeted OCR
        storage_bytes_uploaded: Total bytes uploaded to storage
        storage_bytes_downloaded: Total bytes downloaded from storage
        estimated_cost_usd: Estimated total cost in USD
        llm_usage_records: Detailed records of individual LLM calls
        model_name: Primary model used for cost calculation
    """

    llm_tokens_input: int = 0
    llm_tokens_output: int = 0
    llm_calls: int = 0
    ocr_pages_processed: int = 0
    ocr_regions_processed: int = 0
    storage_bytes_uploaded: int = 0
    storage_bytes_downloaded: int = 0
    estimated_cost_usd: float = 0.0
    llm_usage_records: tuple[LLMUsage, ...] = ()
    model_name: str = "gpt-4o-mini"

    @classmethod
    def create(cls, model_name: str = "gpt-4o-mini") -> "CostTracker":
        """Create a new empty CostTracker.

        Args:
            model_name: Default model for cost calculations

        Returns:
            New CostTracker instance with zero values
        """
        return cls(model_name=model_name)

    def add_llm_usage(self, usage: LLMUsage) -> "CostTracker":
        """Add LLM usage and return a new CostTracker.

        Creates a new immutable CostTracker with the usage added.
        Recalculates estimated cost based on accumulated usage.

        Args:
            usage: LLM usage record to add

        Returns:
            New CostTracker with updated totals
        """
        new_input_tokens = self.llm_tokens_input + usage.input_tokens
        new_output_tokens = self.llm_tokens_output + usage.output_tokens
        new_calls = self.llm_calls + 1
        new_records = self.llm_usage_records + (usage,)

        # Calculate new estimated cost
        new_cost = self._calculate_total_cost(
            llm_tokens_input=new_input_tokens,
            llm_tokens_output=new_output_tokens,
            ocr_pages=self.ocr_pages_processed,
            model_name=usage.model or self.model_name,
            ocr_regions=self.ocr_regions_processed,
            storage_bytes_uploaded=self.storage_bytes_uploaded,
            storage_bytes_downloaded=self.storage_bytes_downloaded,
        )

        return replace(
            self,
            llm_tokens_input=new_input_tokens,
            llm_tokens_output=new_output_tokens,
            llm_calls=new_calls,
            llm_usage_records=new_records,
            estimated_cost_usd=new_cost,
        )

    def add_ocr_pages(self, page_count: int) -> "CostTracker":
        """Add OCR page processing and return a new CostTracker.

        Args:
            page_count: Number of pages processed by OCR

        Returns:
            New CostTracker with updated OCR count and cost
        """
        new_pages = self.ocr_pages_processed + page_count

        # Recalculate total cost
        new_cost = self._calculate_total_cost(
            llm_tokens_input=self.llm_tokens_input,
            llm_tokens_output=self.llm_tokens_output,
            ocr_pages=new_pages,
            model_name=self.model_name,
            ocr_regions=self.ocr_regions_processed,
            storage_bytes_uploaded=self.storage_bytes_uploaded,
            storage_bytes_downloaded=self.storage_bytes_downloaded,
        )

        return replace(
            self,
            ocr_pages_processed=new_pages,
            estimated_cost_usd=new_cost,
        )

    def add_ocr_regions(self, region_count: int) -> "CostTracker":
        """Add OCR region processing and return a new CostTracker.

        Args:
            region_count: Number of regions processed by targeted OCR

        Returns:
            New CostTracker with updated OCR region count and cost
        """
        new_regions = self.ocr_regions_processed + region_count

        # Recalculate total cost
        new_cost = self._calculate_total_cost(
            llm_tokens_input=self.llm_tokens_input,
            llm_tokens_output=self.llm_tokens_output,
            ocr_pages=self.ocr_pages_processed,
            model_name=self.model_name,
            ocr_regions=new_regions,
            storage_bytes_uploaded=self.storage_bytes_uploaded,
            storage_bytes_downloaded=self.storage_bytes_downloaded,
        )

        return replace(
            self,
            ocr_regions_processed=new_regions,
            estimated_cost_usd=new_cost,
        )

    def add_storage_upload(self, byte_count: int) -> "CostTracker":
        """Add storage upload bytes and return a new CostTracker.

        Args:
            byte_count: Number of bytes uploaded to storage

        Returns:
            New CostTracker with updated storage upload count and cost
        """
        new_bytes = self.storage_bytes_uploaded + byte_count

        # Recalculate total cost
        new_cost = self._calculate_total_cost(
            llm_tokens_input=self.llm_tokens_input,
            llm_tokens_output=self.llm_tokens_output,
            ocr_pages=self.ocr_pages_processed,
            model_name=self.model_name,
            ocr_regions=self.ocr_regions_processed,
            storage_bytes_uploaded=new_bytes,
            storage_bytes_downloaded=self.storage_bytes_downloaded,
        )

        return replace(
            self,
            storage_bytes_uploaded=new_bytes,
            estimated_cost_usd=new_cost,
        )

    def add_storage_download(self, byte_count: int) -> "CostTracker":
        """Add storage download bytes and return a new CostTracker.

        Args:
            byte_count: Number of bytes downloaded from storage

        Returns:
            New CostTracker with updated storage download count and cost
        """
        new_bytes = self.storage_bytes_downloaded + byte_count

        # Recalculate total cost
        new_cost = self._calculate_total_cost(
            llm_tokens_input=self.llm_tokens_input,
            llm_tokens_output=self.llm_tokens_output,
            ocr_pages=self.ocr_pages_processed,
            model_name=self.model_name,
            ocr_regions=self.ocr_regions_processed,
            storage_bytes_uploaded=self.storage_bytes_uploaded,
            storage_bytes_downloaded=new_bytes,
        )

        return replace(
            self,
            storage_bytes_downloaded=new_bytes,
            estimated_cost_usd=new_cost,
        )

    def merge(self, other: "CostTracker") -> "CostTracker":
        """Merge another CostTracker and return a new combined tracker.

        Useful for aggregating costs from parallel operations.

        Args:
            other: Another CostTracker to merge

        Returns:
            New CostTracker with combined totals
        """
        combined_input = self.llm_tokens_input + other.llm_tokens_input
        combined_output = self.llm_tokens_output + other.llm_tokens_output
        combined_calls = self.llm_calls + other.llm_calls
        combined_pages = self.ocr_pages_processed + other.ocr_pages_processed
        combined_regions = self.ocr_regions_processed + other.ocr_regions_processed
        combined_upload = self.storage_bytes_uploaded + other.storage_bytes_uploaded
        combined_download = self.storage_bytes_downloaded + other.storage_bytes_downloaded
        combined_records = self.llm_usage_records + other.llm_usage_records

        # Use this tracker's model for cost calculation
        new_cost = self._calculate_total_cost(
            llm_tokens_input=combined_input,
            llm_tokens_output=combined_output,
            ocr_pages=combined_pages,
            model_name=self.model_name,
            ocr_regions=combined_regions,
            storage_bytes_uploaded=combined_upload,
            storage_bytes_downloaded=combined_download,
        )

        return replace(
            self,
            llm_tokens_input=combined_input,
            llm_tokens_output=combined_output,
            llm_calls=combined_calls,
            ocr_pages_processed=combined_pages,
            ocr_regions_processed=combined_regions,
            storage_bytes_uploaded=combined_upload,
            storage_bytes_downloaded=combined_download,
            llm_usage_records=combined_records,
            estimated_cost_usd=new_cost,
        )

    @staticmethod
    def _calculate_total_cost(
        llm_tokens_input: int,
        llm_tokens_output: int,
        ocr_pages: int,
        model_name: str,
        ocr_regions: int = 0,
        storage_bytes_uploaded: int = 0,
        storage_bytes_downloaded: int = 0,
    ) -> float:
        """Calculate total estimated cost in USD.

        Args:
            llm_tokens_input: Total input tokens
            llm_tokens_output: Total output tokens
            ocr_pages: Number of OCR pages
            model_name: Model name for pricing lookup
            ocr_regions: Number of OCR regions processed
            storage_bytes_uploaded: Bytes uploaded to storage
            storage_bytes_downloaded: Bytes downloaded from storage

        Returns:
            Estimated cost in USD
        """
        # Get pricing for model, fallback to gpt-4o-mini pricing
        pricing = DEFAULT_LLM_PRICING.get(
            model_name, DEFAULT_LLM_PRICING["gpt-4o-mini"]
        )

        # Calculate LLM cost (per million tokens)
        input_cost = (llm_tokens_input / 1_000_000) * pricing["input_per_1m"]
        output_cost = (llm_tokens_output / 1_000_000) * pricing["output_per_1m"]

        # Calculate OCR cost
        ocr_page_cost = ocr_pages * DEFAULT_OCR_COST_PER_PAGE
        ocr_region_cost = ocr_regions * DEFAULT_OCR_COST_PER_REGION
        ocr_cost = ocr_page_cost + ocr_region_cost

        # Calculate storage cost (convert bytes to GB)
        bytes_per_gb = 1024 * 1024 * 1024
        upload_cost = (storage_bytes_uploaded / bytes_per_gb) * DEFAULT_STORAGE_UPLOAD_COST_PER_GB
        download_cost = (storage_bytes_downloaded / bytes_per_gb) * DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB
        storage_cost = upload_cost + download_cost

        total = input_cost + output_cost + ocr_cost + storage_cost
        return round(total, 6)  # Round to 6 decimal places for precision

    def calculate_llm_cost(self) -> float:
        """Calculate LLM cost component only.

        Returns:
            LLM cost in USD
        """
        pricing = DEFAULT_LLM_PRICING.get(
            self.model_name, DEFAULT_LLM_PRICING["gpt-4o-mini"]
        )
        input_cost = (self.llm_tokens_input / 1_000_000) * pricing["input_per_1m"]
        output_cost = (self.llm_tokens_output / 1_000_000) * pricing["output_per_1m"]
        return round(input_cost + output_cost, 6)

    def calculate_ocr_cost(self) -> float:
        """Calculate OCR cost component only.

        Returns:
            OCR cost in USD
        """
        page_cost = self.ocr_pages_processed * DEFAULT_OCR_COST_PER_PAGE
        region_cost = self.ocr_regions_processed * DEFAULT_OCR_COST_PER_REGION
        return round(page_cost + region_cost, 6)

    def calculate_storage_cost(self) -> float:
        """Calculate storage cost component only.

        Returns:
            Storage cost in USD
        """
        bytes_per_gb = 1024 * 1024 * 1024
        upload_cost = (self.storage_bytes_uploaded / bytes_per_gb) * DEFAULT_STORAGE_UPLOAD_COST_PER_GB
        download_cost = (self.storage_bytes_downloaded / bytes_per_gb) * DEFAULT_STORAGE_DOWNLOAD_COST_PER_GB
        return round(upload_cost + download_cost, 6)

    def to_summary_dict(self) -> dict:
        """Convert to a summary dictionary for API responses.

        Returns:
            Dictionary with cost summary suitable for JSON serialization
        """
        return {
            "llm_tokens_input": self.llm_tokens_input,
            "llm_tokens_output": self.llm_tokens_output,
            "llm_calls": self.llm_calls,
            "ocr_pages_processed": self.ocr_pages_processed,
            "ocr_regions_processed": self.ocr_regions_processed,
            "storage_bytes_uploaded": self.storage_bytes_uploaded,
            "storage_bytes_downloaded": self.storage_bytes_downloaded,
            "estimated_cost_usd": self.estimated_cost_usd,
            "breakdown": {
                "llm_cost_usd": self.calculate_llm_cost(),
                "ocr_cost_usd": self.calculate_ocr_cost(),
                "storage_cost_usd": self.calculate_storage_cost(),
            },
            "model_name": self.model_name,
        }


@dataclass(frozen=True)
class CostSummary:
    """Pydantic-compatible cost summary for API responses.

    Simplified representation of CostTracker for serialization.

    Attributes:
        llm_tokens_input: Total input tokens
        llm_tokens_output: Total output tokens
        llm_calls: Number of LLM calls
        ocr_pages_processed: Number of OCR pages
        ocr_regions_processed: Number of OCR regions
        storage_bytes_uploaded: Bytes uploaded
        storage_bytes_downloaded: Bytes downloaded
        estimated_cost_usd: Total estimated cost
        llm_cost_usd: LLM portion of cost
        ocr_cost_usd: OCR portion of cost
        storage_cost_usd: Storage portion of cost
        model_name: Model used for calculations
    """

    llm_tokens_input: int
    llm_tokens_output: int
    llm_calls: int
    ocr_pages_processed: int
    ocr_regions_processed: int
    storage_bytes_uploaded: int
    storage_bytes_downloaded: int
    estimated_cost_usd: float
    llm_cost_usd: float
    ocr_cost_usd: float
    storage_cost_usd: float
    model_name: str

    @classmethod
    def from_tracker(cls, tracker: CostTracker) -> "CostSummary":
        """Create a CostSummary from a CostTracker.

        Args:
            tracker: CostTracker to summarize

        Returns:
            CostSummary instance
        """
        return cls(
            llm_tokens_input=tracker.llm_tokens_input,
            llm_tokens_output=tracker.llm_tokens_output,
            llm_calls=tracker.llm_calls,
            ocr_pages_processed=tracker.ocr_pages_processed,
            ocr_regions_processed=tracker.ocr_regions_processed,
            storage_bytes_uploaded=tracker.storage_bytes_uploaded,
            storage_bytes_downloaded=tracker.storage_bytes_downloaded,
            estimated_cost_usd=tracker.estimated_cost_usd,
            llm_cost_usd=tracker.calculate_llm_cost(),
            ocr_cost_usd=tracker.calculate_ocr_cost(),
            storage_cost_usd=tracker.calculate_storage_cost(),
            model_name=tracker.model_name,
        )


def tracker_to_pydantic(tracker: CostTracker) -> "CostSummaryModel":
    """Convert a CostTracker to a Pydantic CostSummaryModel.

    Utility function for converting internal tracking data to API response format.

    Args:
        tracker: CostTracker instance

    Returns:
        CostSummaryModel suitable for JSON serialization
    """
    # Import here to avoid circular imports
    from app.models.common import CostBreakdown, CostSummaryModel

    return CostSummaryModel(
        llm_tokens_input=tracker.llm_tokens_input,
        llm_tokens_output=tracker.llm_tokens_output,
        llm_calls=tracker.llm_calls,
        ocr_pages_processed=tracker.ocr_pages_processed,
        ocr_regions_processed=tracker.ocr_regions_processed,
        storage_bytes_uploaded=tracker.storage_bytes_uploaded,
        storage_bytes_downloaded=tracker.storage_bytes_downloaded,
        estimated_cost_usd=tracker.estimated_cost_usd,
        breakdown=CostBreakdown(
            llm_cost_usd=tracker.calculate_llm_cost(),
            ocr_cost_usd=tracker.calculate_ocr_cost(),
            storage_cost_usd=tracker.calculate_storage_cost(),
        ),
        model_name=tracker.model_name,
    )
