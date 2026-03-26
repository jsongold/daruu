"""Structure/Labelling API routes.

POST /api/v1/structure_labelling - Extract document structure and link labels to fields.
Uses FieldLabellingAgent (LLM) for semantic label-to-position linking.

This endpoint is the entry point for the Structure/Labelling phase of document processing.
It coordinates deterministic structure detection with LLM-based field labelling.
"""

from fastapi import APIRouter, HTTPException, status

from app.agents.structure_labelling import LangChainFieldLabellingAgent
from app.config import get_settings
from app.models.common import ApiResponse
from app.models.structure_labelling import (
    StructureLabellingRequest,
    StructureLabellingResult,
)
from app.services.structure_labelling import (
    LocalPageImageLoader,
    OpenCVStructureDetector,
    StructureLabellingService,
)

router = APIRouter(tags=["structure_labelling"])


def _create_service() -> StructureLabellingService:
    """Create and configure the StructureLabellingService.

    Factory function to create service with proper adapters.
    In production, this would use dependency injection.

    Returns:
        Configured StructureLabellingService instance
    """
    settings = get_settings()

    # Initialize adapters
    agent = LangChainFieldLabellingAgent(
        model_name=settings.openai_model,
        temperature=0.0,
    )
    detector = OpenCVStructureDetector()
    loader = LocalPageImageLoader(
        base_path=str(settings.upload_dir),
    )

    return StructureLabellingService(
        field_labelling_agent=agent,
        structure_detector=detector,
        page_image_loader=loader,
    )


@router.post(
    "/structure_labelling",
    response_model=ApiResponse[StructureLabellingResult],
    status_code=status.HTTP_200_OK,
    summary="Extract document structure and link labels to fields",
    description="""
Extract document structure and perform label-to-position linking.

This endpoint implements the Structure/Labelling phase from the PRD:

**Input**:
- page_images: Rendered page images for visual analysis
- native_text_blocks: (optional) Native PDF text blocks
- box_candidates: (optional) Pre-detected input boxes
- table_candidates: (optional) Pre-detected tables

**Output**:
- fields[]: Detected fields with name, type, bbox, anchor, confidence
- evidence[]: Evidence supporting each field detection (REQUIRED per PRD)

**Process**:
1. Load page images from storage
2. Run deterministic structure detection (if no candidates provided)
3. Use FieldLabellingAgent (LLM) for label-to-position linking
4. Return fields with evidence for auditability

**Why LLM is required**:
- Label text variations across document versions
- Multiple candidates for the same semantic field
- Table/form structure interpretation
- Nested box relationships require understanding

**Acceptance Criteria (MVP)**:
- Returns Field[] for major fields (name, address, date, amount)
- Every field has evidence_refs (audit trail)
""",
    responses={
        200: {
            "description": "Structure labelling completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "document_id": "doc-123",
                            "success": True,
                            "fields": [
                                {
                                    "id": "field_abc123",
                                    "name": "Name",
                                    "field_type": "text",
                                    "page": 1,
                                    "bbox": [100, 200, 300, 30],
                                    "anchor_bbox": [100, 170, 50, 20],
                                    "confidence": 0.92,
                                    "needs_review": False,
                                    "evidence_refs": ["ev_xyz789"],
                                }
                            ],
                            "evidence": [
                                {
                                    "id": "ev_xyz789",
                                    "kind": "llm_linking",
                                    "field_id": "field_abc123",
                                    "page": 1,
                                    "bbox": [100, 170, 50, 20],
                                    "text": "Name",
                                    "confidence": 0.92,
                                    "rationale": "Label 'Name' linked to adjacent input box",
                                }
                            ],
                            "page_count": 1,
                            "warnings": [],
                            "errors": [],
                        },
                        "error": None,
                        "meta": {"processing_time_ms": 1234},
                    }
                }
            },
        },
        400: {
            "description": "Invalid request (validation error)",
        },
        404: {
            "description": "Page images not found",
        },
        500: {
            "description": "Internal processing error",
        },
    },
)
async def structure_labelling(
    request: StructureLabellingRequest,
) -> ApiResponse[StructureLabellingResult]:
    """Extract document structure and link labels to fields.

    Args:
        request: Structure labelling request with page images and candidates

    Returns:
        ApiResponse containing StructureLabellingResult with fields and evidence

    Raises:
        HTTPException: If processing fails
    """
    import time

    start_time = time.time()

    try:
        # Create service instance
        service = _create_service()

        # Process the request
        result = await service.process(request)

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Check for complete failure
        if not result.success and result.errors:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Processing failed: {'; '.join(result.errors)}",
            )

        return ApiResponse(
            success=True,
            data=result,
            error=None,
            meta={
                "processing_time_ms": processing_time_ms,
                "field_count": len(result.fields),
                "evidence_count": len(result.evidence),
            },
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page images not found: {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {e}",
        )
    except HTTPException:
        raise
    except Exception as e:
        # Log the error in production
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error during structure labelling: {e}",
        )
