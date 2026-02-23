"""Domain models for rule snippets — output of RuleAnalyzer.

RuleSnippets are extracted from user-provided rule documents and
injected into the FormContext to guide the FillPlanner.
"""

from pydantic import BaseModel, Field


class RuleSnippet(BaseModel):
    """A rule snippet extracted from a rule document.

    Represents a single filling rule or constraint that applies
    to one or more form fields.
    """

    rule_text: str = Field(..., description="The rule text/instruction")
    applicable_fields: tuple[str, ...] = Field(
        default=(), description="Field IDs this rule applies to (empty = all fields)"
    )
    source_document: str | None = Field(
        None, description="Source document the rule was extracted from"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in rule extraction"
    )

    model_config = {"frozen": True}
