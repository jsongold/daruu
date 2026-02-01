"""Agent interfaces and implementations for LLM-based reasoning.

This module provides Agent Ports (interfaces) following Clean Architecture:
- Agents are responsible for LLM-based reasoning, judgment, and proposals
- Agents are non-deterministic (LLM inference)
- Agents are implemented as Ports (interfaces) for easy replacement
- Services use Agents internally but don't depend on implementation details

Agents:
- FieldLabellingAgent: Links labels to positions (bbox) in documents
- ValueExtractionAgent: Resolves ambiguity, normalizes, detects conflicts
- MappingAgent: Maps source fields to target fields

Utilities:
- llm_wrapper: Helper functions for LLM calls with token tracking
"""

# DEPRECATED: Import from app.agents instead
# This redirect is provided for backward compatibility
from app.agents.ports import (
    FieldLabellingAgent,
    MappingAgent,
    ValueExtractionAgent,
)
from app.agents.llm_wrapper import (
    CostTrackingContext,
    LLMResult,
    extract_usage_from_response,
    invoke_structured_with_tracking,
    invoke_with_tracking,
)

__all__ = [
    "FieldLabellingAgent",
    "ValueExtractionAgent",
    "MappingAgent",
    # LLM wrapper utilities
    "CostTrackingContext",
    "LLMResult",
    "extract_usage_from_response",
    "invoke_structured_with_tracking",
    "invoke_with_tracking",
]
