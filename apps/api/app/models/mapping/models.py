"""API models for the Mapping service.

All models use frozen=True for immutability, following project conventions.
These models define the API contract for the mapping endpoint.
"""

from pydantic import BaseModel, Field


class SourceField(BaseModel):
    """A field from the source document.

    Contains the field identifier and metadata needed for mapping.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the source field",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human-readable field name/label",
    )
    value: str | None = Field(
        default=None,
        description="Current value of the field (if available)",
    )
    field_type: str | None = Field(
        default=None,
        description="Type of the field (text, number, date, etc.)",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Page number where field appears",
    )

    model_config = {"frozen": True}


class TargetField(BaseModel):
    """A field from the target document/template.

    Contains the field identifier and metadata for mapping targets.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for the target field",
    )
    name: str = Field(
        ...,
        min_length=1,
        description="Human-readable field name/label",
    )
    field_type: str | None = Field(
        default=None,
        description="Expected type of the field (text, number, date, etc.)",
    )
    is_required: bool = Field(
        default=False,
        description="Whether this field must be mapped",
    )
    page: int | None = Field(
        default=None,
        ge=1,
        description="Page number where field appears",
    )

    model_config = {"frozen": True}


class UserRule(BaseModel):
    """User-provided mapping rule.

    Explicit rules that override or guide automatic mapping.
    """

    source_pattern: str = Field(
        ...,
        min_length=1,
        description="Pattern to match source field names",
    )
    target_pattern: str = Field(
        ...,
        min_length=1,
        description="Pattern to match target field names",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description of the rule",
    )

    model_config = {"frozen": True}


class MappingRequest(BaseModel):
    """Request to generate field mappings.

    Contract input: source_fields[], target_fields[], user_rules, template_history
    """

    source_fields: tuple[SourceField, ...] = Field(
        ...,
        min_length=1,
        description="Fields from the source document to map",
    )
    target_fields: tuple[TargetField, ...] = Field(
        ...,
        min_length=1,
        description="Fields in the target document to map to",
    )
    user_rules: tuple[UserRule, ...] | None = Field(
        default=None,
        description="Optional user-defined mapping rules",
    )
    template_history: tuple[str, ...] | None = Field(
        default=None,
        description="Optional template IDs for historical mapping inference",
    )
    require_confirmation: bool = Field(
        default=False,
        description="If true, low-confidence mappings generate followup questions",
    )
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for automatic mapping (0.0 to 1.0)",
    )

    model_config = {"frozen": True}


class MappingItem(BaseModel):
    """A single field mapping in the result.

    Represents a confirmed source-to-target field correspondence.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this mapping",
    )
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
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this mapping (0.0 to 1.0)",
    )
    reason: str = Field(
        ...,
        description="Reason for this mapping (exact_match, fuzzy_match, llm_inference, etc.)",
    )
    is_confirmed: bool = Field(
        default=False,
        description="Whether this mapping has been user-confirmed",
    )

    model_config = {"frozen": True}


class FollowupQuestion(BaseModel):
    """A question for the user to resolve ambiguous mappings.

    Generated when the service cannot confidently map a field.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this question",
    )
    question: str = Field(
        ...,
        min_length=1,
        description="The question text for the user",
    )
    source_field_id: str = Field(
        ...,
        min_length=1,
        description="ID of the source field in question",
    )
    candidate_target_ids: tuple[str, ...] = Field(
        ...,
        description="IDs of potential target fields for user selection",
    )
    context: str | None = Field(
        default=None,
        description="Additional context to help the user decide",
    )

    model_config = {"frozen": True}


class MappingResult(BaseModel):
    """Result of the mapping operation.

    Contract output: mappings[], evidence_refs, followup_questions[]
    """

    mappings: tuple[MappingItem, ...] = Field(
        default=(),
        description="Generated field mappings",
    )
    evidence_refs: tuple[str, ...] = Field(
        default=(),
        description="References to evidence supporting the mappings",
    )
    followup_questions: tuple[FollowupQuestion, ...] = Field(
        default=(),
        description="Questions for user to resolve ambiguous mappings",
    )
    unmapped_source_fields: tuple[str, ...] = Field(
        default=(),
        description="IDs of source fields that could not be mapped",
    )
    unmapped_target_fields: tuple[str, ...] = Field(
        default=(),
        description="IDs of required target fields that have no mapping",
    )

    model_config = {"frozen": True}
