"""Domain protocols for the To-Be autofill architecture.

Re-exports all protocol interfaces for convenient importing:
    from app.domain.protocols import FillPlannerProtocol, FormContextBuilderProtocol
"""

from app.domain.protocols.correction_tracker import CorrectionTrackerProtocol
from app.domain.protocols.fill_planner import FillPlannerProtocol
from app.domain.protocols.form_context_builder import FormContextBuilderProtocol
from app.domain.protocols.form_renderer import FormRendererProtocol
from app.domain.protocols.rule_analyzer import RuleAnalyzerProtocol

__all__ = [
    "CorrectionTrackerProtocol",
    "FillPlannerProtocol",
    "FormContextBuilderProtocol",
    "FormRendererProtocol",
    "RuleAnalyzerProtocol",
]
