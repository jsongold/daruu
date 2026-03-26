"""Field and mapping models."""

from enum import Enum

from pydantic import BaseModel, Field

from app.models.common import BBox


class FieldType(str, Enum):
    """Type of form field."""

    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SIGNATURE = "signature"
    IMAGE = "image"
    UNKNOWN = "unknown"


class FieldModel(BaseModel):
    """A form field in a document."""

    id: str = Field(..., description="Unique field ID")
    name: str = Field(..., description="Field name/label")
    field_type: FieldType = Field(default=FieldType.TEXT, description="Type of field")
    value: str | None = Field(None, description="Current field value")
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Confidence score for extracted value"
    )
    bbox: BBox | None = Field(None, description="Bounding box location")
    document_id: str = Field(..., description="ID of document containing this field")
    page: int = Field(..., ge=1, description="Page number where field appears")
    is_required: bool = Field(default=False, description="Whether field is required")
    is_editable: bool = Field(default=True, description="Whether field can be edited")

    model_config = {"frozen": True}


# Alias for backward compatibility
FieldAlias = FieldModel


class Mapping(BaseModel):
    """Mapping between source and target fields."""

    id: str = Field(..., description="Unique mapping ID")
    source_field_id: str = Field(..., description="ID of source field")
    target_field_id: str = Field(..., description="ID of target field")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for this mapping")
    is_confirmed: bool = Field(default=False, description="Whether mapping is user-confirmed")

    model_config = {"frozen": True}


class FieldAnswer(BaseModel):
    """Answer to a field question."""

    field_id: str = Field(..., description="ID of field being answered")
    value: str = Field(..., description="Answer value")

    model_config = {"frozen": True}


class FieldEdit(BaseModel):
    """Manual edit to a field."""

    field_id: str = Field(..., description="ID of field being edited")
    value: str | None = Field(None, description="New value for the field")
    bbox: BBox | None = Field(None, description="New bounding box location")
    render_params: dict[str, str | int | float | bool] | None = Field(
        None, description="Rendering parameters"
    )

    model_config = {"frozen": True}
