"""DEPRECATED: Agents moved to app.agents.extract.

This module is kept for backward compatibility only.
Please import from app.agents.extract instead.
"""

# Re-export from new location for backward compatibility
from app.agents.extract import LangChainValueExtractionAgent

__all__ = ["LangChainValueExtractionAgent"]
