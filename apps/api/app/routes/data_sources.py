"""Data sources routes for uploading user data.

API version: v2

Endpoints:
- POST   /api/v2/conversations/{id}/data-sources         - Upload file or text
- GET    /api/v2/conversations/{id}/data-sources         - List all sources
- DELETE /api/v2/conversations/{id}/data-sources/{id}    - Remove source
- POST   /api/v2/conversations/{id}/data-sources/{id}/extract - Trigger extraction
"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.infrastructure.repositories import (
    get_conversation_repository,
    get_data_source_repository,
    get_document_repository,
    get_file_repository,
)
from app.models.common import ApiResponse
from app.models.conversation import ErrorCode, ErrorDetail, ErrorResponse
from app.models.data_source import (
    EXTENSION_TYPE_MAP,
    MIME_TYPE_MAP,
    SIZE_LIMITS,
    DataSourceListResponse,
    DataSourceResponse,
    DataSourceType,
    ExtractionResult,
)
from app.repositories import (
    ConversationRepository,
    DataSourceRepository,
    DocumentRepository,
    FileRepository,
)
from app.services.document_service import DocumentService
from app.services.text_extraction_service import TextExtractionService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v2/conversations/{conversation_id}/data-sources",
    tags=["data-sources"],
)


# ============================================
# Dependencies
# ============================================


async def get_current_user_id() -> str:
    """Get the authenticated user ID.

    TODO: Replace with actual auth from Supabase.
    """
    return "stub-user-id"


def get_conversation_repo() -> ConversationRepository:
    """Get the conversation repository."""
    return get_conversation_repository()


def get_data_source_repo() -> DataSourceRepository:
    """Get the data source repository."""
    return get_data_source_repository()


def get_document_repo() -> DocumentRepository:
    """Get the document repository."""
    return get_document_repository()


def get_file_repo() -> FileRepository:
    """Get the file repository."""
    return get_file_repository()


def get_document_service(
    doc_repo: DocumentRepository = Depends(get_document_repo),
    file_repo: FileRepository = Depends(get_file_repo),
) -> DocumentService:
    """Get the document service."""
    return DocumentService(document_repository=doc_repo, file_repository=file_repo)


def get_text_extraction_service(
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    document_service: DocumentService = Depends(get_document_service),
) -> TextExtractionService:
    """Get the text extraction service."""
    return TextExtractionService(
        data_source_repo=data_source_repo,
        document_service=document_service,
    )


# ============================================
# Helper Functions
# ============================================


def _get_data_source_type(filename: str, content_type: str | None) -> DataSourceType | None:
    """Determine data source type from filename and content type.

    Args:
        filename: Original filename.
        content_type: MIME type.

    Returns:
        DataSourceType if recognized, None otherwise.
    """
    # Try MIME type first
    if content_type and content_type in MIME_TYPE_MAP:
        return MIME_TYPE_MAP[content_type]

    # Fall back to extension
    ext = Path(filename).suffix.lower()
    return EXTENSION_TYPE_MAP.get(ext)


def _generate_preview(content: str, max_length: int = 500) -> str:
    """Generate a preview of text content.

    Args:
        content: Full text content.
        max_length: Maximum preview length.

    Returns:
        Preview string, truncated if necessary.
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


# ============================================
# Route Handlers
# ============================================


@router.post(
    "",
    response_model=ApiResponse[DataSourceResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a data source (file or text)",
    responses={
        201: {"description": "Data source created"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
        413: {"model": ErrorResponse, "description": "File too large"},
    },
)
async def create_data_source(
    conversation_id: str,
    file: Annotated[UploadFile | None, File(description="File to upload")] = None,
    text_name: Annotated[str | None, Form(description="Name for text data source")] = None,
    text_content: Annotated[str | None, Form(description="Text content")] = None,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    document_service: DocumentService = Depends(get_document_service),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
) -> ApiResponse[DataSourceResponse]:
    """Upload a data source for AI form filling.

    Accepts either a file upload or text content (not both).
    Supported file types: PDF, PNG, JPG, TIFF, WebP, TXT, CSV.

    For text input, provide text_name and text_content.
    For file upload, provide the file parameter.
    """
    # TODO: Re-enable conversation verification when using persistent storage
    # For now, skip verification since conversations are in-memory and may not persist
    # conversation = conversation_repo.get_by_user(user_id, conversation_id)
    # if conversation is None:
    #     raise HTTPException(
    #         status_code=status.HTTP_404_NOT_FOUND,
    #         detail=ErrorResponse(
    #             error=ErrorDetail(
    #                 code=ErrorCode.CONVERSATION_NOT_FOUND,
    #                 message="Conversation not found",
    #             )
    #         ).model_dump(),
    #     )

    # Validate input - must have either file or text
    if file is None and text_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either file or text_content must be provided",
        )

    if file is not None and text_content is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot provide both file and text_content",
        )

    # Handle text input
    if text_content is not None:
        name = text_name or "Text Input"

        # Check size limit
        content_size = len(text_content.encode("utf-8"))
        if content_size > SIZE_LIMITS[DataSourceType.TEXT]:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.FILE_TOO_LARGE,
                        message=f"Text content exceeds {SIZE_LIMITS[DataSourceType.TEXT] // (1024 * 1024)}MB limit",
                    )
                ).model_dump(),
            )

        # Create data source for text
        data_source = data_source_repo.create(
            conversation_id=conversation_id,
            source_type=DataSourceType.TEXT,
            name=name,
            text_content=text_content,
            content_preview=_generate_preview(text_content),
            file_size_bytes=content_size,
            mime_type="text/plain",
        )

        # Eager extraction: extract immediately so autofill skips re-extraction
        try:
            result = extraction_service.extract_from_data_source(data_source)
            saved = dict(result.extracted_fields) if result.extracted_fields else {}
            if result.raw_text:
                saved["_raw_text"] = result.raw_text
            data_source_repo.update_extracted_data(data_source.id, saved)
            logger.info(
                "Eager extraction OK for text source %s: %d fields, raw_text=%s",
                data_source.id,
                len(saved) - (1 if "_raw_text" in saved else 0),
                "yes" if "_raw_text" in saved else "no",
            )
        except Exception:
            logger.warning(
                "Eager extraction failed for text source %s", data_source.id, exc_info=True
            )

        logger.info(f"Created text data source {data_source.id} for conversation {conversation_id}")

        return ApiResponse(
            success=True,
            data=DataSourceResponse.from_data_source(data_source),
        )

    # Handle file upload
    if file is not None:
        filename = file.filename or "unknown"

        # Determine file type
        source_type = _get_data_source_type(filename, file.content_type)
        if source_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.INVALID_FILE_TYPE,
                        message="Unsupported file type. Supported: PDF, PNG, JPG, TIFF, WebP, TXT, CSV",
                    )
                ).model_dump(),
            )

        # Check file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > SIZE_LIMITS[source_type]:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code=ErrorCode.FILE_TOO_LARGE,
                        message=f"File exceeds {SIZE_LIMITS[source_type] // (1024 * 1024)}MB limit",
                    )
                ).model_dump(),
            )

        # Read file content
        file_content = await file.read()

        # Handle text-based files differently (store content directly)
        if source_type in (DataSourceType.TEXT, DataSourceType.CSV):
            try:
                text_content = file_content.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Text file must be UTF-8 encoded",
                )

            data_source = data_source_repo.create(
                conversation_id=conversation_id,
                source_type=source_type,
                name=filename,
                text_content=text_content,
                content_preview=_generate_preview(text_content),
                file_size_bytes=file_size,
                mime_type=file.content_type or "text/plain",
            )

            # Eager extraction for text/CSV file sources
            try:
                result = extraction_service.extract_from_data_source(data_source)
                saved = dict(result.extracted_fields) if result.extracted_fields else {}
                if result.raw_text:
                    saved["_raw_text"] = result.raw_text
                data_source_repo.update_extracted_data(data_source.id, saved)
                logger.info(
                    "Eager extraction OK for %s file source %s: %d fields, raw_text=%s",
                    source_type.value,
                    data_source.id,
                    len(saved) - (1 if "_raw_text" in saved else 0),
                    "yes" if "_raw_text" in saved else "no",
                )
            except Exception:
                logger.warning(
                    "Eager extraction failed for %s source %s",
                    source_type.value,
                    data_source.id,
                    exc_info=True,
                )

            logger.info(
                f"Created {source_type.value} data source {data_source.id} "
                f"for conversation {conversation_id}"
            )

            return ApiResponse(
                success=True,
                data=DataSourceResponse.from_data_source(data_source),
            )

        # Handle binary files (PDF, images) - upload as document
        document = await document_service.upload_document(
            content=file_content,
            filename=filename,
            document_type="source",
        )

        # Create data source linked to document
        data_source = data_source_repo.create(
            conversation_id=conversation_id,
            source_type=source_type,
            name=filename,
            document_id=document.id,
            file_size_bytes=file_size,
            mime_type=file.content_type or document.meta.mime_type,
        )

        # Eager extraction for PDF/image sources (document already uploaded)
        try:
            result = extraction_service.extract_from_data_source(data_source)
            saved = dict(result.extracted_fields) if result.extracted_fields else {}
            if result.raw_text:
                saved["_raw_text"] = result.raw_text
            data_source_repo.update_extracted_data(data_source.id, saved)
            logger.info(
                "Eager extraction OK for %s source %s: %d fields, raw_text=%d chars",
                source_type.value,
                data_source.id,
                len(saved) - (1 if "_raw_text" in saved else 0),
                len(saved.get("_raw_text", "")),
            )
        except Exception:
            logger.warning(
                "Eager extraction failed for %s source %s",
                source_type.value,
                data_source.id,
                exc_info=True,
            )

        logger.info(
            f"Created {source_type.value} data source {data_source.id} "
            f"(document: {document.id}) for conversation {conversation_id}"
        )

        return ApiResponse(
            success=True,
            data=DataSourceResponse.from_data_source(data_source),
        )

    # Should not reach here
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid request",
    )


@router.get(
    "",
    response_model=ApiResponse[DataSourceListResponse],
    summary="List data sources for a conversation",
    responses={
        200: {"description": "List of data sources"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def list_data_sources(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
) -> ApiResponse[DataSourceListResponse]:
    """List all data sources for a conversation.

    Returns data sources ordered by creation time (newest first).
    """
    # TODO: Re-enable conversation verification when using persistent storage
    # conversation = conversation_repo.get_by_user(user_id, conversation_id)
    # if conversation is None:
    #     raise HTTPException(...)

    # Get data sources
    data_sources = data_source_repo.list_by_conversation(conversation_id)
    total = data_source_repo.count_by_conversation(conversation_id)

    return ApiResponse(
        success=True,
        data=DataSourceListResponse(
            items=[DataSourceResponse.from_data_source(ds) for ds in data_sources],
            total=total,
        ),
    )


@router.delete(
    "/{data_source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a data source",
    responses={
        204: {"description": "Data source deleted"},
        404: {"model": ErrorResponse, "description": "Data source not found"},
    },
)
async def delete_data_source(
    conversation_id: str,
    data_source_id: str,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
) -> None:
    """Delete a data source.

    Note: This does not delete the underlying document if one exists.
    """
    # TODO: Re-enable conversation verification when using persistent storage
    # conversation = conversation_repo.get_by_user(user_id, conversation_id)
    # if conversation is None:
    #     raise HTTPException(...)

    # Delete data source
    deleted = data_source_repo.delete(data_source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )

    logger.info(f"Deleted data source {data_source_id} from conversation {conversation_id}")


@router.post(
    "/{data_source_id}/extract",
    response_model=ApiResponse[ExtractionResult],
    summary="Trigger extraction from a data source",
    responses={
        200: {"description": "Extraction result"},
        404: {"model": ErrorResponse, "description": "Data source not found"},
    },
)
async def extract_from_data_source(
    conversation_id: str,
    data_source_id: str,
    force: bool = False,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
) -> ApiResponse[ExtractionResult]:
    """Trigger extraction from a data source.

    Extracts structured data from the data source.
    Results are cached in the data source record.

    Args:
        force: If True, re-extract even if cached results exist.
    """
    # TODO: Re-enable conversation verification when using persistent storage
    # conversation = conversation_repo.get_by_user(user_id, conversation_id)
    # if conversation is None:
    #     raise HTTPException(...)

    # Get data source
    data_source = data_source_repo.get(data_source_id)
    if data_source is None or data_source.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )

    # Check if we have cached extraction (unless force is True)
    if data_source.extracted_data and not force:
        logger.info(f"Returning cached extraction for data source {data_source_id}")
        return ApiResponse(
            success=True,
            data=ExtractionResult(
                data_source_id=data_source_id,
                extracted_fields=data_source.extracted_data,
                confidence=1.0,  # Cached results have full confidence
                raw_text=data_source.text_content,
            ),
        )

    # Perform extraction using the service
    logger.info(f"Extracting data from data source {data_source_id}")
    extraction_result = extraction_service.extract_from_data_source(data_source)

    # Cache the extraction results if we got any fields
    if extraction_result.extracted_fields:
        data_source_repo.update_extracted_data(
            data_source_id=data_source_id,
            extracted_data=extraction_result.extracted_fields,
        )
        logger.info(
            f"Cached {len(extraction_result.extracted_fields)} extracted fields "
            f"for data source {data_source_id}"
        )

    return ApiResponse(
        success=True,
        data=extraction_result,
    )


@router.post(
    "/extract-all",
    response_model=ApiResponse[dict],
    summary="Extract and combine data from all sources",
    responses={
        200: {"description": "Combined extraction result"},
        404: {"model": ErrorResponse, "description": "Conversation not found"},
    },
)
async def extract_from_all_data_sources(
    conversation_id: str,
    force: bool = False,
    user_id: str = Depends(get_current_user_id),
    conversation_repo: ConversationRepository = Depends(get_conversation_repo),
    data_source_repo: DataSourceRepository = Depends(get_data_source_repo),
    extraction_service: TextExtractionService = Depends(get_text_extraction_service),
) -> ApiResponse[dict]:
    """Extract data from all sources and combine results.

    Useful for autofill - combines extracted fields from all data sources.
    Higher confidence sources take precedence for duplicate fields.

    Args:
        force: If True, re-extract even if cached results exist.
    """
    # TODO: Re-enable conversation verification when using persistent storage
    # conversation = conversation_repo.get_by_user(user_id, conversation_id)
    # if conversation is None:
    #     raise HTTPException(...)

    # Get all data sources
    data_sources = data_source_repo.list_by_conversation(conversation_id)

    if not data_sources:
        return ApiResponse(
            success=True,
            data={
                "combined_fields": {},
                "source_count": 0,
                "total_fields": 0,
            },
        )

    # Extract from each source
    extractions = []
    for data_source in data_sources:
        # Use cached if available and not forcing
        if data_source.extracted_data and not force:
            extractions.append(
                ExtractionResult(
                    data_source_id=data_source.id,
                    extracted_fields=data_source.extracted_data,
                    confidence=1.0,
                    raw_text=data_source.text_content,
                )
            )
        else:
            # Perform extraction
            result = extraction_service.extract_from_data_source(data_source)
            extractions.append(result)

            # Cache if we got results
            if result.extracted_fields:
                data_source_repo.update_extracted_data(
                    data_source_id=data_source.id,
                    extracted_data=result.extracted_fields,
                )

    # Combine all extractions
    combined = extraction_service.combine_extractions(extractions)

    logger.info(
        f"Combined extraction from {len(data_sources)} sources: "
        f"{len(combined)} fields for conversation {conversation_id}"
    )

    return ApiResponse(
        success=True,
        data={
            "combined_fields": combined,
            "source_count": len(data_sources),
            "total_fields": len(combined),
        },
    )
