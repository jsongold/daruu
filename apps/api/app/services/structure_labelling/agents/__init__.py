"""DEPRECATED: Agents moved to app.agents.structure_labelling.

This module is kept for backward compatibility only.
Please import from app.agents.structure_labelling instead.
"""

# Re-export from new location for backward compatibility
from app.agents.structure_labelling import LangChainFieldLabellingAgent

__all__ = ["LangChainFieldLabellingAgent"]
