"""Review routes.

POST /api/v1/review - Get review data for a job.
Returns diff images, issues, field states, and evidence.
"""

from fastapi import APIRouter, HTTPException, status

from app.adapters.dto.review import (
    ConfidenceSummaryDTO,
    ReviewRequestDTO,
    ReviewResponseDTO,
)
from app.models import ApiResponse

router = APIRouter(tags=["review"])


@router.post(
    "/review",
    response_model=ApiResponse[ReviewResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Get review data for job",
    description="""
Get review data for a filled document job.

Returns comprehensive review information:
- **fields**: Current state of all fields (filled, missing, low_confidence)
- **issues**: Detected issues (overflow, overlap, validation errors)
- **previews**: Page preview images with optional diff images
- **evidence**: Evidence supporting each extraction
- **confidence_summary**: Aggregate confidence statistics

This endpoint is used by the review UI to:
- Display before/after comparisons
- Highlight issues requiring attention
- Show evidence for each extracted value
- Enable one-click navigation to issues
""",
)
async def get_review_data(
    request: ReviewRequestDTO,
) -> ApiResponse[ReviewResponseDTO]:
    """Get review data for a job.

    Args:
        request: Review request with job ID and options

    Returns:
        Review data with fields, issues, previews, and evidence

    Raises:
        HTTPException: If job not found
    """
    # TODO: Implement with actual review data generation
    # This is a stub that returns minimal data

    # Check if job exists
    from app.services import JobService

    service = JobService()
    job = service.get_job(request.job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {request.job_id}",
        )

    # Return stub response
    # In production, this would:
    # 1. Load job context
    # 2. Generate diff images if requested
    # 3. Compile field states with evidence
    # 4. Calculate confidence summary
    # 5. Return comprehensive review data

    # Calculate confidence summary from job fields
    total_fields = len(job.fields)
    high_conf = sum(1 for f in job.fields if f.confidence and f.confidence >= 0.8)
    medium_conf = sum(1 for f in job.fields if f.confidence and 0.5 <= f.confidence < 0.8)
    low_conf = sum(1 for f in job.fields if f.confidence and f.confidence < 0.5)
    no_value = sum(1 for f in job.fields if not f.value)

    confidences = [f.confidence for f in job.fields if f.confidence]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return ApiResponse(
        success=True,
        data=ReviewResponseDTO(
            job_id=request.job_id,
            status=job.status.value,
            fields=[],  # Would be populated from job.fields
            issues=[],  # Would be populated from job.issues
            previews=[],  # Would be generated from document pages
            evidence=[],  # Would be populated from job.evidence
            confidence_summary=ConfidenceSummaryDTO(
                total_fields=total_fields,
                high_confidence=high_conf,
                medium_confidence=medium_conf,
                low_confidence=low_conf,
                missing=no_value,
                average_confidence=avg_conf,
            ),
            output_url=None,  # Would be set if job is done
        ),
        meta={
            "stub": True,
            "include_diff_images": request.include_diff_images,
            "include_evidence": request.include_evidence,
        },
    )
