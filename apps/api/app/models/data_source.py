"""Data source models for AI form filling.

Data sources are files or text that users upload to provide information
that the AI agent uses to auto-fill form fields.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DataSourceType(str, Enum):
    """Type of data source."""

    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    CSV = "csv"


# ============================================
# Core Models
# ============================================


class DataSource(BaseModel):
    """A data source for AI form filling."""

    id: str = Field(..., description="Unique data source ID")
    conversation_id: str = Field(..., description="ID of the parent conversation")
    type: DataSourceType = Field(..., description="Type of data source")
    name: str = Field(..., min_length=1, description="Display name (usually original filename)")
    document_id: str | None = Field(None, description="Reference to documents table for files")
    text_content: str | None = Field(None, description="Direct text content for text/csv sources")
    content_preview: str | None = Field(None, description="First 500 chars for preview")
    extracted_data: dict[str, Any] | None = Field(None, description="Cached AI extraction results")
    file_size_bytes: int | None = Field(None, ge=0, description="File size in bytes")
    mime_type: str | None = Field(None, description="MIME type")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = {"frozen": True}


# ============================================
# Request Models
# ============================================


class CreateTextDataSourceRequest(BaseModel):
    """Request to create a text data source."""

    name: str = Field(..., min_length=1, max_length=255, description="Display name")
    content: str = Field(..., min_length=1, max_length=100000, description="Text content")

    model_config = {"frozen": True}


class CreateFileDataSourceRequest(BaseModel):
    """Request to create a file-based data source.

    Note: Actual file is sent via multipart form data.
    """

    # File is uploaded via UploadFile, not in this request body
    pass


# ============================================
# Response Models
# ============================================


class DataSourceResponse(BaseModel):
    """Response for a single data source."""

    id: str = Field(..., description="Unique data source ID")
    type: DataSourceType = Field(..., description="Type of data source")
    name: str = Field(..., description="Display name")
    document_id: str | None = Field(None, description="Reference to documents table")
    content_preview: str | None = Field(None, description="First 500 chars for preview")
    extracted_data: dict[str, Any] | None = Field(None, description="Cached extraction results")
    file_size_bytes: int | None = Field(None, description="File size in bytes")
    mime_type: str | None = Field(None, description="MIME type")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"frozen": True}

    @classmethod
    def from_data_source(cls, data_source: DataSource) -> "DataSourceResponse":
        """Create response from DataSource model."""
        return cls(
            id=data_source.id,
            type=data_source.type,
            name=data_source.name,
            document_id=data_source.document_id,
            content_preview=data_source.content_preview,
            extracted_data=data_source.extracted_data,
            file_size_bytes=data_source.file_size_bytes,
            mime_type=data_source.mime_type,
            created_at=data_source.created_at,
        )


class DataSourceListResponse(BaseModel):
    """Response for list of data sources."""

    items: list[DataSourceResponse] = Field(..., description="List of data sources")
    total: int = Field(..., ge=0, description="Total count")

    model_config = {"frozen": True}


class ExtractionResult(BaseModel):
    """Result of AI extraction from a data source."""

    data_source_id: str = Field(..., description="Data source ID")
    extracted_fields: dict[str, Any] = Field(
        default_factory=dict, description="Extracted field name-value pairs"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall extraction confidence")
    raw_text: str | None = Field(None, description="Raw extracted text")

    model_config = {"frozen": True}


# ============================================
# Supported File Types
# ============================================

# Mapping of MIME types to DataSourceType
MIME_TYPE_MAP: dict[str, DataSourceType] = {
    "application/pdf": DataSourceType.PDF,
    "image/png": DataSourceType.IMAGE,
    "image/jpeg": DataSourceType.IMAGE,
    "image/tiff": DataSourceType.IMAGE,
    "image/webp": DataSourceType.IMAGE,
    "text/plain": DataSourceType.TEXT,
    "text/csv": DataSourceType.CSV,
    "application/csv": DataSourceType.CSV,
}

# File extension mapping
EXTENSION_TYPE_MAP: dict[str, DataSourceType] = {
    ".pdf": DataSourceType.PDF,
    ".png": DataSourceType.IMAGE,
    ".jpg": DataSourceType.IMAGE,
    ".jpeg": DataSourceType.IMAGE,
    ".tiff": DataSourceType.IMAGE,
    ".tif": DataSourceType.IMAGE,
    ".webp": DataSourceType.IMAGE,
    ".txt": DataSourceType.TEXT,
    ".csv": DataSourceType.CSV,
}

# Size limits by type (in bytes)
SIZE_LIMITS: dict[DataSourceType, int] = {
    DataSourceType.PDF: 50 * 1024 * 1024,  # 50MB
    DataSourceType.IMAGE: 50 * 1024 * 1024,  # 50MB
    DataSourceType.TEXT: 1 * 1024 * 1024,  # 1MB
    DataSourceType.CSV: 5 * 1024 * 1024,  # 5MB
}
