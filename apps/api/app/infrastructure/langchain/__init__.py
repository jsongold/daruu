"""LangChain infrastructure adapters.

This package provides LangChain-based implementations of the LLM Gateway.
LangChain is used for:
- Model provider abstraction (OpenAI, Anthropic, Google, etc.)
- Agent construction with tools
- Structured output parsing
"""

from app.infrastructure.langchain.agent import LangChainLLMGateway

__all__ = [
    "LangChainLLMGateway",
]
