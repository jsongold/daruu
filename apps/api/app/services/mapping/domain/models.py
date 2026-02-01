"""Domain models for the Mapping service.

All models use frozen=True for immutability, following project conventions.
These are pure domain models without infrastructure dependencies.
"""

from enum import Enum

from pydantic import BaseModel, Field


class MappingType(str, Enum):
    """Type of field mapping relationship."""

    ONE_TO_ONE = "one_to_one"  # Single source field to single target field
    ONE_TO_MANY = "one_to_many"  # Single source field to multiple target fields
    MANY_TO_ONE = "many_to_one"  # Multiple source fields to single target field
    TABLE_ROW = "table_row"  # Table row correspondence


class MappingReason(str, Enum):
    """Reason for how a mapping was determined."""

    EXACT_MATCH = "exact_match"  # Field names matched exactly
    FUZZY_MATCH = "fuzzy_match"  # Field names matched via fuzzy string matching
    FUZZY_MATCH_AMBIGUOUS = "fuzzy_match_ambiguous"  # Fuzzy match with ambiguity (local-only)
    SEMANTIC_MATCH = "semantic_match"  # Fields matched via LLM semantic understanding
    USER_RULE = "user_rule"  # Mapping derived from explicit user-defined rule
    TEMPLATE_HISTORY = "template_history"  # Mapping inferred from previous template usage
    LLM_INFERENCE = "llm_inference"  # LLM inferred the mapping from context


class MappingCandidate(BaseModel):
    """A candidate mapping between source and target fields.

    Represents a potential correspondence before final decision.
    Multiple candidates may exist for a single source/target field.
    """

    source_field_id: str = Field(
        ...,
        min_length=1,
        description="ID of the source field",
    )
    target_field_id: str = Field(
        ...,
        min_length=1,
        description="ID of the target field",
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="String similarity score (0.0 to 1.0)",
    )
    match_reason: MappingReason = Field(
        ...,
        description="How this candidate was identified",
    )

    model_config = {"frozen": True}


class MappingDecision(BaseModel):
    """Final decision for a field mapping.

    Represents a confirmed or high-confidence mapping after
    candidate evaluation (possibly by LLM agent).
    """

    source_field_id: str = Field(
        ...,
        min_length=1,
        description="ID of the source field",
    )
    target_field_id: str = Field(
        ...,
        min_length=1,
        description="ID of the target field",
    )
    mapping_type: MappingType = Field(
        default=MappingType.ONE_TO_ONE,
        description="Type of mapping relationship",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this mapping (0.0 to 1.0)",
    )
    reason: MappingReason = Field(
        ...,
        description="Primary reason for this mapping decision",
    )
    evidence_ref: str | None = Field(
        default=None,
        description="Reference to evidence supporting this mapping",
    )

    model_config = {"frozen": True}


class MappingRule(BaseModel):
    """User-defined mapping rule.

    Explicit rules provided by the user to guide mapping behavior.
    These take precedence over automatic matching.
    """

    source_pattern: str = Field(
        ...,
        min_length=1,
        description="Pattern to match source field names (supports wildcards)",
    )
    target_pattern: str = Field(
        ...,
        min_length=1,
        description="Pattern to match target field names (supports wildcards)",
    )
    priority: int = Field(
        default=0,
        ge=0,
        description="Rule priority (higher = applied first)",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of the rule",
    )

    model_config = {"frozen": True}
