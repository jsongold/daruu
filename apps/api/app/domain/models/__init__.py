"""Domain models for the To-Be autofill architecture.

Re-exports all domain model classes for convenient importing:
    from app.domain.models import FormContext, FillPlan, RenderReport
"""

from app.domain.models.correction_record import CorrectionCategory, CorrectionRecord
from app.domain.models.fill_plan import FieldFillAction, FillActionType, FillPlan
from app.domain.models.form_context import (
    DataSourceEntry,
    FormContext,
    FormFieldSpec,
    LabelCandidate,
    MappingCandidate,
)
from app.domain.models.render_report import (
    FieldRenderResult,
    RenderReport,
    RenderStatus,
    ValidationResult,
)
from app.domain.models.rule_snippet import RuleSnippet

__all__ = [
    # form_context
    "DataSourceEntry",
    "FormContext",
    "FormFieldSpec",
    "LabelCandidate",
    "MappingCandidate",
    # fill_plan
    "FieldFillAction",
    "FillActionType",
    "FillPlan",
    # render_report
    "FieldRenderResult",
    "RenderReport",
    "RenderStatus",
    "ValidationResult",
    # rule_snippet
    "RuleSnippet",
    # correction_record
    "CorrectionCategory",
    "CorrectionRecord",
]
