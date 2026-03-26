"""Fill Service routes.

POST /api/v1/fill/service - Fill target document with values using the Fill Service.
GET /api/v1/fill/download - Download a filled PDF by reference path.
Supports AcroForm filling or overlay drawing with deterministic behavior.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.infrastructure.repositories import get_file_repository
from app.models import ApiResponse
from app.models.common import BBox
from app.models.fill import (
    FillMethod,
    FillRequest,
    FillResult,
    FillValue,
    RenderParams,
)
from app.repositories import FileRepository
from app.services.fill import (
    FillService,
    LocalStorageAdapter,
    PyMuPdfAcroFormAdapter,
    PyMuPdfMergerAdapter,
    PyMuPdfReaderAdapter,
    ReportlabMeasureAdapter,
    ReportlabOverlayAdapter,
)

router = APIRouter(prefix="/fill", tags=["fill-service"])


# Request/Response DTOs for API layer
class FillValueDTO(BaseModel):
    """A value to fill into a field (API layer)."""

    field_id: str = Field(..., min_length=1, description="Target field ID")
    value: str = Field(..., description="Value to fill")
    x: float | None = Field(None, description="X coordinate (optional bbox)")
    y: float | None = Field(None, description="Y coordinate (optional bbox)")
    width: float | None = Field(None, ge=0, description="Width (optional bbox)")
    height: float | None = Field(None, ge=0, description="Height (optional bbox)")
    page: int | None = Field(None, ge=1, description="Page number (optional bbox)")

    model_config = {"frozen": True}


class RenderParamsDTO(BaseModel):
    """Rendering parameters for overlay drawing (API layer)."""

    font_name: str = Field(default="Helvetica", description="Font family name")
    font_size: float = Field(default=12.0, gt=0, le=200, description="Font size in points")
    font_color: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="RGB color [0-1, 0-1, 0-1]",
    )
    alignment: str = Field(
        default="left",
        description="Text alignment (left, center, right)",
    )
    line_height: float = Field(default=1.2, gt=0, le=5, description="Line height multiplier")
    word_wrap: bool = Field(default=True, description="Enable word wrapping")
    overflow_handling: str = Field(
        default="truncate",
        description="Overflow handling (truncate, shrink, error)",
    )

    model_config = {"frozen": True}


class FillServiceRequestDTO(BaseModel):
    """Request body for POST /api/v1/fill/service.

    Fill target document using the Fill Service with
    deterministic, repeatable behavior.
    """

    target_document_ref: str = Field(
        ..., min_length=1, description="Reference/path to the target PDF"
    )
    fields: list[FillValueDTO] = Field(..., min_length=1, description="Fields and values to fill")
    method: str = Field(
        default="auto",
        description="Fill method: auto, acroform, or overlay",
    )
    render_params: RenderParamsDTO | None = Field(None, description="Default rendering parameters")
    field_params: dict[str, RenderParamsDTO] | None = Field(
        None, description="Field-specific rendering parameters"
    )

    model_config = {"frozen": True}


class FillIssueDTO(BaseModel):
    """An issue detected during filling (API layer)."""

    field_id: str = Field(..., description="Field ID with issue")
    issue_type: str = Field(..., description="Type of issue")
    severity: str = Field(..., description="Severity (info, warning, error)")
    message: str = Field(..., description="Human-readable description")

    model_config = {"frozen": True}


class FieldResultDTO(BaseModel):
    """Result for a single field (API layer)."""

    field_id: str = Field(..., description="Field ID")
    success: bool = Field(..., description="Whether field was filled")
    value_written: str | None = Field(None, description="Value that was written")
    issues: list[FillIssueDTO] = Field(default_factory=list, description="Issues for this field")

    model_config = {"frozen": True}


class FillServiceResponseDTO(BaseModel):
    """Response body for POST /api/v1/fill/service."""

    filled_document_ref: str | None = Field(
        None, description="Reference to filled PDF (if successful)"
    )
    method_used: str = Field(..., description="Method that was used (acroform or overlay)")
    filled_count: int = Field(..., ge=0, description="Number of fields filled")
    failed_count: int = Field(..., ge=0, description="Number of fields that failed")
    field_results: list[FieldResultDTO] = Field(
        default_factory=list, description="Per-field results"
    )
    errors: list[str] = Field(default_factory=list, description="Fatal errors encountered")

    model_config = {"frozen": True}


def get_fill_service() -> FillService:
    """Dependency injection for FillService.

    Creates a configured FillService with all adapters.
    In production, this would be configured with proper paths
    and potentially different adapter implementations.

    Returns:
        Configured FillService instance
    """
    return FillService(
        pdf_reader=PyMuPdfReaderAdapter(),
        acroform_writer=PyMuPdfAcroFormAdapter(),
        overlay_renderer=ReportlabOverlayAdapter(),
        pdf_merger=PyMuPdfMergerAdapter(),
        storage=LocalStorageAdapter(base_path="/tmp/fill-service"),
        text_measure=ReportlabMeasureAdapter(),
    )


# Directory for temporary document downloads
TEMP_DOCUMENT_DIR = Path("/tmp/fill-service/source-docs")
TEMP_DOCUMENT_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_document_ref(
    document_ref: str,
    file_repo: FileRepository,
) -> str:
    """Resolve a document reference to a local file path.

    If the reference is a Supabase URL (starts with 'supabase://'),
    downloads the content to a temporary file and returns the local path.
    Otherwise, assumes it's already a local path.

    Args:
        document_ref: Document reference (Supabase URL or local path).
        file_repo: File repository for downloading from Supabase.

    Returns:
        Local file path to the document.

    Raises:
        HTTPException: If document cannot be loaded.
    """
    # Check if it's a Supabase URL
    if document_ref.startswith("supabase://"):
        # Download from Supabase
        content = file_repo.get_content(document_ref)
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not load document: {document_ref}",
            )

        # Save to temporary file
        temp_filename = f"{uuid.uuid4()}.pdf"
        temp_path = TEMP_DOCUMENT_DIR / temp_filename
        temp_path.write_bytes(content)
        return str(temp_path)

    # Already a local path
    return document_ref


def _dto_to_fill_value(dto: FillValueDTO) -> FillValue:
    """Convert API DTO to domain model.

    Args:
        dto: FillValueDTO from API

    Returns:
        FillValue domain model
    """
    bbox = None
    if all(v is not None for v in [dto.x, dto.y, dto.width, dto.height, dto.page]):
        bbox = BBox(
            x=dto.x,
            y=dto.y,
            width=dto.width,
            height=dto.height,
            page=dto.page,
        )

    return FillValue(
        field_id=dto.field_id,
        value=dto.value,
        bbox=bbox,
    )


def _dto_to_render_params(dto: RenderParamsDTO) -> RenderParams:
    """Convert API DTO to domain model.

    Args:
        dto: RenderParamsDTO from API

    Returns:
        RenderParams domain model
    """
    return RenderParams(
        font_name=dto.font_name,
        font_size=dto.font_size,
        font_color=(dto.font_color[0], dto.font_color[1], dto.font_color[2]),
        alignment=dto.alignment,
        line_height=dto.line_height,
        word_wrap=dto.word_wrap,
        overflow_handling=dto.overflow_handling,
    )


def _result_to_dto(result: FillResult) -> FillServiceResponseDTO:
    """Convert domain model to API DTO.

    Args:
        result: FillResult from service

    Returns:
        FillServiceResponseDTO for API
    """
    field_results = [
        FieldResultDTO(
            field_id=fr.field_id,
            success=fr.success,
            value_written=fr.value_written,
            issues=[
                FillIssueDTO(
                    field_id=issue.field_id,
                    issue_type=issue.issue_type.value,
                    severity=issue.severity.value,
                    message=issue.message,
                )
                for issue in fr.issues
            ],
        )
        for fr in result.field_results
    ]

    errors = [error.message for error in result.errors]

    return FillServiceResponseDTO(
        filled_document_ref=result.filled_document_ref,
        method_used=result.method_used.value,
        filled_count=result.filled_count,
        failed_count=result.failed_count,
        field_results=field_results,
        errors=errors,
    )


@router.post(
    "/service",
    response_model=ApiResponse[FillServiceResponseDTO],
    status_code=status.HTTP_200_OK,
    summary="Fill document using Fill Service",
    description="""
Fill target PDF document with values using the deterministic Fill Service.

This endpoint uses a service-based approach with:
- **Deterministic behavior**: Same input always produces same output
- **No LLM/Agent**: Pure algorithmic text rendering
- **AcroForm support**: Direct form field filling for PDF forms
- **Overlay support**: Text overlay for non-form PDFs

Fill Methods:
- **auto**: Automatically detect AcroForm or use overlay
- **acroform**: Force AcroForm filling (fails if no form fields)
- **overlay**: Force overlay method (works for any PDF)

Quality Checks:
- Overflow detection (text exceeds bounding box)
- Overlap detection (fields overlap each other)
- Truncation reporting (text was cut off)

Returns the reference to the filled PDF and detailed per-field results.
""",
)
async def fill_document_service(
    request: FillServiceRequestDTO,
    service: FillService = Depends(get_fill_service),
    file_repo: FileRepository = Depends(get_file_repository),
) -> ApiResponse[FillServiceResponseDTO]:
    """Fill target document with values using Fill Service.

    Args:
        request: Fill request with document reference and values
        service: Injected FillService instance
        file_repo: File repository for resolving Supabase URLs

    Returns:
        API response with fill result

    Raises:
        HTTPException: If document not found or critical error
    """
    # Validate method
    valid_methods = {"auto", "acroform", "overlay"}
    if request.method not in valid_methods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid fill method: {request.method}. Must be one of: {valid_methods}",
        )

    # Resolve document reference (download from Supabase if needed)
    local_document_path = _resolve_document_ref(request.target_document_ref, file_repo)

    # Convert DTOs to domain models
    fill_values = tuple(_dto_to_fill_value(dto) for dto in request.fields)

    default_render_params = RenderParams()
    if request.render_params:
        default_render_params = _dto_to_render_params(request.render_params)

    field_params = None
    if request.field_params:
        field_params = {
            field_id: _dto_to_render_params(params)
            for field_id, params in request.field_params.items()
        }

    method_map = {
        "auto": FillMethod.AUTO,
        "acroform": FillMethod.ACROFORM,
        "overlay": FillMethod.OVERLAY,
    }

    fill_request = FillRequest(
        target_document_ref=local_document_path,
        fields=fill_values,
        render_params=default_render_params,
        field_params=field_params,
        method=method_map[request.method],
    )

    # Execute fill operation
    result = await service.fill(fill_request)

    # Convert to response DTO
    response_dto = _result_to_dto(result)

    if not result.success:
        # Return error response but with 200 status (operation completed, but with errors)
        return ApiResponse(
            success=False,
            data=response_dto,
            error=(
                "; ".join(response_dto.errors) if response_dto.errors else "Fill operation failed"
            ),
            meta={
                "method_requested": request.method,
                "field_count": len(request.fields),
            },
        )

    return ApiResponse(
        success=True,
        data=response_dto,
        meta={
            "method_requested": request.method,
            "method_used": response_dto.method_used,
            "field_count": len(request.fields),
            "filled_count": response_dto.filled_count,
            "failed_count": response_dto.failed_count,
        },
    )


# Allowed base paths for downloads (security: prevent path traversal)
ALLOWED_DOWNLOAD_PATHS = [
    "/tmp/fill-service",
    "/tmp/fill-artifacts",
]


def _validate_download_path(ref: str) -> Path:
    """Validate that the download path is within allowed directories.

    Args:
        ref: The file reference/path to validate

    Returns:
        Resolved Path object

    Raises:
        HTTPException: If path is invalid or outside allowed directories
    """
    try:
        # Resolve the path to handle any .. or symlinks
        resolved_path = Path(ref).resolve()

        # Check if the path is within any allowed base path
        is_allowed = any(
            str(resolved_path).startswith(allowed_base) for allowed_base in ALLOWED_DOWNLOAD_PATHS
        )

        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this file is not allowed",
            )

        if not resolved_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found",
            )

        if not resolved_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path is not a file",
            )

        return resolved_path

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file path: {e}",
        )


@router.get(
    "/download",
    response_class=FileResponse,
    summary="Download filled PDF",
    description="""
Download a filled PDF document by its reference path.

The reference path is returned from the fill service endpoint as `filled_document_ref`.
Only files within the allowed fill-service directories can be downloaded.
""",
    responses={
        200: {
            "description": "PDF file download",
            "content": {"application/pdf": {}},
        },
        403: {"description": "Access denied - path outside allowed directories"},
        404: {"description": "File not found"},
    },
)
async def download_filled_pdf(
    ref: str = Query(
        ...,
        description="Reference path to the filled PDF (from fill service response)",
        example="/tmp/fill-service/abc123-filled.pdf",
    ),
    filename: str | None = Query(
        None,
        description="Optional custom filename for the download",
        example="my-document-filled.pdf",
    ),
) -> FileResponse:
    """Download a filled PDF by reference path.

    Args:
        ref: Reference path to the filled PDF
        filename: Optional custom filename for the Content-Disposition header

    Returns:
        FileResponse with the PDF file
    """
    # Validate and resolve the path
    file_path = _validate_download_path(ref)

    # Determine the download filename
    download_filename = filename or file_path.name

    # Ensure .pdf extension
    if not download_filename.lower().endswith(".pdf"):
        download_filename += ".pdf"

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=download_filename,
        headers={
            "Content-Disposition": f'attachment; filename="{download_filename}"',
        },
    )
