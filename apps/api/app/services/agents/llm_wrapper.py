"""LLM wrapper for tracking token usage.

This module provides utilities for wrapping LLM calls to extract
and track token usage for cost estimation.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TypeVar

from langchain_core.messages import BaseMessage

from app.models.cost import CostTracker, LLMUsage

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class LLMResult:
    """Result from an LLM call with usage tracking.

    Immutable container for LLM response and token usage.

    Attributes:
        content: The response content from the LLM
        usage: Token usage record for this call
        raw_response: Raw response object from LangChain (optional)
    """

    content: Any
    usage: LLMUsage
    raw_response: Any = None


def extract_usage_from_response(
    response: Any,
    model: str,
    agent_name: str,
    operation: str,
) -> LLMUsage:
    """Extract token usage from a LangChain response.

    Handles various response formats from different LangChain LLMs.

    Args:
        response: Response object from LangChain
        model: Model name used for the call
        agent_name: Name of the agent making the call
        operation: Description of the operation

    Returns:
        LLMUsage record with extracted token counts
    """
    input_tokens = 0
    output_tokens = 0

    # Try to extract usage from response metadata
    if hasattr(response, "response_metadata"):
        metadata = response.response_metadata
        if isinstance(metadata, dict):
            # OpenAI format
            token_usage = metadata.get("token_usage", {})
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)
            else:
                # Alternative OpenAI format
                usage = metadata.get("usage", {})
                if usage:
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

    # Try usage_metadata (newer LangChain format)
    if input_tokens == 0 and hasattr(response, "usage_metadata"):
        usage_meta = response.usage_metadata
        if usage_meta:
            input_tokens = getattr(usage_meta, "input_tokens", 0) or 0
            output_tokens = getattr(usage_meta, "output_tokens", 0) or 0

    # Try direct attributes
    if input_tokens == 0:
        if hasattr(response, "llm_output") and response.llm_output:
            llm_output = response.llm_output
            if isinstance(llm_output, dict):
                token_usage = llm_output.get("token_usage", {})
                input_tokens = token_usage.get("prompt_tokens", 0)
                output_tokens = token_usage.get("completion_tokens", 0)

    return LLMUsage.create(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        agent_name=agent_name,
        operation=operation,
    )


async def invoke_with_tracking(
    llm: Any,
    messages: list[BaseMessage],
    model: str,
    agent_name: str,
    operation: str,
) -> LLMResult:
    """Invoke LLM and track token usage.

    Wraps a LangChain LLM call to extract and return usage information.

    Args:
        llm: LangChain LLM instance
        messages: Messages to send to the LLM
        model: Model name for tracking
        agent_name: Name of the calling agent
        operation: Description of the operation

    Returns:
        LLMResult with content and usage tracking

    Raises:
        Exception: Any exception from the LLM call is re-raised
    """
    response = await llm.ainvoke(messages)

    usage = extract_usage_from_response(
        response=response,
        model=model,
        agent_name=agent_name,
        operation=operation,
    )

    # Extract content from response
    content = response.content if hasattr(response, "content") else response

    return LLMResult(
        content=content,
        usage=usage,
        raw_response=response,
    )


async def invoke_structured_with_tracking(
    llm: Any,
    messages: list[BaseMessage],
    output_schema: type[T],
    model: str,
    agent_name: str,
    operation: str,
) -> tuple[T, LLMUsage]:
    """Invoke LLM with structured output and track token usage.

    Uses LangChain's with_structured_output for reliable parsing.

    Args:
        llm: LangChain LLM instance
        messages: Messages to send to the LLM
        output_schema: Pydantic model for structured output
        model: Model name for tracking
        agent_name: Name of the calling agent
        operation: Description of the operation

    Returns:
        Tuple of (parsed_output, usage)

    Raises:
        Exception: Any exception from the LLM call is re-raised
    """
    structured_llm = llm.with_structured_output(output_schema)
    response = await structured_llm.ainvoke(messages)

    # For structured output, we need to get usage differently
    # The response is the parsed model, not the raw response
    # We need to estimate based on the structured output size
    usage = LLMUsage.create(
        model=model,
        input_tokens=_estimate_input_tokens(messages),
        output_tokens=_estimate_output_tokens(response),
        agent_name=agent_name,
        operation=operation,
    )

    return response, usage


def _estimate_input_tokens(messages: list[BaseMessage]) -> int:
    """Estimate input tokens from messages.

    Uses a rough approximation of 4 characters per token.

    Args:
        messages: List of messages

    Returns:
        Estimated token count
    """
    total_chars = 0
    for msg in messages:
        content = msg.content if hasattr(msg, "content") else str(msg)
        total_chars += len(content)

    # Rough estimate: ~4 chars per token, plus overhead for message formatting
    return max(1, int(total_chars / 4) + len(messages) * 10)


def _estimate_output_tokens(response: Any) -> int:
    """Estimate output tokens from response.

    Uses a rough approximation based on the serialized response size.

    Args:
        response: Response object (can be Pydantic model or string)

    Returns:
        Estimated token count
    """
    try:
        if hasattr(response, "model_dump_json"):
            # Pydantic model
            json_str = response.model_dump_json()
            return max(1, int(len(json_str) / 4))
        elif hasattr(response, "json"):
            # Legacy Pydantic
            json_str = response.json()
            return max(1, int(len(json_str) / 4))
        elif isinstance(response, str):
            return max(1, int(len(response) / 4))
        else:
            # Fallback: serialize to string
            return max(1, int(len(str(response)) / 4))
    except Exception:
        # Default estimate if serialization fails
        return 100


class CostTrackingContext:
    """Context manager for tracking costs across multiple LLM calls.

    Provides a thread-safe way to accumulate costs across operations.

    Example:
        async with CostTrackingContext("gpt-4o-mini") as ctx:
            result1 = await ctx.invoke(llm, messages, "agent1", "op1")
            result2 = await ctx.invoke(llm, messages, "agent2", "op2")
            total_cost = ctx.tracker
    """

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        """Initialize tracking context.

        Args:
            model_name: Default model name for cost calculations
        """
        self._tracker = CostTracker.create(model_name=model_name)
        self._model_name = model_name

    @property
    def tracker(self) -> CostTracker:
        """Get current cost tracker."""
        return self._tracker

    def add_usage(self, usage: LLMUsage) -> None:
        """Add usage to the tracker.

        Args:
            usage: LLM usage record to add
        """
        self._tracker = self._tracker.add_llm_usage(usage)

    def add_ocr_pages(self, page_count: int) -> None:
        """Add OCR pages to the tracker.

        Args:
            page_count: Number of pages processed
        """
        self._tracker = self._tracker.add_ocr_pages(page_count)

    async def invoke(
        self,
        llm: Any,
        messages: list[BaseMessage],
        agent_name: str,
        operation: str,
    ) -> Any:
        """Invoke LLM and automatically track usage.

        Args:
            llm: LangChain LLM instance
            messages: Messages to send
            agent_name: Name of the calling agent
            operation: Description of the operation

        Returns:
            LLM response content
        """
        result = await invoke_with_tracking(
            llm=llm,
            messages=messages,
            model=self._model_name,
            agent_name=agent_name,
            operation=operation,
        )
        self._tracker = self._tracker.add_llm_usage(result.usage)
        return result.content

    async def __aenter__(self) -> "CostTrackingContext":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        pass
