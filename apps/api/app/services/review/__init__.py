"""Review service for visual inspection and issue detection.

This service handles:
- PDF rendering for filled documents
- Visual diff/overlay generation
- Issue detection (overflow, overlap, missing values)
- Preview artifact generation for UI display

This is a deterministic Service (no Agent/LLM):
- Same input -> same output
- Pure geometric and visual analysis
- Unit testable
"""

from app.models.review import (
    ConfidenceUpdate,
    PageMetaInput,
    PreviewArtifact,
    ReviewRequest,
    ReviewResult,
)
from app.services.review.service import ReviewService

__all__ = [
    "ConfidenceUpdate",
    "PageMetaInput",
    "PreviewArtifact",
    "ReviewRequest",
    "ReviewResult",
    "ReviewService",
]
