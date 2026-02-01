"""Template service for template management and matching.

This service coordinates template operations:
1. CRUD operations for templates
2. Visual embedding generation and storage
3. Similarity-based template matching

Following Clean Architecture:
- Depends on repository and gateway interfaces
- Returns immutable result objects
- Coordinates workflow without direct infrastructure access
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.application.ports.embedding_gateway import EmbeddingGateway
from app.application.ports.vector_db_gateway import VectorDBGateway
from app.infrastructure.observability import get_logger
from app.models.template import (
    Template,
    TemplateBbox,
    TemplateCreate,
    TemplateMatch,
    TemplateRule,
    TemplateUpdate,
)
from app.repositories.template_repository import TemplateRepository


logger = get_logger(__name__)


class TemplateService:
    """Application service for template management.

    Handles template CRUD operations and similarity-based matching.
    Uses visual embeddings to find templates that match uploaded documents.

    Example:
        # Create with dependencies
        service = TemplateService(
            template_repo=MemoryTemplateRepository(),
            vector_db=MemoryVectorDB(),
            embedding_gateway=MemoryEmbedding(),
        )

        # Create a template
        template = await service.create_template(
            TemplateCreate(name="W-9", form_type="W-9", bboxes=[...])
        )

        # Find matching templates for a page
        matches = await service.search_by_embedding(page_embedding)
    """

    def __init__(
        self,
        template_repo: TemplateRepository,
        vector_db: VectorDBGateway,
        embedding_gateway: EmbeddingGateway,
    ) -> None:
        """Initialize the template service.

        Args:
            template_repo: Repository for template persistence.
            vector_db: Gateway for vector similarity search.
            embedding_gateway: Gateway for embedding generation.
        """
        self._repo = template_repo
        self._vector_db = vector_db
        self._embedding = embedding_gateway

    async def create_template(
        self,
        request: TemplateCreate,
        page_image: bytes | None = None,
    ) -> Template:
        """Create a new template.

        Optionally generates and stores a visual embedding if page_image
        is provided.

        Args:
            request: Template creation request.
            page_image: Optional page image for embedding generation.

        Returns:
            Created Template entity.
        """
        now = datetime.now(timezone.utc)
        template_id = f"tmpl-{uuid4().hex[:12]}"

        # Generate embedding if image provided
        embedding_id: str | None = None
        if page_image:
            embedding_result = await self._embedding.embed_document_page(
                page_image=page_image,
            )
            embedding_id = await self._vector_db.store_template_embedding(
                template_id=template_id,
                template_name=request.name,
                page_embedding=embedding_result.vector,
                page_number=1,
                tenant_id=request.tenant_id,
                metadata={
                    "form_type": request.form_type,
                    "field_count": len(request.bboxes),
                    "preview_url": request.preview_url or "",
                },
            )
            logger.info(
                "Generated template embedding",
                template_id=template_id,
                embedding_id=embedding_id,
                dimensions=embedding_result.dimensions,
            )

        template = Template(
            id=template_id,
            name=request.name,
            form_type=request.form_type,
            bboxes=tuple(request.bboxes),
            rules=tuple(request.rules),
            embedding_id=embedding_id,
            preview_url=request.preview_url,
            field_count=len(request.bboxes),
            created_at=now,
            updated_at=now,
            tenant_id=request.tenant_id,
        )

        created = self._repo.create(template)
        logger.info(
            "Created template",
            template_id=created.id,
            name=created.name,
            form_type=created.form_type,
            field_count=created.field_count,
        )

        return created

    async def get_template(self, template_id: str) -> Template | None:
        """Get a template by ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            Template if found, None otherwise.
        """
        return self._repo.get(template_id)

    async def list_templates(
        self,
        tenant_id: str | None = None,
    ) -> list[Template]:
        """List templates for a tenant.

        Args:
            tenant_id: Optional tenant ID to filter by.

        Returns:
            List of templates.
        """
        return self._repo.list_by_tenant(tenant_id)

    async def update_template(
        self,
        template_id: str,
        request: TemplateUpdate,
        page_image: bytes | None = None,
    ) -> Template | None:
        """Update an existing template.

        Args:
            template_id: ID of template to update.
            request: Update request with new values.
            page_image: Optional new page image for embedding.

        Returns:
            Updated Template, or None if not found.
        """
        existing = self._repo.get(template_id)
        if existing is None:
            return None

        # Build updated values (immutable pattern)
        name = request.name if request.name is not None else existing.name
        form_type = request.form_type if request.form_type is not None else existing.form_type
        bboxes = tuple(request.bboxes) if request.bboxes is not None else existing.bboxes
        rules = tuple(request.rules) if request.rules is not None else existing.rules
        preview_url = request.preview_url if request.preview_url is not None else existing.preview_url
        field_count = len(bboxes)

        # Update embedding if new image provided
        embedding_id = existing.embedding_id
        if page_image:
            # Delete old embedding if exists
            if existing.embedding_id:
                await self._vector_db.delete_embedding(
                    collection="template_embeddings",
                    embedding_id=existing.embedding_id,
                )

            # Create new embedding
            embedding_result = await self._embedding.embed_document_page(
                page_image=page_image,
            )
            embedding_id = await self._vector_db.store_template_embedding(
                template_id=template_id,
                template_name=name,
                page_embedding=embedding_result.vector,
                page_number=1,
                tenant_id=existing.tenant_id,
                metadata={
                    "form_type": form_type,
                    "field_count": field_count,
                    "preview_url": preview_url or "",
                },
            )

        updated = Template(
            id=existing.id,
            name=name,
            form_type=form_type,
            bboxes=bboxes,
            rules=rules,
            embedding_id=embedding_id,
            preview_url=preview_url,
            field_count=field_count,
            created_at=existing.created_at,
            updated_at=datetime.now(timezone.utc),
            tenant_id=existing.tenant_id,
        )

        result = self._repo.update(updated)
        logger.info(
            "Updated template",
            template_id=template_id,
            name=result.name,
        )

        return result

    async def delete_template(self, template_id: str) -> bool:
        """Delete a template.

        Also removes the associated embedding from the vector database.

        Args:
            template_id: ID of template to delete.

        Returns:
            True if deleted, False if not found.
        """
        existing = self._repo.get(template_id)
        if existing is None:
            return False

        # Delete embedding if exists
        if existing.embedding_id:
            await self._vector_db.delete_embedding(
                collection="template_embeddings",
                embedding_id=existing.embedding_id,
            )

        deleted = self._repo.delete(template_id)
        if deleted:
            logger.info("Deleted template", template_id=template_id)

        return deleted

    async def search_by_embedding(
        self,
        page_embedding: list[float],
        tenant_id: str | None = None,
        limit: int = 3,
        threshold: float = 0.8,
    ) -> list[TemplateMatch]:
        """Search for templates by visual embedding similarity.

        Args:
            page_embedding: Visual embedding of the uploaded page.
            tenant_id: Optional tenant ID to filter by.
            limit: Maximum number of matches.
            threshold: Minimum similarity score.

        Returns:
            List of matching templates sorted by similarity.
        """
        matches = await self._vector_db.find_matching_templates(
            page_embedding=page_embedding,
            tenant_id=tenant_id,
            limit=limit,
            threshold=threshold,
        )

        # Enrich matches with form_type from repository
        enriched_matches = []
        for match in matches:
            template = self._repo.get(match.template_id)
            if template:
                enriched = TemplateMatch(
                    template_id=match.template_id,
                    template_name=match.template_name,
                    form_type=template.form_type,
                    similarity_score=match.similarity_score,
                    preview_url=match.preview_url or template.preview_url,
                    field_count=match.field_count or template.field_count,
                )
                enriched_matches.append(enriched)
            else:
                # Template may have been deleted but embedding still exists
                # Return basic match info
                enriched_matches.append(
                    TemplateMatch(
                        template_id=match.template_id,
                        template_name=match.template_name,
                        form_type="unknown",
                        similarity_score=match.similarity_score,
                        preview_url=match.preview_url,
                        field_count=match.field_count,
                    )
                )

        logger.debug(
            "Template search completed",
            matches_found=len(enriched_matches),
            threshold=threshold,
        )

        return enriched_matches

    async def match_page_image(
        self,
        page_image: bytes,
        page_text: str | None = None,
        tenant_id: str | None = None,
        limit: int = 3,
        threshold: float = 0.8,
    ) -> list[TemplateMatch]:
        """Find templates matching a page image.

        Generates an embedding from the page image and searches
        for similar templates.

        Args:
            page_image: Page image bytes (PNG/JPEG).
            page_text: Optional extracted text for hybrid embedding.
            tenant_id: Optional tenant ID to filter by.
            limit: Maximum number of matches.
            threshold: Minimum similarity score.

        Returns:
            List of matching templates sorted by similarity.
        """
        # Generate embedding for the page
        embedding_result = await self._embedding.embed_document_page(
            page_image=page_image,
            page_text=page_text,
        )

        # Search for similar templates
        return await self.search_by_embedding(
            page_embedding=embedding_result.vector,
            tenant_id=tenant_id,
            limit=limit,
            threshold=threshold,
        )

    async def save_template(
        self,
        template: Template,
        page_image: bytes | None = None,
    ) -> Template:
        """Save a template with optional embedding generation.

        If the template exists, updates it. Otherwise, creates a new one.

        Args:
            template: Template to save.
            page_image: Optional page image for embedding generation.

        Returns:
            Saved Template entity.
        """
        existing = self._repo.get(template.id)

        if existing:
            # Update existing template
            update_request = TemplateUpdate(
                name=template.name,
                form_type=template.form_type,
                bboxes=list(template.bboxes),
                rules=list(template.rules),
                preview_url=template.preview_url,
            )
            result = await self.update_template(
                template_id=template.id,
                request=update_request,
                page_image=page_image,
            )
            return result if result else template
        else:
            # Create new template
            create_request = TemplateCreate(
                name=template.name,
                form_type=template.form_type,
                bboxes=list(template.bboxes),
                rules=list(template.rules),
                preview_url=template.preview_url,
                tenant_id=template.tenant_id,
            )
            return await self.create_template(
                request=create_request,
                page_image=page_image,
            )

    def get_rules(self, template_id: str) -> list[TemplateRule]:
        """Get validation rules for a template.

        Args:
            template_id: Template ID.

        Returns:
            List of template rules, or empty list if template not found.
        """
        template = self._repo.get(template_id)
        if template is None:
            return []
        return list(template.rules)

    async def find_by_form_type(
        self,
        form_type: str,
        tenant_id: str | None = None,
    ) -> list[Template]:
        """Find templates by form type.

        Args:
            form_type: Form type identifier (e.g., "W-9").
            tenant_id: Optional tenant ID to filter by.

        Returns:
            List of matching templates.
        """
        return self._repo.find_by_form_type(form_type, tenant_id)
