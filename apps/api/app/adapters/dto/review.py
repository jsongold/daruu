"""DTOs for the /review endpoint."""

from pydantic import BaseModel, Field


class ReviewRequestDTO(BaseModel):
    """Request body for POST /api/v1/review.

    Get review data for a filled document.
    """

    job_id: str = Field(..., description="Job ID to review")
    include_diff_images: bool = Field(
        default=True, description="Whether to include diff images"
    )
    include_evidence: bool = Field(
        default=True, description="Whether to include evidence details"
    )

    model_config = {"frozen": True}


class FieldStateDTO(BaseModel):
    """State of a field in the review."""

    field_id: str = Field(..., description="Field ID")
    name: str = Field(..., description="Field name")
    value: str | None = Field(None, description="Current value")
    confidence: float | None = Field(None, description="Extraction confidence")
    status: str = Field(
        ..., description="Status (filled, missing, low_confidence, error)"
    )
    page: int = Field(..., ge=1, description="Page number")
    bbox: list[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Bounding box [x0, y0, x1, y1]",
    )

    model_config = {"frozen": True}


class IssueDetailDTO(BaseModel):
    """Detailed issue information."""

    id: str = Field(..., description="Issue ID")
    field_id: str = Field(..., description="Related field ID")
    issue_type: str = Field(..., description="Issue type")
    message: str = Field(..., description="Issue description")
    severity: str = Field(..., description="Severity level")
    suggested_action: str | None = Field(None, description="Suggested resolution")

    model_config = {"frozen": True}


class PagePreviewDTO(BaseModel):
    """Preview information for a page."""

    page: int = Field(..., ge=1, description="Page number")
    preview_url: str = Field(..., description="URL to preview image")
    diff_url: str | None = Field(None, description="URL to diff image (if available)")
    field_count: int = Field(..., ge=0, description="Number of fields on this page")

    model_config = {"frozen": True}


class EvidenceDetailDTO(BaseModel):
    """Detailed evidence information."""

    id: str = Field(..., description="Evidence ID")
    field_id: str = Field(..., description="Related field ID")
    kind: str = Field(..., description="Evidence kind")
    source_page: int = Field(..., ge=1, description="Source page number")
    source_bbox: list[float] | None = Field(
        None,
        min_length=4,
        max_length=4,
        description="Source bounding box",
    )
    text: str | None = Field(None, description="Extracted text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence")
    crop_url: str | None = Field(None, description="URL to crop image")

    model_config = {"frozen": True}


class ConfidenceSummaryDTO(BaseModel):
    """Summary of confidence across all fields."""

    total_fields: int = Field(..., ge=0, description="Total number of fields")
    high_confidence: int = Field(
        ..., ge=0, description="Fields with confidence >= 0.8"
    )
    medium_confidence: int = Field(
        ..., ge=0, description="Fields with confidence 0.5-0.8"
    )
    low_confidence: int = Field(
        ..., ge=0, description="Fields with confidence < 0.5"
    )
    missing: int = Field(..., ge=0, description="Fields with no value")
    average_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Average confidence"
    )

    model_config = {"frozen": True}


class ReviewResponseDTO(BaseModel):
    """Response body for POST /api/v1/review."""

    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Current job status")
    fields: list[FieldStateDTO] = Field(
        default_factory=list, description="Field states"
    )
    issues: list[IssueDetailDTO] = Field(
        default_factory=list, description="Current issues"
    )
    previews: list[PagePreviewDTO] = Field(
        default_factory=list, description="Page previews"
    )
    evidence: list[EvidenceDetailDTO] = Field(
        default_factory=list, description="Evidence details"
    )
    confidence_summary: ConfidenceSummaryDTO = Field(
        ..., description="Confidence summary"
    )
    output_url: str | None = Field(None, description="URL to output PDF (if available)")

    model_config = {"frozen": True}
