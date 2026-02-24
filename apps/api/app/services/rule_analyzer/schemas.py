"""LLM output schemas for rule extraction.

Defines the structured output format expected from the LLM when
analyzing document chunks for filling rules.
"""

from pydantic import BaseModel, Field


class ExtractedRule(BaseModel):
    """A single rule extracted by the LLM from a document chunk."""

    rule_text: str = Field(..., description="The rule text/instruction")
    applicable_fields: list[str] = Field(
        default_factory=list,
        description="Field IDs this rule applies to (empty = all fields)",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in rule extraction",
    )

    model_config = {"frozen": True}


class ChunkAnalysisResult(BaseModel):
    """LLM output for a single chunk analysis."""

    rules: list[ExtractedRule] = Field(
        default_factory=list,
        description="Rules extracted from the chunk",
    )

    model_config = {"frozen": True}
