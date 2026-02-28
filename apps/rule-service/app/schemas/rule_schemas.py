"""Domain models and LLM output schemas for rule extraction.

Merges RuleSnippet (domain model) with ExtractedRule / ChunkAnalysisResult
(LLM output schemas) into a single module for the standalone rule service.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------


class RuleSnippet(BaseModel):
    """A rule snippet extracted from a rule document.

    Represents a single filling rule or constraint that applies
    to one or more form fields. Persisted in the rule_snippets table.
    """

    id: str | None = Field(default=None, description="Database ID (UUID)")
    document_id: str = Field(default="", description="Parent document ID")
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
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of creation",
    )

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# LLM output schemas
# ---------------------------------------------------------------------------


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
