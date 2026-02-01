"""Adjust routes.

POST /api/v1/adjust - Adjust field bboxes and rendering parameters.
Returns patches to apply for overflow/overlap corrections.
"""

from fastapi import APIRouter, status

from app.models import ApiResponse
from app.models.adjust import AdjustRequest, AdjustResult
from app.services.adjust import AdjustService
from app.services.adjust.adapters import SimpleOverlapDetector

router = APIRouter(tags=["adjust"])


def _get_adjust_service() -> AdjustService:
    """Create and return an AdjustService instance.

    Factory function for dependency injection.
    In production, this would be configured via FastAPI dependencies.
    """
    overlap_detector = SimpleOverlapDetector()
    return AdjustService(overlap_detector)


@router.post(
    "/adjust",
    response_model=ApiResponse[AdjustResult],
    status_code=status.HTTP_200_OK,
    summary="Adjust field bboxes and render parameters",
    description="""
Adjust field bounding boxes and rendering parameters based on:
- Detected issues (overflow, overlap)
- Page metadata (boundaries)
- User edits (manual corrections)

This is a **deterministic service** (no LLM reasoning):
- Same input always produces same output
- Suitable for unit testing
- Fast, predictable execution

**Input:**
- `fields`: Fields to potentially adjust
- `issues`: Issues to address (from Review service)
- `page_meta`: Page dimensions for boundary checking
- `user_edits`: Optional user corrections (take precedence)

**Output:**
- `field_patches`: Proposed bbox/render changes
- `confidence_updates`: Confidence score adjustments
- `resolved_issue_ids`: Issues addressed by patches
- `remaining_issue_count`: Unresolved issues

**Patch Types:**
- `bbox_move`: Move bbox position
- `bbox_resize`: Resize bbox dimensions
- `bbox_full`: Complete bbox replacement
- `render_params`: Render parameter changes only
- `combined`: Both bbox and render changes

The orchestrator decides whether to apply returned patches.
""",
)
async def adjust_fields(
    request: AdjustRequest,
) -> ApiResponse[AdjustResult]:
    """Adjust field bboxes and rendering parameters.

    Analyzes fields and issues to generate correction patches.
    This is a deterministic operation - same input always
    produces the same output.

    Args:
        request: Adjust request with fields, issues, and page metadata.

    Returns:
        ApiResponse containing AdjustResult with patches.
    """
    service = _get_adjust_service()
    result = await service.adjust(request)

    return ApiResponse(
        success=result.success,
        data=result,
        error=result.errors[0].message if result.errors else None,
        meta={
            "patches_generated": len(result.field_patches),
            "issues_resolved": len(result.resolved_issue_ids),
            "issues_remaining": result.remaining_issue_count,
            "iterations_used": result.iterations_used,
        },
    )
