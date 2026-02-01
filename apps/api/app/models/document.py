"""Document models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Type of document in the workflow."""

    SOURCE = "source"
    TARGET = "target"


class DocumentMeta(BaseModel):
    """Metadata about a document."""

    page_count: int = Field(..., ge=1, description="Number of pages")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the document")
    filename: str = Field(..., description="Original filename")
    has_password: bool = Field(default=False, description="Whether document is password-protected")
    has_acroform: bool = Field(
        default=False,
        description="Whether document has AcroForm fields (pre-defined input areas)",
    )

    model_config = {"frozen": True}


class Document(BaseModel):
    """A document in the system."""

    id: str = Field(..., description="Unique document ID")
    ref: str = Field(..., description="Document reference/path")
    document_type: DocumentType = Field(..., description="Type of document")
    meta: DocumentMeta = Field(..., description="Document metadata")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = {"frozen": True}


class DocumentCreate(BaseModel):
    """Request to create/upload a document."""

    document_type: DocumentType = Field(..., description="Type of document being uploaded")

    model_config = {"frozen": True}


class DocumentResponse(BaseModel):
    """Response after document upload."""

    document_id: str = Field(..., description="Unique document ID")
    document_ref: str = Field(..., description="Document reference/path")
    meta: DocumentMeta = Field(..., description="Document metadata")

    model_config = {"frozen": True}


class PagePreviewResponse(BaseModel):
    """Response with page preview information."""

    document_id: str = Field(..., description="Document ID")
    page: int = Field(..., ge=1, description="Page number")
    content_type: str = Field(..., description="Image content type")
    width: int = Field(..., ge=1, description="Image width in pixels")
    height: int = Field(..., ge=1, description="Image height in pixels")

    model_config = {"frozen": True}
