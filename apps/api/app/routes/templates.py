"""Template API routes (v2 API).

Provides endpoints for template management and matching.
These endpoints are part of the Phase 2 Template System for
the Agent Chat UI.

Endpoints:
- POST /api/v2/templates - Create a new template
- GET /api/v2/templates - List templates
- GET /api/v2/templates/{id} - Get template details
- DELETE /api/v2/templates/{id} - Delete a template
- POST /api/v2/templates/match - Find matching templates
"""

import base64
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.infrastructure.adapters import MemoryEmbedding, MemoryVectorDB
from app.infrastructure.observability import get_logger
from app.infrastructure.repositories.memory_template_repository import (
    MemoryTemplateRepository,
)
from app.models.template import (
    TemplateBbox,
    TemplateCreate,
    TemplateDetailResponse,
    TemplateListResponse,
    TemplateMatchResponse,
    TemplateResponse,
    TemplateRule,
    TemplateUpdate,
)
from app.services.template import TemplateService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v2/templates",
    tags=["templates"],
)


# Singleton instances for dependencies
# In production, these would be replaced with Supabase/production implementations
_template_repo: MemoryTemplateRepository | None = None
_vector_db: MemoryVectorDB | None = None
_embedding: MemoryEmbedding | None = None
_template_service: TemplateService | None = None


def get_template_service() -> TemplateService:
    """Get the template service singleton.

    Returns:
        TemplateService instance with dependencies injected.
    """
    global _template_repo, _vector_db, _embedding, _template_service

    if _template_service is None:
        if _template_repo is None:
            _template_repo = MemoryTemplateRepository()
        if _vector_db is None:
            _vector_db = MemoryVectorDB()
        if _embedding is None:
            _embedding = MemoryEmbedding()

        _template_service = TemplateService(
            template_repo=_template_repo,
            vector_db=_vector_db,
            embedding_gateway=_embedding,
        )
        logger.info("Initialized template service")

    return _template_service


# Request/Response models for API


class CreateTemplateRequest(BaseModel):
    """Request body for creating a template."""

    name: str = Field(..., min_length=1, max_length=200, description="Template name")
    form_type: str = Field(..., min_length=1, max_length=50, description="Form type")
    bboxes: list[TemplateBbox] = Field(default_factory=list, description="Field positions")
    rules: list[TemplateRule] = Field(default_factory=list, description="Validation rules")
    preview_url: str | None = Field(None, description="Preview image URL")
    tenant_id: str | None = Field(None, description="Tenant ID")
    page_image_base64: str | None = Field(
        None, description="Base64-encoded page image for embedding"
    )


class UpdateTemplateRequest(BaseModel):
    """Request body for updating a template."""

    name: str | None = Field(None, max_length=200, description="Template name")
    form_type: str | None = Field(None, max_length=50, description="Form type")
    bboxes: list[TemplateBbox] | None = Field(None, description="Field positions")
    rules: list[TemplateRule] | None = Field(None, description="Validation rules")
    preview_url: str | None = Field(None, description="Preview image URL")
    page_image_base64: str | None = Field(
        None, description="Base64-encoded page image for embedding"
    )


class MatchTemplateRequest(BaseModel):
    """Request body for template matching."""

    page_image_base64: str | None = Field(None, description="Base64-encoded page image")
    page_image_ref: str | None = Field(None, description="Reference to stored page image")
    page_text: str | None = Field(None, description="Extracted text for hybrid matching")
    limit: int = Field(default=3, ge=1, le=10, description="Maximum matches")
    threshold: float = Field(default=0.8, ge=0.0, le=1.0, description="Minimum similarity")
    tenant_id: str | None = Field(None, description="Filter by tenant")


class ApiResponse(BaseModel):
    """Standard API response wrapper."""

    success: bool = Field(..., description="Whether the request succeeded")
    data: Any | None = Field(None, description="Response data")
    error: str | None = Field(None, description="Error message if failed")


def _template_to_response(template: Any) -> TemplateResponse:
    """Convert Template model to API response."""
    return TemplateResponse(
        id=template.id,
        name=template.name,
        form_type=template.form_type,
        field_count=template.field_count,
        preview_url=template.preview_url,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _template_to_detail_response(template: Any) -> TemplateDetailResponse:
    """Convert Template model to detailed API response."""
    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        form_type=template.form_type,
        bboxes=template.bboxes,
        rules=template.rules,
        field_count=template.field_count,
        preview_url=template.preview_url,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.post(
    "",
    response_model=ApiResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a template",
    description="Create a new template with optional visual embedding.",
)
async def create_template(
    request: CreateTemplateRequest,
    service: Annotated[TemplateService, Depends(get_template_service)],
) -> ApiResponse:
    """Create a new template.

    Args:
        request: Template creation request.
        service: Injected template service.

    Returns:
        Created template details.
    """
    # Decode page image if provided
    page_image: bytes | None = None
    if request.page_image_base64:
        try:
            page_image = base64.b64decode(request.page_image_base64)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image data: {str(e)}",
            )

    create_request = TemplateCreate(
        name=request.name,
        form_type=request.form_type,
        bboxes=request.bboxes,
        rules=request.rules,
        preview_url=request.preview_url,
        tenant_id=request.tenant_id,
    )

    template = await service.create_template(
        request=create_request,
        page_image=page_image,
    )

    logger.info("Template created via API", template_id=template.id)

    return ApiResponse(
        success=True,
        data=_template_to_detail_response(template).model_dump(),
    )


@router.get(
    "",
    response_model=TemplateListResponse,
    summary="List templates",
    description="List all templates, optionally filtered by tenant.",
)
async def list_templates(
    tenant_id: str | None = None,
    service: TemplateService = Depends(get_template_service),
) -> TemplateListResponse:
    """List templates.

    Args:
        tenant_id: Optional tenant filter.
        service: Injected template service.

    Returns:
        List of templates.
    """
    templates = await service.list_templates(tenant_id=tenant_id)

    return TemplateListResponse(
        success=True,
        templates=tuple(_template_to_response(t) for t in templates),
        total=len(templates),
    )


@router.get(
    "/{template_id}",
    response_model=ApiResponse,
    summary="Get template details",
    description="Get full details of a specific template.",
)
async def get_template(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """Get a template by ID.

    Args:
        template_id: Template identifier.
        service: Injected template service.

    Returns:
        Template details.

    Raises:
        HTTPException: If template not found.
    """
    template = await service.get_template(template_id)

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    return ApiResponse(
        success=True,
        data=_template_to_detail_response(template).model_dump(),
    )


@router.put(
    "/{template_id}",
    response_model=ApiResponse,
    summary="Update a template",
    description="Update an existing template.",
)
async def update_template(
    template_id: str,
    request: UpdateTemplateRequest,
    service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """Update a template.

    Args:
        template_id: Template identifier.
        request: Update request.
        service: Injected template service.

    Returns:
        Updated template details.

    Raises:
        HTTPException: If template not found.
    """
    # Decode page image if provided
    page_image: bytes | None = None
    if request.page_image_base64:
        try:
            page_image = base64.b64decode(request.page_image_base64)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image data: {str(e)}",
            )

    update_request = TemplateUpdate(
        name=request.name,
        form_type=request.form_type,
        bboxes=request.bboxes,
        rules=request.rules,
        preview_url=request.preview_url,
    )

    template = await service.update_template(
        template_id=template_id,
        request=update_request,
        page_image=page_image,
    )

    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    logger.info("Template updated via API", template_id=template_id)

    return ApiResponse(
        success=True,
        data=_template_to_detail_response(template).model_dump(),
    )


@router.delete(
    "/{template_id}",
    response_model=ApiResponse,
    summary="Delete a template",
    description="Delete a template and its associated embedding.",
)
async def delete_template(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """Delete a template.

    Args:
        template_id: Template identifier.
        service: Injected template service.

    Returns:
        Success confirmation.

    Raises:
        HTTPException: If template not found.
    """
    deleted = await service.delete_template(template_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    logger.info("Template deleted via API", template_id=template_id)

    return ApiResponse(
        success=True,
        data={"deleted": template_id},
    )


@router.post(
    "/match",
    response_model=TemplateMatchResponse,
    summary="Find matching templates",
    description="Find templates that match an uploaded page using visual similarity.",
)
async def match_templates(
    request: MatchTemplateRequest,
    service: TemplateService = Depends(get_template_service),
) -> TemplateMatchResponse:
    """Find templates matching an uploaded page.

    Args:
        request: Match request with page image.
        service: Injected template service.

    Returns:
        List of matching templates sorted by similarity.

    Raises:
        HTTPException: If no image data provided.
    """
    # Decode page image
    page_image: bytes | None = None
    if request.page_image_base64:
        try:
            page_image = base64.b64decode(request.page_image_base64)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid base64 image data: {str(e)}",
            )

    if page_image is None and request.page_image_ref is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either page_image_base64 or page_image_ref must be provided",
        )

    # TODO: Handle page_image_ref by loading from file storage
    if page_image is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="page_image_ref support not yet implemented",
        )

    try:
        matches = await service.match_page_image(
            page_image=page_image,
            page_text=request.page_text,
            tenant_id=request.tenant_id,
            limit=request.limit,
            threshold=request.threshold,
        )

        logger.info(
            "Template matching completed",
            matches_found=len(matches),
            threshold=request.threshold,
        )

        return TemplateMatchResponse(
            success=True,
            matches=tuple(matches),
        )

    except Exception as e:
        logger.error("Template matching failed", error=str(e))
        return TemplateMatchResponse(
            success=False,
            matches=(),
            error=str(e),
        )


@router.get(
    "/{template_id}/rules",
    response_model=ApiResponse,
    summary="Get template rules",
    description="Get validation and fill rules for a template.",
)
async def get_template_rules(
    template_id: str,
    service: TemplateService = Depends(get_template_service),
) -> ApiResponse:
    """Get rules for a template.

    Args:
        template_id: Template identifier.
        service: Injected template service.

    Returns:
        List of template rules.

    Raises:
        HTTPException: If template not found.
    """
    # Check if template exists
    template = await service.get_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    rules = service.get_rules(template_id)

    return ApiResponse(
        success=True,
        data=[rule.model_dump() for rule in rules],
    )


def clear_template_singletons() -> None:
    """Clear singleton instances (for testing).

    Resets the template service and its dependencies.
    """
    global _template_repo, _vector_db, _embedding, _template_service
    _template_repo = None
    _vector_db = None
    _embedding = None
    _template_service = None
