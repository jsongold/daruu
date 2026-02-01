"""Fill document routes.

POST /api/v1/fill - Fill target document with values.
Supports AcroForm filling or overlay drawing.
"""

from fastapi import APIRouter, HTTPException, status

from app.adapters.dto.fill import (
    FillRequestDTO,
    FillResponseDTO,
)
from app.models import ApiResponse

router = APIRouter(tags=["fill"])


@router.post(
    "/fill",
    response_model=ApiResponse[FillResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Fill document with values",
    description="""
Fill target document with extracted or provided values.

Supports two fill methods:
- **acroform**: Direct AcroForm field filling for PDF forms
- **overlay**: Coordinate-based text overlay for non-form PDFs
- **auto**: Automatically detect and use the best method

Quality checks performed:
- Overflow detection (text exceeds bounding box)
- Overlap detection (text overlaps other fields)
- Font embedding for consistent display

Returns the URL to download the filled PDF.
""",
)
async def fill_document(
    request: FillRequestDTO,
) -> ApiResponse[FillResponseDTO]:
    """Fill target document with values.

    Args:
        request: Fill request with values and rendering parameters

    Returns:
        Fill result with output URL and any issues

    Raises:
        HTTPException: If document not found or filling fails
    """
    # TODO: Implement with actual document filling
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

    # Validate fill method
    valid_methods = {"auto", "acroform", "overlay"}
    if request.method not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid fill method: {request.method}. Must be one of: {valid_methods}",
        )

    # Return stub response
    # In production, this would:
    # 1. Load target document
    # 2. Detect if AcroForm is available (for auto method)
    # 3. Fill fields using appropriate method
    # 4. Check for overflow/overlap issues
    # 5. Save and return output URL

    return ApiResponse(
        success=True,
        data=FillResponseDTO(
            document_id=request.document_id,
            output_url="",  # Would be actual URL in production
            filled_count=0,
            failed_count=len(request.values),  # All fail in stub
            issues=[],
            method_used="none",  # Stub
        ),
        meta={
            "stub": True,
            "requested_method": request.method,
            "value_count": len(request.values),
            "message": "Fill not yet implemented. "
            "This is a stub endpoint that will be completed with PDF writing integration.",
        },
    )
