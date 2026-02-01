"""Template models for the Template System.

Templates define reusable form structures for faster document processing.
They contain field positions (bboxes), validation rules, and visual embeddings
for similarity-based matching.

Key entities:
- Template: The main template definition with metadata
- TemplateBbox: Field position and type information
- TemplateRule: Validation and fill rules for fields
- TemplateMatch: Result of template similarity search
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Type of form field."""

    TEXT = "text"
    CHECKBOX = "checkbox"
    SIGNATURE = "signature"
    DATE = "date"
    NUMBER = "number"
    RADIO = "radio"
    DROPDOWN = "dropdown"


class RuleType(str, Enum):
    """Type of validation/fill rule."""

    REQUIRED = "required"
    FORMAT = "format"
    DEPENDENCY = "dependency"
    RANGE = "range"
    PATTERN = "pattern"
    READONLY = "readonly"


class TemplateBbox(BaseModel):
    """Field bounding box within a template.

    Defines the position and type of a single field on a page.
    Coordinates are in PDF points (72 points = 1 inch).
    """

    id: str = Field(..., description="Unique field identifier within template")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    x: float = Field(..., ge=0, description="X coordinate from left edge")
    y: float = Field(..., ge=0, description="Y coordinate from top edge")
    width: float = Field(..., gt=0, description="Field width")
    height: float = Field(..., gt=0, description="Field height")
    label: str | None = Field(None, description="Human-readable label for the field")
    field_type: FieldType = Field(
        default=FieldType.TEXT, description="Type of input field"
    )

    model_config = {"frozen": True}


class TemplateRule(BaseModel):
    """Validation or fill rule for a template field.

    Rules define constraints and behaviors for fields:
    - required: Field must have a value
    - format: Value must match a format (e.g., date, phone)
    - dependency: Field depends on another field's value
    - range: Numeric value must be within a range
    - pattern: Value must match a regex pattern
    """

    field_id: str = Field(..., description="ID of the field this rule applies to")
    rule_type: RuleType = Field(..., description="Type of rule")
    rule_config: dict[str, Any] = Field(
        default_factory=dict, description="Rule-specific configuration"
    )

    model_config = {"frozen": True}


class Template(BaseModel):
    """A form template definition.

    Templates capture the structure of common forms (W-9, I-9, 1040, etc.)
    for reuse. They include field positions, validation rules, and
    embeddings for visual similarity matching.
    """

    id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    form_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Form type identifier (e.g., 'W-9', 'I-9', '1040')",
    )
    bboxes: tuple[TemplateBbox, ...] = Field(
        default_factory=tuple, description="Field positions within the template"
    )
    rules: tuple[TemplateRule, ...] = Field(
        default_factory=tuple, description="Validation and fill rules"
    )
    embedding_id: str | None = Field(
        None, description="Reference to stored visual embedding"
    )
    preview_url: str | None = Field(None, description="URL to template preview image")
    field_count: int = Field(default=0, ge=0, description="Number of fields")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    tenant_id: str | None = Field(None, description="Tenant ID for multi-tenancy")

    model_config = {"frozen": True}


class TemplateCreate(BaseModel):
    """Request to create a new template."""

    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    form_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Form type identifier",
    )
    bboxes: list[TemplateBbox] = Field(
        default_factory=list, description="Field positions"
    )
    rules: list[TemplateRule] = Field(
        default_factory=list, description="Validation rules"
    )
    preview_url: str | None = Field(None, description="URL to template preview image")
    tenant_id: str | None = Field(None, description="Tenant ID for multi-tenancy")

    model_config = {"frozen": True}


class TemplateUpdate(BaseModel):
    """Request to update an existing template."""

    name: str | None = Field(None, max_length=200, description="Template name")
    form_type: str | None = Field(None, max_length=50, description="Form type")
    bboxes: list[TemplateBbox] | None = Field(None, description="Field positions")
    rules: list[TemplateRule] | None = Field(None, description="Validation rules")
    preview_url: str | None = Field(None, description="URL to template preview image")

    model_config = {"frozen": True}


class TemplateResponse(BaseModel):
    """API response containing a template."""

    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    form_type: str = Field(..., description="Form type identifier")
    field_count: int = Field(..., description="Number of fields")
    preview_url: str | None = Field(None, description="Preview image URL")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


class TemplateDetailResponse(BaseModel):
    """API response with full template details."""

    id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    form_type: str = Field(..., description="Form type identifier")
    bboxes: tuple[TemplateBbox, ...] = Field(..., description="Field positions")
    rules: tuple[TemplateRule, ...] = Field(..., description="Validation rules")
    field_count: int = Field(..., description="Number of fields")
    preview_url: str | None = Field(None, description="Preview image URL")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


class TemplateMatch(BaseModel):
    """Result of template similarity search.

    Represents a template that visually matches an uploaded document page.
    """

    template_id: str = Field(..., description="Matched template ID")
    template_name: str = Field(..., description="Template display name")
    form_type: str = Field(..., description="Form type identifier")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score (0-1)"
    )
    preview_url: str | None = Field(None, description="Template preview URL")
    field_count: int = Field(default=0, description="Number of fields in template")

    model_config = {"frozen": True}


class TemplateMatchRequest(BaseModel):
    """Request to find matching templates for an uploaded page."""

    page_image: bytes | None = Field(
        None, description="Page image bytes (PNG/JPEG) for embedding"
    )
    page_image_ref: str | None = Field(
        None, description="Reference to stored page image"
    )
    limit: int = Field(default=3, ge=1, le=10, description="Maximum matches to return")
    threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    tenant_id: str | None = Field(None, description="Filter by tenant")

    model_config = {"frozen": True}


class TemplateMatchResponse(BaseModel):
    """Response containing template matches."""

    success: bool = Field(..., description="Whether matching succeeded")
    matches: tuple[TemplateMatch, ...] = Field(
        default_factory=tuple, description="Matching templates sorted by similarity"
    )
    error: str | None = Field(None, description="Error message if failed")

    model_config = {"frozen": True}


class TemplateListResponse(BaseModel):
    """Response containing a list of templates."""

    success: bool = Field(default=True, description="Whether request succeeded")
    templates: tuple[TemplateResponse, ...] = Field(
        default_factory=tuple, description="List of templates"
    )
    total: int = Field(default=0, description="Total count of templates")

    model_config = {"frozen": True}
