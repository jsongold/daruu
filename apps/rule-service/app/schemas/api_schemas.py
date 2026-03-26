"""Request/response DTOs for the Rule Service API."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = Field(..., description="Whether the request succeeded")
    data: T | None = Field(None, description="Response data")
    error: str | None = Field(None, description="Error message if failed")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")

    model_config = {"frozen": True}


class FieldHintInput(BaseModel):
    """A single field hint for rule analysis context."""

    field_id: str = Field(..., min_length=1, description="Field identifier")
    label: str = Field(..., min_length=1, description="Field label")

    model_config = {"frozen": True}


class AnalyzeRulesRequest(BaseModel):
    """Request body for rule analysis."""

    document_id: str = Field(
        ..., min_length=1, max_length=255, description="Document ID for DB persistence"
    )
    rule_docs: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Rule document text strings (max 20 documents)",
    )
    field_hints: list[FieldHintInput] = Field(
        default_factory=list,
        description="Field hints with field_id and label",
    )

    model_config = {"frozen": True}

    @field_validator("rule_docs")
    @classmethod
    def validate_rule_doc_size(cls, v: list[str]) -> list[str]:
        max_chars = 500_000
        for i, doc in enumerate(v):
            if len(doc) > max_chars:
                raise ValueError(f"rule_docs[{i}] exceeds maximum length of {max_chars} characters")
        return v


class RuleSnippetDTO(BaseModel):
    """Response DTO for a rule snippet."""

    id: str | None
    document_id: str
    rule_text: str
    applicable_fields: list[str]
    source_document: str | None
    confidence: float
    created_at: datetime

    model_config = {"frozen": True}
