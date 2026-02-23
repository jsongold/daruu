"""Domain models for correction tracking.

CorrectionRecords capture user corrections to auto-filled values,
enabling learning and improvement over time.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CorrectionCategory(StrEnum):
    """Category of the correction."""

    WRONG_VALUE = "wrong_value"
    WRONG_FIELD = "wrong_field"
    MISSING_VALUE = "missing_value"
    FORMAT_ERROR = "format_error"
    OTHER = "other"


class CorrectionRecord(BaseModel):
    """Record of a user correction to an auto-filled field.

    Captures what was originally filled, what the user changed it to,
    and the category of correction for learning purposes.
    """

    document_id: str = Field(..., description="Document ID")
    field_id: str = Field(..., description="Field that was corrected")
    original_value: str | None = Field(
        None, description="Value that was auto-filled"
    )
    corrected_value: str = Field(..., description="User's corrected value")
    category: CorrectionCategory = Field(
        default=CorrectionCategory.OTHER,
        description="Category of the correction",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the correction was made",
    )
    conversation_id: str | None = Field(
        None, description="Conversation context"
    )

    model_config = {"frozen": True}
