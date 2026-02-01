"""DEPRECATED: Agents moved to app.agents.mapping.

This module is kept for backward compatibility only.
Please import from app.agents.mapping instead.
"""

# Re-export from new location for backward compatibility
from app.agents.mapping import LangChainMappingAgent

__all__ = ["LangChainMappingAgent"]
