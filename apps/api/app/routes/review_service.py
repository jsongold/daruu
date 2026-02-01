"""Review service routes.

POST /api/v1/review/inspect - Run document review for issue detection.

This endpoint is distinct from the existing /review endpoint which
provides job-level review data. This endpoint specifically runs
the Review Service for visual inspection and issue detection.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.models import ApiResponse
from app.models.review import (
    ReviewRequest,
    ReviewResult,
)
from app.services.review.adapters import (
    LocalPreviewStorage,
    OpenCVDiffGenerator,
    PyMuPdfRenderer,
    RuleBasedIssueDetector,
)
from app.services.review.service import ReviewService

router = APIRouter(tags=["review-service"])


def get_review_service() -> ReviewService:
    """Dependency injection for ReviewService.

    Creates a ReviewService instance with default adapters.
    In production, this would use configuration to select adapters.

    Returns:
        Configured ReviewService instance
    """
    # Create adapters (in production, these would be configured)
    pdf_renderer = PyMuPdfRenderer()
    diff_generator = OpenCVDiffGenerator()
    issue_detector = RuleBasedIssueDetector()
    preview_storage = LocalPreviewStorage()

    return ReviewService(
        pdf_renderer=pdf_renderer,
        diff_generator=diff_generator,
        issue_detector=issue_detector,
        preview_storage=preview_storage,
    )


@router.post(
    "/review/inspect",
    response_model=ApiResponse[ReviewResult],
    status_code=status.HTTP_200_OK,
    summary="Run document review for issue detection",
    description="""
Run the Review Service on a filled document to detect issues.

This is a **deterministic service** (no Agent/LLM):
- Same input -> same output
- Pure geometric and visual analysis

The review process:
1. Renders filled PDF pages to images
2. Detects issues (overflow, overlap, missing values)
3. Generates diff images (if original document provided)
4. Stores preview artifacts for UI display
5. Calculates confidence updates based on issues

**Issue Types Detected:**
- **Overflow**: Text exceeding its bounding box
- **Overlap**: Fields with intersecting bounding boxes
- **Missing Value**: Required fields without values

**Returns:**
- **issues**: List of detected issues with severity and suggested actions
- **preview_artifacts**: Page preview images and optional diff images
- **confidence_updates**: Updated confidence scores for affected fields
""",
)
async def run_review_inspection(
    request: ReviewRequest,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> ApiResponse[ReviewResult]:
    """Run document review inspection.

    Args:
        request: Review request with document refs and fields
        service: Injected ReviewService instance

    Returns:
        ApiResponse containing ReviewResult with issues and previews

    Raises:
        HTTPException: If review fails
    """
    try:
        result = await service.review(request)

        return ApiResponse(
            success=True,
            data=result,
            meta={
                "total_issues": result.total_issues,
                "critical_issues": result.critical_issues,
                "pages_processed": len(result.preview_artifacts),
                "confidence_updates": len(result.confidence_updates),
            },
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {e}",
        ) from e

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        ) from e

    except NotImplementedError as e:
        # Stub implementations raise NotImplementedError
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Feature not yet implemented: {e}",
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Review failed: {e}",
        ) from e


@router.get(
    "/review/inspect/{document_id}/preview/{page_number}",
    status_code=status.HTTP_200_OK,
    summary="Get preview image for a page",
    description="""
Get the preview image for a specific page of a reviewed document.

Returns the PNG image data for the page preview.
""",
)
async def get_page_preview(
    document_id: str,
    page_number: int,
    service: Annotated[ReviewService, Depends(get_review_service)],
) -> dict:
    """Get preview image for a page.

    Args:
        document_id: Document identifier
        page_number: 1-indexed page number
        service: Injected ReviewService instance

    Returns:
        Dictionary with preview URL

    Raises:
        HTTPException: If preview not found
    """
    # This is a placeholder - in production, would look up stored preview
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Preview retrieval not yet implemented",
    )
