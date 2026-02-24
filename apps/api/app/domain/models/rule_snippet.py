"""Domain models for rule snippets — output of RuleAnalyzer.

RuleSnippets are extracted from user-provided rule documents and
persisted in the database for semantic search via vector embeddings.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


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
