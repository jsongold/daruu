"""Cost tracking utilities for LLM and OCR operations.

This module provides decorators and context managers for tracking costs
associated with LLM API calls, OCR processing, and storage operations.

All utilities follow immutable patterns - they return new CostTracker instances
rather than mutating existing state.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

from app.config import get_cost_config
from app.models.cost import CostTracker, LLMUsage


# =============================================================================
# Exceptions
# =============================================================================


class BudgetExceededError(Exception):
    """Raised when a job's cost exceeds the configured budget limit."""

    def __init__(
        self,
        current_cost: float,
        budget_limit: float,
        operation: str = "unknown",
    ) -> None:
        self.current_cost = current_cost
        self.budget_limit = budget_limit
        self.operation = operation
        super().__init__(
            f"Budget exceeded during {operation}: "
            f"current cost ${current_cost:.6f} exceeds limit ${budget_limit:.6f}"
        )


class CostWarningThresholdReached(Exception):
    """Warning raised when cost approaches the configured threshold.

    This is a non-fatal warning that can be caught and logged.
    """

    def __init__(self, current_cost: float, threshold: float) -> None:
        self.current_cost = current_cost
        self.threshold = threshold
        super().__init__(
            f"Cost warning threshold reached: "
            f"current cost ${current_cost:.6f} exceeds threshold ${threshold:.6f}"
        )


# =============================================================================
# Budget Enforcement
# =============================================================================


def check_budget(
    tracker: CostTracker,
    operation: str = "unknown",
    max_cost: float | None = None,
    warn_threshold: float | None = None,
) -> tuple[bool, str | None]:
    """Check if the current cost is within budget limits.

    Args:
        tracker: Current cost tracker.
        operation: Description of the operation for error messages.
        max_cost: Optional override for max cost per job.
        warn_threshold: Optional override for warning threshold.

    Returns:
        Tuple of (is_within_budget, warning_message).
        If is_within_budget is False, raises BudgetExceededError.

    Raises:
        BudgetExceededError: If current cost exceeds the budget limit.
    """
    config = get_cost_config()
    budget_limit = max_cost if max_cost is not None else config.max_cost_per_job
    warning_threshold = (
        warn_threshold if warn_threshold is not None else config.warn_cost_threshold
    )

    current_cost = tracker.estimated_cost_usd
    warning_message: str | None = None

    # Check hard budget limit
    if budget_limit is not None and current_cost > budget_limit:
        raise BudgetExceededError(
            current_cost=current_cost,
            budget_limit=budget_limit,
            operation=operation,
        )

    # Check warning threshold
    if warning_threshold is not None and current_cost > warning_threshold:
        warning_message = (
            f"Cost warning: ${current_cost:.6f} exceeds threshold ${warning_threshold:.6f}"
        )

    return True, warning_message


def enforce_budget(
    tracker: CostTracker,
    operation: str = "unknown",
) -> CostTracker:
    """Enforce budget limits on a cost tracker.

    This is a convenience function that checks the budget and returns
    the tracker unchanged if within limits.

    Args:
        tracker: Current cost tracker.
        operation: Description of the operation.

    Returns:
        The same tracker if within budget.

    Raises:
        BudgetExceededError: If budget is exceeded.
    """
    check_budget(tracker, operation)
    return tracker


# =============================================================================
# Context Managers
# =============================================================================


@dataclass
class CostTrackingContext:
    """Context for accumulating costs during an operation."""

    tracker: CostTracker
    operation: str
    agent_name: str
    _llm_usage: LLMUsage | None = None
    _ocr_pages: int = 0
    _ocr_regions: int = 0
    _storage_uploaded: int = 0
    _storage_downloaded: int = 0

    def record_llm_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record LLM usage for this context.

        Args:
            model: Model identifier.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
        """
        self._llm_usage = LLMUsage.create(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            agent_name=self.agent_name,
            operation=self.operation,
        )

    def record_ocr_pages(self, page_count: int) -> None:
        """Record OCR page processing.

        Args:
            page_count: Number of pages processed.
        """
        self._ocr_pages += page_count

    def record_ocr_regions(self, region_count: int) -> None:
        """Record OCR region processing.

        Args:
            region_count: Number of regions processed.
        """
        self._ocr_regions += region_count

    def record_storage_upload(self, byte_count: int) -> None:
        """Record storage upload.

        Args:
            byte_count: Number of bytes uploaded.
        """
        self._storage_uploaded += byte_count

    def record_storage_download(self, byte_count: int) -> None:
        """Record storage download.

        Args:
            byte_count: Number of bytes downloaded.
        """
        self._storage_downloaded += byte_count

    def finalize(self) -> CostTracker:
        """Finalize the context and return the updated tracker.

        Returns:
            New CostTracker with all recorded costs.
        """
        result = self.tracker

        if self._llm_usage is not None:
            result = result.add_llm_usage(self._llm_usage)

        if self._ocr_pages > 0:
            result = result.add_ocr_pages(self._ocr_pages)

        if self._ocr_regions > 0:
            result = result.add_ocr_regions(self._ocr_regions)

        if self._storage_uploaded > 0:
            result = result.add_storage_upload(self._storage_uploaded)

        if self._storage_downloaded > 0:
            result = result.add_storage_download(self._storage_downloaded)

        return result


@contextmanager
def track_costs(
    tracker: CostTracker,
    operation: str,
    agent_name: str = "unknown",
    enforce_budget_on_exit: bool = True,
) -> Generator[CostTrackingContext, None, None]:
    """Context manager for tracking costs during an operation.

    Usage:
        tracker = CostTracker.create()
        with track_costs(tracker, "extract_values", "ExtractAgent") as ctx:
            # ... do work ...
            ctx.record_llm_usage("gpt-4o-mini", 1000, 500)
            ctx.record_ocr_pages(5)

        # Get the updated tracker
        new_tracker = ctx.finalize()

    Args:
        tracker: Initial cost tracker.
        operation: Description of the operation.
        agent_name: Name of the agent performing the operation.
        enforce_budget_on_exit: Whether to check budget limits on exit.

    Yields:
        CostTrackingContext for recording costs.

    Raises:
        BudgetExceededError: If budget is exceeded (when enforce_budget_on_exit=True).
    """
    ctx = CostTrackingContext(
        tracker=tracker,
        operation=operation,
        agent_name=agent_name,
    )
    yield ctx

    # Finalize is called by the caller to get the updated tracker
    # We don't automatically update the tracker here since it's immutable


@contextmanager
def track_llm_call(
    tracker: CostTracker,
    model: str,
    agent_name: str,
    operation: str,
) -> Generator[dict[str, Any], None, None]:
    """Context manager for tracking a single LLM call.

    Usage:
        with track_llm_call(tracker, "gpt-4o-mini", "MapAgent", "resolve") as usage:
            response = await llm.call(...)
            usage["input_tokens"] = response.usage.prompt_tokens
            usage["output_tokens"] = response.usage.completion_tokens

        new_tracker = tracker.add_llm_usage(usage["record"])

    Args:
        tracker: Current cost tracker.
        model: Model identifier.
        agent_name: Name of the calling agent.
        operation: Description of the operation.

    Yields:
        Dictionary to record token counts. Will contain "record" key with
        LLMUsage after exit.
    """
    usage_data: dict[str, Any] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "record": None,
    }
    yield usage_data

    # Create the usage record after the context exits
    usage_data["record"] = LLMUsage.create(
        model=model,
        input_tokens=usage_data["input_tokens"],
        output_tokens=usage_data["output_tokens"],
        agent_name=agent_name,
        operation=operation,
    )


# =============================================================================
# Decorators
# =============================================================================


F = TypeVar("F", bound=Callable[..., Any])


def track_llm_usage(
    model: str,
    agent_name: str,
    operation: str,
) -> Callable[[F], F]:
    """Decorator for tracking LLM usage on a function.

    The decorated function must accept a 'tracker' keyword argument
    and return a tuple of (result, updated_tracker).

    Usage:
        @track_llm_usage("gpt-4o-mini", "MapAgent", "resolve_candidates")
        async def resolve_candidates(self, candidates: list, tracker: CostTracker):
            response = await self.llm.call(...)
            # The decorator will extract token usage from response.usage
            return result, tracker

    Note: This decorator is a placeholder for integration with specific
    LLM client implementations. The actual token extraction logic
    depends on the LLM client being used.

    Args:
        model: Model identifier.
        agent_name: Name of the agent.
        operation: Description of the operation.

    Returns:
        Decorated function.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get the tracker from kwargs if present
            tracker = kwargs.get("tracker")
            if tracker is None:
                # No tracker, just call the function
                return await func(*args, **kwargs)

            # Call the function and get the result
            result = await func(*args, **kwargs)

            # If the result contains usage information, update the tracker
            # This is a pattern - the actual implementation depends on the LLM client
            if hasattr(result, "usage") and result.usage is not None:
                usage = LLMUsage.create(
                    model=model,
                    input_tokens=getattr(result.usage, "prompt_tokens", 0),
                    output_tokens=getattr(result.usage, "completion_tokens", 0),
                    agent_name=agent_name,
                    operation=operation,
                )
                new_tracker = tracker.add_llm_usage(usage)
                return result, new_tracker

            return result

        return wrapper  # type: ignore
    return decorator


# =============================================================================
# Utility Functions
# =============================================================================


def estimate_token_count(text: str, chars_per_token: float = 4.0) -> int:
    """Estimate the number of tokens in a text string.

    This is a rough estimate based on character count.
    For accurate counts, use the tokenizer for the specific model.

    Args:
        text: Input text.
        chars_per_token: Average characters per token (default 4.0 for English).

    Returns:
        Estimated token count.
    """
    return int(len(text) / chars_per_token)


def format_cost(cost_usd: float) -> str:
    """Format a cost value for display.

    Args:
        cost_usd: Cost in USD.

    Returns:
        Formatted string like "$0.001234" or "$1.23".
    """
    if cost_usd < 0.01:
        return f"${cost_usd:.6f}"
    elif cost_usd < 1.0:
        return f"${cost_usd:.4f}"
    else:
        return f"${cost_usd:.2f}"


def format_bytes(byte_count: int) -> str:
    """Format a byte count for display.

    Args:
        byte_count: Number of bytes.

    Returns:
        Formatted string like "1.5 MB" or "256 KB".
    """
    if byte_count < 1024:
        return f"{byte_count} B"
    elif byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f} KB"
    elif byte_count < 1024 * 1024 * 1024:
        return f"{byte_count / (1024 * 1024):.1f} MB"
    else:
        return f"{byte_count / (1024 * 1024 * 1024):.2f} GB"
