"""Template service for Phase 2 Template System.

Provides business logic for template management including:
- CRUD operations on templates
- Embedding generation and storage
- Template matching via vector similarity search
"""

from datetime import datetime, timezone
from uuid import uuid4

from app.models.template import (
    Template,
    TemplateBbox,
    TemplateCreate,
    TemplateMatch,
    TemplateRule,
)
from app.repositories.embedding_gateway import EmbeddingGateway
from app.repositories.template_repository import TemplateRepository
from app.repositories.vector_db_gateway import VectorDBGateway


class TemplateService:
    """Service for template management operations.

    Handles the business logic for template CRUD, embedding generation,
    and template matching via vector similarity search.

    Example:
        service = TemplateService(
            template_repository=MemoryTemplateRepository(),
            vector_db=InMemoryVectorDB(),
            embedding_gateway=MockEmbeddingGateway(),
        )

        # Create a template
        template = await service.save_template(
            tenant_id="tenant-123",
            template_data=TemplateCreate(name="W-9", form_type="tax"),
            page_images=[b"page1_image"],
        )

        # Search for matching templates
        matches = await service.search_by_embedding(
            page_image=b"document_page",
            tenant_id="tenant-123",
        )
    """

    def __init__(
        self,
        template_repository: TemplateRepository,
        vector_db: VectorDBGateway,
        embedding_gateway: EmbeddingGateway,
    ) -> None:
        """Initialize the template service.

        Args:
            template_repository: Repository for template persistence.
            vector_db: Vector database for embedding storage/search.
            embedding_gateway: Gateway for generating embeddings.
        """
        self._template_repository = template_repository
        self._vector_db = vector_db
        self._embedding_gateway = embedding_gateway

    def get_template(self, template_id: str) -> Template | None:
        """Get a template by ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            Template if found, None otherwise.
        """
        return self._template_repository.get(template_id)

    def list_templates(
        self,
        tenant_id: str,
        form_type: str | None = None,
    ) -> list[Template]:
        """List templates for a tenant.

        Args:
            tenant_id: Tenant identifier.
            form_type: Optional form type to filter by.

        Returns:
            List of matching templates.
        """
        if form_type:
            return self._template_repository.find_by_form_type(form_type, tenant_id)
        return self._template_repository.list_by_tenant(tenant_id)

    async def save_template(
        self,
        tenant_id: str,
        template_data: TemplateCreate,
        page_images: list[bytes] | None = None,
    ) -> Template:
        """Create a new template with embedding.

        Args:
            tenant_id: Tenant identifier.
            template_data: Template creation data.
            page_images: Optional page images for embedding generation.

        Returns:
            Created template.
        """
        template_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Generate embedding from first page image or text description
        embedding_id = None
        if page_images and len(page_images) > 0:
            embedding = await self._embedding_gateway.embed_image(page_images[0])
            embedding_id = f"emb-{template_id}"
            await self._vector_db.store(
                id=embedding_id,
                embedding=embedding,
                metadata={"tenant_id": tenant_id, "template_id": template_id},
            )
        elif template_data.name:
            # Fall back to text embedding from name/description
            text = template_data.name
            if hasattr(template_data, "description") and template_data.description:
                text += f" {template_data.description}"
            embedding = await self._embedding_gateway.embed_text(text)
            embedding_id = f"emb-{template_id}"
            await self._vector_db.store(
                id=embedding_id,
                embedding=embedding,
                metadata={"tenant_id": tenant_id, "template_id": template_id},
            )

        # Convert lists to tuples for immutability
        bboxes = tuple(template_data.bboxes) if template_data.bboxes else ()
        rules = tuple(template_data.rules) if template_data.rules else ()

        template = Template(
            id=template_id,
            name=template_data.name,
            form_type=template_data.form_type,
            bboxes=bboxes,
            rules=rules,
            embedding_id=embedding_id,
            field_count=len(bboxes),
            tenant_id=tenant_id,
            created_at=now,
            updated_at=now,
        )

        return self._template_repository.create(template)

    async def delete_template(self, template_id: str) -> bool:
        """Delete a template and its embedding.

        Args:
            template_id: Unique template identifier.

        Returns:
            True if deleted, False if not found.
        """
        template = self._template_repository.get(template_id)
        if template is None:
            return False

        # Delete embedding if exists
        if template.embedding_id:
            await self._vector_db.delete(template.embedding_id)

        return self._template_repository.delete(template_id)

    async def search_by_embedding(
        self,
        page_image: bytes,
        tenant_id: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[TemplateMatch]:
        """Search for templates matching a page image.

        Args:
            page_image: Page image bytes to match.
            tenant_id: Tenant identifier for filtering.
            limit: Maximum results to return.
            min_score: Minimum similarity score (0-1).

        Returns:
            List of matching templates with scores, sorted by score descending.
        """
        # Generate embedding for the search image
        query_embedding = await self._embedding_gateway.embed_image(page_image)

        # Search vector database
        results = await self._vector_db.search(
            embedding=query_embedding,
            limit=limit * 2,  # Get more to filter by tenant
            min_score=min_score,
            filter={"tenant_id": tenant_id},
        )

        # Resolve templates from embedding IDs
        matches = []
        for result in results:
            embedding_id = result["id"]
            score = result["score"]

            # Find template by embedding ID
            template = None
            for t in self._template_repository.list_by_tenant(tenant_id):
                if t.embedding_id == embedding_id:
                    template = t
                    break

            if template and template.tenant_id == tenant_id:
                matches.append(
                    TemplateMatch(
                        template_id=template.id,
                        template_name=template.name,
                        form_type=template.form_type,
                        similarity_score=score,
                        preview_url=template.preview_url,
                        field_count=template.field_count,
                    )
                )

        # Sort by score and limit
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return matches[:limit]

    def get_rules(self, template_id: str) -> list[TemplateRule] | None:
        """Get validation rules for a template.

        Args:
            template_id: Unique template identifier.

        Returns:
            List of rules if template found, None otherwise.
        """
        template = self._template_repository.get(template_id)
        if template is None:
            return None
        return list(template.rules)

    def get_bboxes(
        self,
        template_id: str,
        page: int | None = None,
    ) -> list[TemplateBbox] | None:
        """Get bounding boxes for a template.

        Args:
            template_id: Unique template identifier.
            page: Optional page number to filter by.

        Returns:
            List of bboxes if template found, None otherwise.
        """
        template = self._template_repository.get(template_id)
        if template is None:
            return None

        bboxes = list(template.bboxes)
        if page is not None:
            bboxes = [b for b in bboxes if b.page == page]

        return bboxes


# Dependency injection helper for FastAPI
def get_template_service() -> TemplateService:
    """Get the template service instance.

    Returns a configured TemplateService with default implementations.
    In production, this would use real database and embedding services.
    """
    from app.infrastructure.gateways.embedding import MockEmbeddingGateway
    from app.infrastructure.gateways.vector_db import InMemoryVectorDB
    from app.infrastructure.repositories.memory_template_repository import (
        MemoryTemplateRepository,
    )

    return TemplateService(
        template_repository=MemoryTemplateRepository(),
        vector_db=InMemoryVectorDB(),
        embedding_gateway=MockEmbeddingGateway(),
    )
