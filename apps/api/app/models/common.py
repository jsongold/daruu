"""Common models used across the API."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BBox(BaseModel):
    """Bounding box coordinates for a region on a page."""

    x: float = Field(..., description="X coordinate (left)")
    y: float = Field(..., description="Y coordinate (top)")
    width: float = Field(..., ge=0, description="Width of the box")
    height: float = Field(..., ge=0, description="Height of the box")
    page: int = Field(..., ge=1, description="Page number (1-indexed)")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "x": 100.0,
                    "y": 200.0,
                    "width": 150.0,
                    "height": 25.0,
                    "page": 1,
                }
            ]
        },
    }


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""

    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    limit: int = Field(..., ge=1, description="Items per page")
    has_more: bool = Field(..., description="Whether more items exist")

    model_config = {"frozen": True}


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    field: str | None = Field(None, description="Field that caused the error")
    trace_id: str | None = Field(None, description="Trace ID for debugging (500 errors)")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input: mode must be 'transfer' or 'scratch'",
                    "field": "body.mode",
                },
                {
                    "code": "NOT_FOUND",
                    "message": "Job not found: 550e8400-e29b-41d4-a716-446655440999",
                },
                {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred. Please try again later.",
                    "trace_id": "550e8400-e29b-41d4-a716-446655440888",
                },
            ]
        },
    }


class ErrorResponse(BaseModel):
    """Standard error response format."""

    success: bool = Field(default=False, description="Always false for errors")
    error: ErrorDetail = Field(..., description="Error details")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": "Job not found: 550e8400-e29b-41d4-a716-446655440999",
                    },
                }
            ]
        },
    }


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool = Field(..., description="Whether the request succeeded")
    data: T | None = Field(None, description="Response data")
    error: str | None = Field(None, description="Error message if failed")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")

    model_config = {"frozen": True}


class CostBreakdown(BaseModel):
    """Breakdown of costs by category."""

    llm_cost_usd: float = Field(..., ge=0, description="LLM API cost in USD")
    ocr_cost_usd: float = Field(..., ge=0, description="OCR processing cost in USD")
    storage_cost_usd: float = Field(default=0.0, ge=0, description="Storage cost in USD")

    model_config = {"frozen": True}


class CostSummaryModel(BaseModel):
    """Cost tracking summary for API responses.

    Provides visibility into resource consumption and estimated costs
    for LLM and OCR operations within a job.
    """

    llm_tokens_input: int = Field(
        default=0, ge=0, description="Total input tokens sent to LLM"
    )
    llm_tokens_output: int = Field(
        default=0, ge=0, description="Total output tokens received from LLM"
    )
    llm_calls: int = Field(default=0, ge=0, description="Number of LLM API calls made")
    ocr_pages_processed: int = Field(
        default=0, ge=0, description="Number of pages processed by OCR"
    )
    ocr_regions_processed: int = Field(
        default=0, ge=0, description="Number of regions processed by targeted OCR"
    )
    storage_bytes_uploaded: int = Field(
        default=0, ge=0, description="Total bytes uploaded to storage"
    )
    storage_bytes_downloaded: int = Field(
        default=0, ge=0, description="Total bytes downloaded from storage"
    )
    estimated_cost_usd: float = Field(
        default=0.0, ge=0, description="Total estimated cost in USD"
    )
    breakdown: CostBreakdown = Field(
        default_factory=lambda: CostBreakdown(
            llm_cost_usd=0.0, ocr_cost_usd=0.0, storage_cost_usd=0.0
        ),
        description="Cost breakdown by category",
    )
    model_name: str = Field(
        default="gpt-4o-mini", description="Primary LLM model used"
    )

    model_config = {"frozen": True}

    @classmethod
    def empty(cls) -> "CostSummaryModel":
        """Create an empty cost summary.

        Returns:
            CostSummaryModel with zero values
        """
        return cls(
            llm_tokens_input=0,
            llm_tokens_output=0,
            llm_calls=0,
            ocr_pages_processed=0,
            ocr_regions_processed=0,
            storage_bytes_uploaded=0,
            storage_bytes_downloaded=0,
            estimated_cost_usd=0.0,
            breakdown=CostBreakdown(
                llm_cost_usd=0.0, ocr_cost_usd=0.0, storage_cost_usd=0.0
            ),
            model_name="gpt-4o-mini",
        )
