"""Ingest routes for PDF normalization.

This module provides the REST API for the Ingest service:
- POST /ingest - Normalize a PDF document

The ingest service is deterministic (no LLM) and handles:
- PDF validation
- Metadata extraction
- Page rendering to images
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_settings
from app.models import ApiResponse
from app.models.ingest import (
    IngestErrorCode,
    IngestRequest,
    IngestResult,
)
from app.services.ingest import IngestService
from app.services.ingest.adapters import LocalStorageAdapter, PyMuPdfAdapter

router = APIRouter(prefix="/ingest", tags=["ingest"])


def get_ingest_service() -> IngestService:
    """Get ingest service instance with adapters.

    Creates a new IngestService with:
    - PyMuPdfAdapter for PDF reading/rendering
    - LocalStorageAdapter for artifact storage

    Returns:
        Configured IngestService instance
    """
    settings = get_settings()

    # Configure storage path from settings or use default
    storage_path = str(settings.upload_dir / "ingest-artifacts")

    pdf_reader = PyMuPdfAdapter()
    storage = LocalStorageAdapter(base_path=storage_path)

    return IngestService(pdf_reader=pdf_reader, storage=storage)


@router.post(
    "",
    response_model=ApiResponse[IngestResult],
    status_code=status.HTTP_200_OK,
    summary="Ingest a PDF document",
    description="""
    Normalize a PDF document for downstream processing.

    This endpoint:
    1. Validates the PDF file (format, structure, password)
    2. Extracts metadata (page count, dimensions, rotation)
    3. Renders pages to images for LLM/OCR processing
    4. Stores rendered artifacts

    The service is deterministic - same input produces same output.
    """,
    responses={
        200: {
            "description": "Ingestion completed (check success field for status)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "document_id": "doc-123",
                            "success": True,
                            "meta": {
                                "page_count": 3,
                                "pages": [
                                    {
                                        "page_number": 1,
                                        "width": 612.0,
                                        "height": 792.0,
                                        "rotation": 0,
                                    }
                                ],
                            },
                            "artifacts": [
                                {
                                    "page_number": 1,
                                    "image_ref": "/artifacts/doc-123/page_1.png",
                                    "width": 1275,
                                    "height": 1650,
                                    "dpi": 150,
                                }
                            ],
                            "errors": [],
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid request parameters",
        },
        500: {
            "description": "Internal server error during processing",
        },
    },
)
async def ingest_document(
    request: IngestRequest,
    service: IngestService = Depends(get_ingest_service),
) -> ApiResponse[IngestResult]:
    """Ingest a PDF document.

    Validates the document, extracts metadata, and renders pages
    to images for downstream processing.

    Args:
        request: Ingest request with document ID and reference
        service: Injected IngestService instance

    Returns:
        ApiResponse containing IngestResult with metadata and artifacts
    """
    try:
        result = await service.ingest(request)

        # Map certain error codes to HTTP errors for clarity
        if not result.success and result.errors:
            first_error = result.errors[0]

            # Password-protected PDFs should return 400
            if first_error.code == IngestErrorCode.PASSWORD_PROTECTED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=first_error.message,
                )

            # Invalid PDFs should return 400
            if first_error.code in (
                IngestErrorCode.INVALID_PDF,
                IngestErrorCode.CORRUPTED_FILE,
                IngestErrorCode.EMPTY_DOCUMENT,
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=first_error.message,
                )

        return ApiResponse(
            success=result.success,
            data=result,
            meta={
                "document_id": request.document_id,
                "pages_rendered": len(result.artifacts),
                "errors_count": len(result.errors),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )


@router.get(
    "/{document_id}/metadata",
    response_model=ApiResponse[IngestResult],
    status_code=status.HTTP_200_OK,
    summary="Get document metadata only",
    description="""
    Extract metadata from a PDF without rendering pages.

    This is a lightweight operation for getting document info
    without the overhead of page rendering.
    """,
)
async def get_document_metadata(
    document_id: str,
    document_ref: str,
    service: IngestService = Depends(get_ingest_service),
) -> ApiResponse[IngestResult]:
    """Get document metadata without rendering.

    Args:
        document_id: Document identifier
        document_ref: Reference/path to the PDF file
        service: Injected IngestService instance

    Returns:
        ApiResponse containing IngestResult with metadata only
    """
    try:
        result = await service.get_metadata(document_ref)

        # Update document_id in result (get_metadata doesn't have access to it)
        result_with_id = IngestResult(
            document_id=document_id,
            success=result.success,
            meta=result.meta,
            artifacts=result.artifacts,
            errors=result.errors,
        )

        return ApiResponse(
            success=result_with_id.success,
            data=result_with_id,
            meta={"document_id": document_id},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract metadata: {str(e)}",
        )
