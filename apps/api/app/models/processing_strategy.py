"""Processing strategy configuration for hybrid services.

This module defines the strategy pattern for services that can operate in
different modes (local-only, LLM-only, hybrid, or LLM with local fallback).

The strategy determines how services coordinate between deterministic
(local) processing and LLM-based reasoning.

Strategies:
- LOCAL_ONLY: Use only deterministic processing (fastest, no LLM costs)
- LLM_ONLY: Use only LLM-based processing (most semantic understanding)
- HYBRID: Local first, then LLM for enhancement (default, balanced)
- LLM_WITH_LOCAL_FALLBACK: LLM first, fall back to local if it fails
"""

from dataclasses import dataclass
from enum import Enum


class ProcessingStrategy(str, Enum):
    """Strategy for coordinating local and LLM processing.

    Each hybrid service (StructureLabelling, Mapping, Extract) can be
    configured with a strategy to control how it balances deterministic
    and LLM-based processing.

    Attributes:
        LOCAL_ONLY: Use only deterministic/local processing.
            - StructureLabelling: OpenCV detection only, no label linking
            - Mapping: RapidFuzz matching only, no ambiguity resolution
            - Extract: Native text extraction only, no normalization

        LLM_ONLY: Use only LLM-based processing.
            - StructureLabelling: Skip detection, LLM does all linking
            - Mapping: LLM infers all mappings, no fuzzy matching
            - Extract: LLM extracts and normalizes values

        HYBRID: Local first, then LLM for enhancement (default).
            - StructureLabelling: Detect structures, then LLM links labels
            - Mapping: Fuzzy match first, LLM resolves ambiguities
            - Extract: Native text first, LLM normalizes and resolves

        LLM_WITH_LOCAL_FALLBACK: Try LLM first, fall back to local on failure.
            - Same as HYBRID but inverted priority
            - Useful when LLM quality is more important than speed
            - Falls back gracefully if LLM is unavailable or fails
    """

    LOCAL_ONLY = "local_only"
    LLM_ONLY = "llm_only"
    HYBRID = "hybrid"
    LLM_WITH_LOCAL_FALLBACK = "llm_with_local_fallback"


@dataclass(frozen=True)
class StrategyConfig:
    """Configuration for a processing strategy.

    Immutable configuration object that can be passed to services
    to control their processing behavior.

    Attributes:
        strategy: The processing strategy to use
        skip_llm_on_high_confidence: When True, skip LLM if local
            processing achieves high confidence (HYBRID mode optimization)
        high_confidence_threshold: Confidence threshold above which
            LLM can be skipped (default 0.9)
        llm_timeout_seconds: Timeout for LLM operations (default 30)
        fallback_on_llm_error: Whether to fall back to local on LLM error
        max_llm_retries: Maximum retries for LLM operations (default 2)
    """

    strategy: ProcessingStrategy = ProcessingStrategy.HYBRID
    skip_llm_on_high_confidence: bool = True
    high_confidence_threshold: float = 0.9
    llm_timeout_seconds: int = 30
    fallback_on_llm_error: bool = True
    max_llm_retries: int = 2

    def should_use_local(self) -> bool:
        """Check if local processing should be used.

        Returns:
            True if the strategy includes local processing
        """
        return self.strategy in (
            ProcessingStrategy.LOCAL_ONLY,
            ProcessingStrategy.HYBRID,
            ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
        )

    def should_use_llm(self) -> bool:
        """Check if LLM processing should be used.

        Returns:
            True if the strategy includes LLM processing
        """
        return self.strategy in (
            ProcessingStrategy.LLM_ONLY,
            ProcessingStrategy.HYBRID,
            ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
        )

    def is_local_first(self) -> bool:
        """Check if local processing should run before LLM.

        Returns:
            True if local processing has priority
        """
        return self.strategy in (
            ProcessingStrategy.LOCAL_ONLY,
            ProcessingStrategy.HYBRID,
        )

    def is_llm_first(self) -> bool:
        """Check if LLM processing should run before local.

        Returns:
            True if LLM processing has priority
        """
        return self.strategy in (
            ProcessingStrategy.LLM_ONLY,
            ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
        )

    def should_fallback_on_error(self) -> bool:
        """Check if fallback is enabled on LLM error.

        Returns:
            True if fallback to local is enabled on LLM failure
        """
        return (
            self.fallback_on_llm_error
            and self.strategy == ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK
        )


# Default strategy configurations for common use cases
DEFAULT_STRATEGY = StrategyConfig(strategy=ProcessingStrategy.HYBRID)

FAST_LOCAL_STRATEGY = StrategyConfig(
    strategy=ProcessingStrategy.LOCAL_ONLY,
    skip_llm_on_high_confidence=False,
)

FULL_LLM_STRATEGY = StrategyConfig(
    strategy=ProcessingStrategy.LLM_ONLY,
    skip_llm_on_high_confidence=False,
    llm_timeout_seconds=60,
    max_llm_retries=3,
)

RESILIENT_STRATEGY = StrategyConfig(
    strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
    fallback_on_llm_error=True,
    llm_timeout_seconds=30,
    max_llm_retries=2,
)
