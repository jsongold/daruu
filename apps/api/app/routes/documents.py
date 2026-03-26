"""Document routes."""

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.config import get_settings
from app.infrastructure.observability import get_logger
from app.models import (
    ApiResponse,
    Document,
    DocumentResponse,
    DocumentType,
)
from app.models.acroform import AcroFormFieldsResponse
from app.services import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])
logger = get_logger("documents")


def get_document_service() -> DocumentService:
    """Get document service instance."""
    return DocumentService()


@router.post(
    "",
    response_model=ApiResponse[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(..., description="PDF or image file to upload"),
    document_type: DocumentType = Form(..., description="Type of document (source or target)"),
) -> ApiResponse[DocumentResponse]:
    """Upload a document (source or target PDF/image).

    Accepts multipart/form-data with:
    - file: The PDF or image file (PNG, JPEG, TIFF, WebP)
    - document_type: Either "source" or "target"

    Image files are automatically converted to PDF for processing.
    Returns document ID, reference, and metadata.
    """
    settings = get_settings()

    # Validate file
    if file.filename is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size} bytes",
        )

    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in settings.allowed_mime_types:
        # Check by file signature for PDF
        is_pdf = content.startswith(b"%PDF")
        # Check by file signature for images
        is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = content.startswith(b"\xff\xd8\xff")
        is_tiff = content.startswith(b"II*\x00") or content.startswith(b"MM\x00*")
        is_webp = content[0:4] == b"RIFF" and content[8:12] == b"WEBP"
        
        if not (is_pdf or is_png or is_jpeg or is_tiff or is_webp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed types: {settings.allowed_mime_types}",
            )

    # NOTE:
    # Some PDFs contain an /Encrypt dictionary even when they can be opened without
    # prompting for a password (e.g., encrypted with an empty password or with only
    # owner permissions set). A raw "/Encrypt" byte check causes false positives.
    #
    # We do NOT reject uploads based on "/Encrypt" presence here.
    # Downstream PDF parsing/rendering should surface a proper error if the PDF
    # truly requires a password to open.

    # Upload document
    service = get_document_service()

    logger.info(
        "Document upload started",
        request_type="upload_document",
        filename=file.filename,
        document_type=document_type.value,
        content_type=content_type,
        file_size_bytes=len(content),
    )

    try:
        result = await service.upload_document(
            content=content,
            filename=file.filename,
            document_type=document_type,
        )
    except Exception as e:
        logger.error(
            "Document upload failed",
            request_type="upload_document",
            filename=file.filename,
            document_type=document_type.value,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )

    logger.info(
        "Document upload completed",
        request_type="upload_document",
        document_id=result.document_id,
        document_type=document_type.value,
        page_count=result.meta.page_count,
        file_size_bytes=result.meta.file_size,
        mime_type=result.meta.mime_type,
    )

    return ApiResponse(
        success=True,
        data=result,
        meta={"document_type": document_type.value},
    )


@router.get("/{document_id}", response_model=ApiResponse[Document])
async def get_document(document_id: str) -> ApiResponse[Document]:
    """Get document metadata by ID."""
    logger.debug(
        "Get document request",
        request_type="get_document",
        document_id=document_id,
    )

    service = get_document_service()
    document = service.get_document(document_id)

    if document is None:
        logger.warning(
            "Document not found",
            request_type="get_document",
            document_id=document_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    logger.debug(
        "Get document completed",
        request_type="get_document",
        document_id=document_id,
        document_type=document.document_type.value,
        page_count=document.meta.page_count,
    )

    return ApiResponse(success=True, data=document)


@router.get("/{document_id}/pages/{page}/preview")
async def get_page_preview(document_id: str, page: int) -> FileResponse:
    """Get a preview image for a specific page.

    Returns a PNG image of the page.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page number must be >= 1",
        )

    service = get_document_service()

    # Check document exists
    document = service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    # Check page is valid
    if page > document.meta.page_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page {page} not found. Document has {document.meta.page_count} pages",
        )

    # Get preview content
    preview_content = service.get_preview_content(document_id, page)
    if preview_content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Preview not available for page {page}",
        )

    # Verify content is not empty
    if len(preview_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preview file is empty for page {page}",
        )

    return Response(
        content=preview_content,
        media_type="image/png",
    )


@router.get(
    "/{document_id}/acroform-fields",
    response_model=ApiResponse[AcroFormFieldsResponse],
)
async def get_acroform_fields(document_id: str) -> ApiResponse[AcroFormFieldsResponse]:
    """Get AcroForm field information for a document.

    Returns field names, types, values, and bounding boxes for all
    AcroForm fields in the PDF. Coordinates are transformed to screen
    coordinates (top-left origin) for overlay rendering.

    If the PDF has no AcroForm fields, returns has_acroform=false with
    empty fields list.
    """
    logger.info(
        "AcroForm fields request",
        request_type="get_acroform_fields",
        document_id=document_id,
    )

    service = get_document_service()

    # Check document exists
    document = service.get_document(document_id)
    if document is None:
        logger.warning(
            "Document not found for AcroForm extraction",
            request_type="get_acroform_fields",
            document_id=document_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    # Get AcroForm fields
    result = service.get_acroform_fields(document_id)
    if result is None:
        logger.warning(
            "Failed to extract AcroForm fields",
            request_type="get_acroform_fields",
            document_id=document_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    # Log important AcroForm extraction results
    field_types_count: dict[str, int] = {}
    for field in result.fields:
        field_types_count[field.field_type] = field_types_count.get(field.field_type, 0) + 1

    logger.info(
        "AcroForm fields extracted",
        request_type="get_acroform_fields",
        document_id=document_id,
        has_acroform=result.has_acroform,
        total_fields=len(result.fields),
        page_count=len(result.page_dimensions),
        preview_scale=result.preview_scale,
        field_types=field_types_count,
        readonly_fields=sum(1 for f in result.fields if f.readonly),
        fields_with_value=sum(1 for f in result.fields if f.value),
    )

    return ApiResponse(success=True, data=result)


@router.get(
    "/{document_id}/text-blocks",
)
async def get_text_blocks(
    document_id: str,
    page: int | None = None,
) -> ApiResponse:
    """Extract text blocks (labels) from a PDF document.

    Returns text spans with bounding boxes in PDF coordinates.
    Each block has: id, text, page, bbox [x, y, width, height],
    font_name, font_size.

    Query params:
        page: Optional 1-indexed page number to filter by.
    """
    logger.info(
        "Text blocks request",
        request_type="get_text_blocks",
        document_id=document_id,
        page=page,
    )

    service = get_document_service()

    document = service.get_document(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    pages_filter = [page] if page is not None else None
    blocks = service.extract_text_blocks(document_id, pages=pages_filter)

    logger.info(
        "Text blocks extracted",
        request_type="get_text_blocks",
        document_id=document_id,
        total_blocks=len(blocks),
    )

    return ApiResponse(success=True, data={"blocks": blocks})
