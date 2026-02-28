"""Domain models for the FormContext — output of FormContextBuilder.

FormContext aggregates all information needed for FillPlanner:
field specs, data source entries, and fuzzy-matched mapping candidates.
"""

from typing import Any

from pydantic import BaseModel, Field


class LabelCandidate(BaseModel):
    """A detected label candidate from the PDF form."""

    text: str = Field(..., description="Detected label text")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence"
    )
    page: int | None = Field(None, ge=1, description="Page number (1-indexed)")

    model_config = {"frozen": True}


class MappingCandidate(BaseModel):
    """A candidate mapping between a form field and a data source entry."""

    field_id: str = Field(..., description="Target form field ID")
    source_key: str = Field(..., description="Key from the data source")
    source_value: str = Field(..., description="Value from the data source")
    source_name: str = Field(..., description="Name of the originating data source")
    score: float = Field(
        ..., ge=0.0, le=1.0, description="Fuzzy match score"
    )

    model_config = {"frozen": True}


class DataSourceEntry(BaseModel):
    """Extracted data from a single data source."""

    source_name: str = Field(..., description="Data source name")
    source_type: str = Field(..., description="Data source type (pdf, csv, image, text)")
    extracted_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs extracted from the source",
    )
    raw_text: str | None = Field(
        None, description="Raw text content (used when no structured fields exist)"
    )
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Extraction confidence"
    )

    model_config = {"frozen": True}


class FormFieldSpec(BaseModel):
    """Specification of a single form field to be filled."""

    field_id: str = Field(..., description="Unique field identifier")
    label: str = Field(..., description="Field label/name")
    field_type: str = Field(
        default="text",
        description="Field type: text, date, checkbox, number",
    )
    page: int | None = Field(None, ge=1, description="Page number (1-indexed)")
    x: float | None = Field(None, description="Bbox X coordinate (PDF points)")
    y: float | None = Field(None, description="Bbox Y coordinate (PDF points)")
    width: float | None = Field(None, ge=0, description="Bbox width (PDF points)")
    height: float | None = Field(None, ge=0, description="Bbox height (PDF points)")
    label_candidates: tuple[LabelCandidate, ...] = Field(
        default=(), description="Detected label candidates"
    )

    model_config = {"frozen": True}


class FormContext(BaseModel):
    """Aggregated context for form filling — output of FormContextBuilder.

    Contains all information the FillPlanner needs to produce a FillPlan:
    the field specifications, available data, and pre-computed mapping candidates.
    """

    document_id: str = Field(..., description="Target document ID")
    conversation_id: str = Field(..., description="Conversation ID with data sources")
    fields: tuple[FormFieldSpec, ...] = Field(
        ..., min_length=1, description="Form field specifications"
    )
    data_sources: tuple[DataSourceEntry, ...] = Field(
        default=(), description="Extracted data source entries"
    )
    mapping_candidates: tuple[MappingCandidate, ...] = Field(
        default=(), description="Pre-computed fuzzy mapping candidates"
    )
    rules: tuple[str, ...] = Field(
        default=(), description="User-provided filling rules"
    )

    model_config = {"frozen": True}
