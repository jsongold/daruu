"""Extract values routes.

POST /api/v1/extract - Extract values from source document.
Uses OCR if needed, LLM for ambiguity resolution.
"""

from fastapi import APIRouter, HTTPException, status

from app.adapters.dto.extract import (
    ExtractRequestDTO,
    ExtractResponseDTO,
)
from app.models import ApiResponse

router = APIRouter(tags=["extract"])


@router.post(
    "/extract",
    response_model=ApiResponse[ExtractResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Extract values from document",
    description="""
Extract values from a source document.

The extraction pipeline follows these steps:
1. Try native PDF text extraction
2. If missing/low-confidence: Run OCR on field region
3. If still ambiguous: Use LLM for resolution/normalization
4. Compute confidence and mark for review if needed

LLM is used for:
- Ambiguity resolution (multiple candidates)
- Value normalization (dates, addresses, names)
- Conflict detection
- Question generation for missing fields
""",
)
async def extract_values(
    request: ExtractRequestDTO,
) -> ApiResponse[ExtractResponseDTO]:
    """Extract values from source document.

    Args:
        request: Extraction request with document ID and options

    Returns:
        Extraction result with values and confidence scores

    Raises:
        HTTPException: If document not found or extraction fails
    """
    # TODO: Implement with actual value extraction
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

    # Return stub response
    # In production, this would:
    # 1. Load document
    # 2. Try native PDF text extraction
    # 3. Run OCR on specified fields if needed
    # 4. Use LLM for ambiguity resolution
    # 5. Return extracted values with evidence

    return ApiResponse(
        success=True,
        data=ExtractResponseDTO(
            document_id=request.document_id,
            extractions=[],  # Empty for stub
            failed_fields=[],
            needs_questions=[],
            warnings=[
                "Extraction not yet implemented. "
                "This is a stub endpoint that will be completed with OCR and LangChain integration."
            ],
        ),
        meta={
            "stub": True,
            "use_ocr": request.use_ocr,
            "confidence_threshold": request.confidence_threshold,
        },
    )
