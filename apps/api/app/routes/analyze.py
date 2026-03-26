"""Analyze document routes.

POST /api/v1/analyze - Analyze document structure and detect fields/anchors.
Uses LLM for label-to-position linking (Structure/Labelling phase).
"""

from fastapi import APIRouter, HTTPException, status

from app.adapters.dto.analyze import (
    AnalyzeRequestDTO,
    AnalyzeResponseDTO,
)
from app.models import ApiResponse

router = APIRouter(tags=["analyze"])


@router.post(
    "/analyze",
    response_model=ApiResponse[AnalyzeResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Analyze document structure",
    description="""
Analyze document structure and detect fields/anchors.

This endpoint uses LLM for label-to-position linking, which is critical for:
- Handling label text variations across document versions
- Resolving multiple candidates for the same semantic field
- Interpreting table/form structures
- Understanding nested box relationships

The analysis process:
1. Extract page images from the document
2. Run OCR/detection to find labels and input boxes
3. Use LLM to link labels to field positions
4. Return detected fields with confidence scores
""",
)
async def analyze_document(
    request: AnalyzeRequestDTO,
) -> ApiResponse[AnalyzeResponseDTO]:
    """Analyze document structure and detect fields/anchors.

    Args:
        request: Analysis request with document ID and options

    Returns:
        Analysis result with detected fields

    Raises:
        HTTPException: If document not found or analysis fails
    """
    # TODO: Implement with actual document analysis
    # This is a stub that returns an error indicating the feature is not yet implemented

    # Check if document exists
    from app.services import DocumentService

    service = DocumentService()
    document = service.get_document(request.document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {request.document_id}",
        )

    # Return stub response for now
    # In production, this would:
    # 1. Load document and extract page images
    # 2. Run OCR/detection on each page
    # 3. Use LLM to link labels to positions
    # 4. Return detected fields

    return ApiResponse(
        success=True,
        data=AnalyzeResponseDTO(
            document_id=request.document_id,
            fields=[],  # Empty for stub
            page_count=document.meta.page_count,
            has_acroform=False,  # Would detect from PDF
            warnings=[
                "Analysis not yet implemented. "
                "This is a stub endpoint that will be completed with LangChain integration."
            ],
        ),
        meta={
            "stub": True,
            "message": "Full implementation pending LangChain integration",
        },
    )
