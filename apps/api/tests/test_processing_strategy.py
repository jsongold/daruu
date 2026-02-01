"""Tests for processing strategy configuration and behavior.

Tests the ProcessingStrategy enum, StrategyConfig dataclass,
and integration with hybrid services.
"""

import pytest

from app.models.processing_strategy import (
    DEFAULT_STRATEGY,
    FAST_LOCAL_STRATEGY,
    FULL_LLM_STRATEGY,
    RESILIENT_STRATEGY,
    ProcessingStrategy,
    StrategyConfig,
)


class TestProcessingStrategyEnum:
    """Tests for ProcessingStrategy enum values and behavior."""

    def test_enum_values(self):
        """Test that all expected strategy values exist."""
        assert ProcessingStrategy.LOCAL_ONLY.value == "local_only"
        assert ProcessingStrategy.LLM_ONLY.value == "llm_only"
        assert ProcessingStrategy.HYBRID.value == "hybrid"
        assert ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK.value == "llm_with_local_fallback"

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        assert ProcessingStrategy("local_only") == ProcessingStrategy.LOCAL_ONLY
        assert ProcessingStrategy("llm_only") == ProcessingStrategy.LLM_ONLY
        assert ProcessingStrategy("hybrid") == ProcessingStrategy.HYBRID
        assert ProcessingStrategy("llm_with_local_fallback") == ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK

    def test_invalid_string_raises_error(self):
        """Test that invalid string raises ValueError."""
        with pytest.raises(ValueError):
            ProcessingStrategy("invalid_strategy")


class TestStrategyConfig:
    """Tests for StrategyConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = StrategyConfig()
        assert config.strategy == ProcessingStrategy.HYBRID
        assert config.skip_llm_on_high_confidence is True
        assert config.high_confidence_threshold == 0.9
        assert config.llm_timeout_seconds == 30
        assert config.fallback_on_llm_error is True
        assert config.max_llm_retries == 2

    def test_custom_values(self):
        """Test creating config with custom values."""
        config = StrategyConfig(
            strategy=ProcessingStrategy.LOCAL_ONLY,
            skip_llm_on_high_confidence=False,
            high_confidence_threshold=0.8,
            llm_timeout_seconds=60,
            fallback_on_llm_error=False,
            max_llm_retries=5,
        )
        assert config.strategy == ProcessingStrategy.LOCAL_ONLY
        assert config.skip_llm_on_high_confidence is False
        assert config.high_confidence_threshold == 0.8
        assert config.llm_timeout_seconds == 60
        assert config.fallback_on_llm_error is False
        assert config.max_llm_retries == 5

    def test_immutability(self):
        """Test that StrategyConfig is immutable (frozen)."""
        config = StrategyConfig()
        with pytest.raises(AttributeError):
            config.strategy = ProcessingStrategy.LOCAL_ONLY

    def test_should_use_local(self):
        """Test should_use_local() method for each strategy."""
        # LOCAL_ONLY should use local
        config = StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY)
        assert config.should_use_local() is True

        # LLM_ONLY should NOT use local
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_ONLY)
        assert config.should_use_local() is False

        # HYBRID should use local
        config = StrategyConfig(strategy=ProcessingStrategy.HYBRID)
        assert config.should_use_local() is True

        # LLM_WITH_LOCAL_FALLBACK should use local
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK)
        assert config.should_use_local() is True

    def test_should_use_llm(self):
        """Test should_use_llm() method for each strategy."""
        # LOCAL_ONLY should NOT use LLM
        config = StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY)
        assert config.should_use_llm() is False

        # LLM_ONLY should use LLM
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_ONLY)
        assert config.should_use_llm() is True

        # HYBRID should use LLM
        config = StrategyConfig(strategy=ProcessingStrategy.HYBRID)
        assert config.should_use_llm() is True

        # LLM_WITH_LOCAL_FALLBACK should use LLM
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK)
        assert config.should_use_llm() is True

    def test_is_local_first(self):
        """Test is_local_first() method for each strategy."""
        # LOCAL_ONLY is local-first
        config = StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY)
        assert config.is_local_first() is True

        # LLM_ONLY is NOT local-first
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_ONLY)
        assert config.is_local_first() is False

        # HYBRID is local-first
        config = StrategyConfig(strategy=ProcessingStrategy.HYBRID)
        assert config.is_local_first() is True

        # LLM_WITH_LOCAL_FALLBACK is NOT local-first
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK)
        assert config.is_local_first() is False

    def test_is_llm_first(self):
        """Test is_llm_first() method for each strategy."""
        # LOCAL_ONLY is NOT LLM-first
        config = StrategyConfig(strategy=ProcessingStrategy.LOCAL_ONLY)
        assert config.is_llm_first() is False

        # LLM_ONLY is LLM-first
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_ONLY)
        assert config.is_llm_first() is True

        # HYBRID is NOT LLM-first
        config = StrategyConfig(strategy=ProcessingStrategy.HYBRID)
        assert config.is_llm_first() is False

        # LLM_WITH_LOCAL_FALLBACK is LLM-first
        config = StrategyConfig(strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK)
        assert config.is_llm_first() is True

    def test_should_fallback_on_error(self):
        """Test should_fallback_on_error() method."""
        # LLM_WITH_LOCAL_FALLBACK with fallback enabled
        config = StrategyConfig(
            strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
            fallback_on_llm_error=True,
        )
        assert config.should_fallback_on_error() is True

        # LLM_WITH_LOCAL_FALLBACK with fallback disabled
        config = StrategyConfig(
            strategy=ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK,
            fallback_on_llm_error=False,
        )
        assert config.should_fallback_on_error() is False

        # Other strategies should not fallback (even with flag enabled)
        for strategy in [
            ProcessingStrategy.LOCAL_ONLY,
            ProcessingStrategy.LLM_ONLY,
            ProcessingStrategy.HYBRID,
        ]:
            config = StrategyConfig(strategy=strategy, fallback_on_llm_error=True)
            assert config.should_fallback_on_error() is False


class TestPresetConfigurations:
    """Tests for preset strategy configurations."""

    def test_default_strategy(self):
        """Test DEFAULT_STRATEGY preset."""
        assert DEFAULT_STRATEGY.strategy == ProcessingStrategy.HYBRID
        assert DEFAULT_STRATEGY.should_use_local() is True
        assert DEFAULT_STRATEGY.should_use_llm() is True
        assert DEFAULT_STRATEGY.is_local_first() is True

    def test_fast_local_strategy(self):
        """Test FAST_LOCAL_STRATEGY preset."""
        assert FAST_LOCAL_STRATEGY.strategy == ProcessingStrategy.LOCAL_ONLY
        assert FAST_LOCAL_STRATEGY.should_use_local() is True
        assert FAST_LOCAL_STRATEGY.should_use_llm() is False
        assert FAST_LOCAL_STRATEGY.skip_llm_on_high_confidence is False

    def test_full_llm_strategy(self):
        """Test FULL_LLM_STRATEGY preset."""
        assert FULL_LLM_STRATEGY.strategy == ProcessingStrategy.LLM_ONLY
        assert FULL_LLM_STRATEGY.should_use_local() is False
        assert FULL_LLM_STRATEGY.should_use_llm() is True
        assert FULL_LLM_STRATEGY.llm_timeout_seconds == 60
        assert FULL_LLM_STRATEGY.max_llm_retries == 3

    def test_resilient_strategy(self):
        """Test RESILIENT_STRATEGY preset."""
        assert RESILIENT_STRATEGY.strategy == ProcessingStrategy.LLM_WITH_LOCAL_FALLBACK
        assert RESILIENT_STRATEGY.should_use_local() is True
        assert RESILIENT_STRATEGY.should_use_llm() is True
        assert RESILIENT_STRATEGY.is_llm_first() is True
        assert RESILIENT_STRATEGY.should_fallback_on_error() is True


class TestConfigIntegration:
    """Tests for config.py strategy configuration."""

    def test_get_strategy_config_default(self):
        """Test getting default strategy config from settings."""
        from app.config import get_strategy_config

        config = get_strategy_config()
        # Default is HYBRID as per config.py
        assert config.strategy == ProcessingStrategy.HYBRID

    def test_get_strategy_config_for_service(self):
        """Test getting strategy config for specific services."""
        from app.config import get_strategy_config

        # These should work without errors
        structure_config = get_strategy_config("structure_labelling")
        mapping_config = get_strategy_config("mapping")
        extract_config = get_strategy_config("extract")

        # All should return valid configs
        assert isinstance(structure_config, StrategyConfig)
        assert isinstance(mapping_config, StrategyConfig)
        assert isinstance(extract_config, StrategyConfig)
