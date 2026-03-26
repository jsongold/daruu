"""Request and response models for Vision Autofill Service.

These models define the contract for the LLM vision-based form autofill API.
"""

from pydantic import BaseModel, Field


class FieldInfo(BaseModel):
    """Information about a form field to be filled."""

    field_id: str = Field(..., description="Unique field identifier")
    label: str = Field(..., description="Field label/name")
    type: str = Field(
        default="text",
        description="Field type: text, date, checkbox, number",
    )
    x: float | None = Field(None, description="Bbox X coordinate (PDF points)")
    y: float | None = Field(None, description="Bbox Y coordinate (PDF points)")
    width: float | None = Field(None, ge=0, description="Bbox width (PDF points)")
    height: float | None = Field(None, ge=0, description="Bbox height (PDF points)")
    page: int | None = Field(None, ge=1, description="Page number")

    model_config = {"frozen": True}


class VisionAutofillRequest(BaseModel):
    """Request for vision-based autofill.

    Sends document fields and data source context to the LLM
    for intelligent field value extraction and matching.
    """

    document_id: str = Field(..., description="Target document ID to fill")
    fields: list[FieldInfo] = Field(
        ..., min_length=1, description="Fields to fill with their definitions"
    )
    conversation_id: str = Field(..., description="Conversation ID with data sources")
    rules: list[str] | None = Field(
        None, description="Optional rules for field filling (e.g., date format)"
    )
    system_prompt: str | None = Field(
        None, description="Optional system prompt override for LLM autofill"
    )

    model_config = {"frozen": True}


class FilledField(BaseModel):
    """A field that was successfully filled by the LLM."""

    field_id: str = Field(..., description="Field identifier")
    value: str = Field(..., description="Extracted/computed value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    source: str | None = Field(None, description="Data source that provided the value")

    model_config = {"frozen": True}


class VisionAutofillResponse(BaseModel):
    """Response from vision autofill service.

    Contains filled field values, unfilled fields, and any warnings.
    """

    success: bool = Field(..., description="Whether autofill succeeded")
    filled_fields: list[FilledField] = Field(
        default_factory=list, description="Fields that were filled with values"
    )
    unfilled_fields: list[str] = Field(
        default_factory=list, description="Field IDs that could not be filled"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings about data quality or ambiguity"
    )
    processing_time_ms: int = Field(default=0, ge=0, description="Processing time in milliseconds")
    error: str | None = Field(None, description="Error message if success=False")
    raw_response: str | None = Field(
        None, description="Raw LLM response text (populated when LLM is used)"
    )
    system_prompt: str | None = Field(
        None, description="System prompt sent to LLM (populated when LLM is used)"
    )
    user_prompt: str | None = Field(
        None, description="User prompt sent to LLM (populated when LLM is used)"
    )

    model_config = {"frozen": True}
