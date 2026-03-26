"""Tests for the Phase 2 Template System.

Tests cover:
- Template models (Pydantic validation, immutability)
- Template repository (CRUD operations)
- VectorDB gateway (similarity search)
- Embedding gateway (mock embeddings)
- Template service (business logic)
- Template routes (API endpoints)
"""

import base64
from datetime import datetime, timezone

import pytest
from app.infrastructure.adapters.memory_embedding import (
    MemoryEmbedding,
    _hash_to_vector,
)
from app.infrastructure.adapters.memory_vector_db import (
    MemoryVectorDB,
    _cosine_similarity,
)
from app.infrastructure.repositories.memory_template_repository import (
    MemoryTemplateRepository,
)
from app.models.template import (
    FieldType,
    RuleType,
    Template,
    TemplateBbox,
    TemplateCreate,
    TemplateMatch,
    TemplateRule,
    TemplateUpdate,
)
from app.services.template.service import TemplateService

# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def sample_bbox() -> TemplateBbox:
    """Create a sample bounding box."""
    return TemplateBbox(
        id="field-1",
        page=1,
        x=10.0,
        y=20.0,
        width=100.0,
        height=20.0,
        label="Name",
        field_type=FieldType.TEXT,
    )


@pytest.fixture
def sample_rule() -> TemplateRule:
    """Create a sample rule."""
    return TemplateRule(
        field_id="field-1",
        rule_type=RuleType.REQUIRED,
        rule_config={"message": "Name is required"},
    )


@pytest.fixture
def sample_template(sample_bbox: TemplateBbox, sample_rule: TemplateRule) -> Template:
    """Create a sample template."""
    now = datetime.now(timezone.utc)
    return Template(
        id="tmpl-test-1",
        name="W-9 Form",
        form_type="W-9",
        bboxes=(sample_bbox,),
        rules=(sample_rule,),
        embedding_id=None,
        preview_url="https://example.com/w9-preview.png",
        field_count=1,
        created_at=now,
        updated_at=now,
        tenant_id=None,
    )


@pytest.fixture
def template_repo() -> MemoryTemplateRepository:
    """Create a fresh template repository."""
    return MemoryTemplateRepository()


@pytest.fixture
def vector_db() -> MemoryVectorDB:
    """Create a fresh vector database."""
    return MemoryVectorDB()


@pytest.fixture
def embedding_gateway() -> MemoryEmbedding:
    """Create a fresh embedding gateway."""
    return MemoryEmbedding()


@pytest.fixture
def template_service(
    template_repo: MemoryTemplateRepository,
    vector_db: MemoryVectorDB,
    embedding_gateway: MemoryEmbedding,
) -> TemplateService:
    """Create a template service with test dependencies."""
    return TemplateService(
        template_repo=template_repo,
        vector_db=vector_db,
        embedding_gateway=embedding_gateway,
    )


# --------------------------------------------------------------------------
# Model Tests
# --------------------------------------------------------------------------


class TestTemplateModels:
    """Tests for template Pydantic models."""

    def test_template_bbox_creation(self, sample_bbox: TemplateBbox) -> None:
        """Test creating a valid TemplateBbox."""
        assert sample_bbox.id == "field-1"
        assert sample_bbox.page == 1
        assert sample_bbox.x == 10.0
        assert sample_bbox.y == 20.0
        assert sample_bbox.width == 100.0
        assert sample_bbox.height == 20.0
        assert sample_bbox.label == "Name"
        assert sample_bbox.field_type == FieldType.TEXT

    def test_template_bbox_immutability(self, sample_bbox: TemplateBbox) -> None:
        """Test that TemplateBbox is immutable."""
        with pytest.raises(Exception):  # ValidationError or TypeError
            sample_bbox.label = "Changed"  # type: ignore

    def test_template_rule_creation(self, sample_rule: TemplateRule) -> None:
        """Test creating a valid TemplateRule."""
        assert sample_rule.field_id == "field-1"
        assert sample_rule.rule_type == RuleType.REQUIRED
        assert sample_rule.rule_config == {"message": "Name is required"}

    def test_template_creation(self, sample_template: Template) -> None:
        """Test creating a valid Template."""
        assert sample_template.id == "tmpl-test-1"
        assert sample_template.name == "W-9 Form"
        assert sample_template.form_type == "W-9"
        assert len(sample_template.bboxes) == 1
        assert len(sample_template.rules) == 1
        assert sample_template.field_count == 1

    def test_template_immutability(self, sample_template: Template) -> None:
        """Test that Template is immutable."""
        with pytest.raises(Exception):
            sample_template.name = "Changed"  # type: ignore

    def test_template_create_request(self, sample_bbox: TemplateBbox) -> None:
        """Test TemplateCreate request model."""
        request = TemplateCreate(
            name="Test Template",
            form_type="TEST",
            bboxes=[sample_bbox],
            rules=[],
            preview_url=None,
            tenant_id="tenant-1",
        )
        assert request.name == "Test Template"
        assert request.form_type == "TEST"
        assert len(request.bboxes) == 1

    def test_template_match_model(self) -> None:
        """Test TemplateMatch model."""
        match = TemplateMatch(
            template_id="tmpl-1",
            template_name="W-9",
            form_type="W-9",
            similarity_score=0.95,
            preview_url=None,
            field_count=10,
        )
        assert match.template_id == "tmpl-1"
        assert match.similarity_score == 0.95


# --------------------------------------------------------------------------
# Repository Tests
# --------------------------------------------------------------------------


class TestMemoryTemplateRepository:
    """Tests for in-memory template repository."""

    def test_create_template(
        self,
        template_repo: MemoryTemplateRepository,
        sample_template: Template,
    ) -> None:
        """Test creating a template."""
        created = template_repo.create(sample_template)
        assert created.id == sample_template.id
        assert created.name == sample_template.name

    def test_get_template(
        self,
        template_repo: MemoryTemplateRepository,
        sample_template: Template,
    ) -> None:
        """Test retrieving a template by ID."""
        template_repo.create(sample_template)
        retrieved = template_repo.get(sample_template.id)
        assert retrieved is not None
        assert retrieved.id == sample_template.id

    def test_get_nonexistent_template(
        self,
        template_repo: MemoryTemplateRepository,
    ) -> None:
        """Test retrieving a nonexistent template."""
        result = template_repo.get("nonexistent")
        assert result is None

    def test_list_by_tenant(
        self,
        template_repo: MemoryTemplateRepository,
        sample_bbox: TemplateBbox,
    ) -> None:
        """Test listing templates by tenant."""
        now = datetime.now(timezone.utc)

        # Create templates with different tenants
        t1 = Template(
            id="t1",
            name="A",
            form_type="T1",
            bboxes=(),
            rules=(),
            embedding_id=None,
            preview_url=None,
            field_count=0,
            created_at=now,
            updated_at=now,
            tenant_id=None,
        )
        t2 = Template(
            id="t2",
            name="B",
            form_type="T2",
            bboxes=(),
            rules=(),
            embedding_id=None,
            preview_url=None,
            field_count=0,
            created_at=now,
            updated_at=now,
            tenant_id="tenant-1",
        )
        t3 = Template(
            id="t3",
            name="C",
            form_type="T3",
            bboxes=(),
            rules=(),
            embedding_id=None,
            preview_url=None,
            field_count=0,
            created_at=now,
            updated_at=now,
            tenant_id=None,
        )

        template_repo.create(t1)
        template_repo.create(t2)
        template_repo.create(t3)

        # List templates with no tenant
        global_templates = template_repo.list_by_tenant(None)
        assert len(global_templates) == 2
        assert all(t.tenant_id is None for t in global_templates)

        # List templates for specific tenant
        tenant_templates = template_repo.list_by_tenant("tenant-1")
        assert len(tenant_templates) == 1
        assert tenant_templates[0].id == "t2"

    def test_update_template(
        self,
        template_repo: MemoryTemplateRepository,
        sample_template: Template,
    ) -> None:
        """Test updating a template."""
        template_repo.create(sample_template)

        # Update the template
        updated = Template(
            id=sample_template.id,
            name="Updated Name",
            form_type=sample_template.form_type,
            bboxes=sample_template.bboxes,
            rules=sample_template.rules,
            embedding_id=sample_template.embedding_id,
            preview_url=sample_template.preview_url,
            field_count=sample_template.field_count,
            created_at=sample_template.created_at,
            updated_at=sample_template.updated_at,
            tenant_id=sample_template.tenant_id,
        )
        result = template_repo.update(updated)
        assert result.name == "Updated Name"
        # Check updated_at is newer
        assert result.updated_at >= sample_template.updated_at

    def test_update_nonexistent_template(
        self,
        template_repo: MemoryTemplateRepository,
        sample_template: Template,
    ) -> None:
        """Test updating a nonexistent template raises error."""
        with pytest.raises(ValueError):
            template_repo.update(sample_template)

    def test_delete_template(
        self,
        template_repo: MemoryTemplateRepository,
        sample_template: Template,
    ) -> None:
        """Test deleting a template."""
        template_repo.create(sample_template)
        assert template_repo.delete(sample_template.id) is True
        assert template_repo.get(sample_template.id) is None

    def test_delete_nonexistent_template(
        self,
        template_repo: MemoryTemplateRepository,
    ) -> None:
        """Test deleting a nonexistent template."""
        assert template_repo.delete("nonexistent") is False

    def test_find_by_form_type(
        self,
        template_repo: MemoryTemplateRepository,
    ) -> None:
        """Test finding templates by form type."""
        now = datetime.now(timezone.utc)

        t1 = Template(
            id="t1",
            name="W-9 2023",
            form_type="W-9",
            bboxes=(),
            rules=(),
            embedding_id=None,
            preview_url=None,
            field_count=0,
            created_at=now,
            updated_at=now,
            tenant_id=None,
        )
        t2 = Template(
            id="t2",
            name="W-9 2024",
            form_type="w-9",
            bboxes=(),
            rules=(),
            embedding_id=None,
            preview_url=None,
            field_count=0,
            created_at=now,
            updated_at=now,
            tenant_id=None,
        )
        t3 = Template(
            id="t3",
            name="I-9",
            form_type="I-9",
            bboxes=(),
            rules=(),
            embedding_id=None,
            preview_url=None,
            field_count=0,
            created_at=now,
            updated_at=now,
            tenant_id=None,
        )

        template_repo.create(t1)
        template_repo.create(t2)
        template_repo.create(t3)

        # Case-insensitive search
        w9_templates = template_repo.find_by_form_type("W-9", None)
        assert len(w9_templates) == 2

        i9_templates = template_repo.find_by_form_type("I-9", None)
        assert len(i9_templates) == 1

    def test_exists(
        self,
        template_repo: MemoryTemplateRepository,
        sample_template: Template,
    ) -> None:
        """Test checking if template exists."""
        assert template_repo.exists(sample_template.id) is False
        template_repo.create(sample_template)
        assert template_repo.exists(sample_template.id) is True


# --------------------------------------------------------------------------
# VectorDB Tests
# --------------------------------------------------------------------------


class TestMemoryVectorDB:
    """Tests for in-memory vector database."""

    def test_cosine_similarity_same_vector(self) -> None:
        """Test cosine similarity of identical vectors is 1."""
        vec = [0.1, 0.2, 0.3, 0.4]
        assert abs(_cosine_similarity(vec, vec) - 1.0) < 0.0001

    def test_cosine_similarity_orthogonal(self) -> None:
        """Test cosine similarity of orthogonal vectors is 0."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        assert abs(_cosine_similarity(vec_a, vec_b)) < 0.0001

    def test_cosine_similarity_opposite(self) -> None:
        """Test cosine similarity of opposite vectors is -1 (clamped to 0)."""
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        # Our implementation clamps to [0, 1]
        assert _cosine_similarity(vec_a, vec_b) == 0.0

    @pytest.mark.asyncio
    async def test_store_and_search_embedding(
        self,
        vector_db: MemoryVectorDB,
    ) -> None:
        """Test storing and searching embeddings."""
        from app.application.ports.vector_db_gateway import EmbeddingVector

        # Store an embedding
        embedding = EmbeddingVector(
            id="emb-1",
            vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            metadata={"name": "test"},
            tenant_id=None,
        )
        await vector_db.store_embedding("test_collection", embedding)

        # Search for similar
        results = await vector_db.search_similar(
            collection="test_collection",
            query_vector=[0.1, 0.2, 0.3, 0.4, 0.5],
            limit=5,
            threshold=0.5,
        )

        assert len(results) == 1
        assert results[0].id == "emb-1"
        assert results[0].score > 0.99  # Should be very similar

    @pytest.mark.asyncio
    async def test_store_template_embedding(
        self,
        vector_db: MemoryVectorDB,
    ) -> None:
        """Test storing template embeddings."""
        embedding_id = await vector_db.store_template_embedding(
            template_id="tmpl-1",
            template_name="W-9",
            page_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            page_number=1,
            tenant_id=None,
            metadata={"form_type": "W-9", "field_count": 10},
        )

        assert embedding_id.startswith("emb-")

    @pytest.mark.asyncio
    async def test_find_matching_templates(
        self,
        vector_db: MemoryVectorDB,
    ) -> None:
        """Test finding matching templates."""
        # Store a template embedding
        await vector_db.store_template_embedding(
            template_id="tmpl-1",
            template_name="W-9 Form",
            page_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            page_number=1,
            tenant_id=None,
            metadata={"form_type": "W-9", "field_count": 10},
        )

        # Find matching templates
        matches = await vector_db.find_matching_templates(
            page_embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            limit=3,
            threshold=0.5,
        )

        assert len(matches) == 1
        assert matches[0].template_id == "tmpl-1"
        assert matches[0].template_name == "W-9 Form"
        assert matches[0].similarity_score > 0.99

    @pytest.mark.asyncio
    async def test_delete_embedding(
        self,
        vector_db: MemoryVectorDB,
    ) -> None:
        """Test deleting embeddings."""
        from app.application.ports.vector_db_gateway import EmbeddingVector

        embedding = EmbeddingVector(
            id="emb-delete",
            vector=[0.1, 0.2, 0.3],
            metadata={},
            tenant_id=None,
        )
        await vector_db.store_embedding("test", embedding)

        # Delete
        await vector_db.delete_embedding("test", "emb-delete")

        # Search should find nothing
        results = await vector_db.search_similar(
            collection="test",
            query_vector=[0.1, 0.2, 0.3],
            limit=5,
            threshold=0.5,
        )
        assert len(results) == 0


# --------------------------------------------------------------------------
# Embedding Gateway Tests
# --------------------------------------------------------------------------


class TestMemoryEmbedding:
    """Tests for mock embedding gateway."""

    def test_hash_to_vector_deterministic(self) -> None:
        """Test that hash_to_vector is deterministic."""
        data = b"test data"
        vec1 = _hash_to_vector(data, 10)
        vec2 = _hash_to_vector(data, 10)
        assert vec1 == vec2

    def test_hash_to_vector_normalized(self) -> None:
        """Test that hash_to_vector produces normalized vectors."""
        import math

        data = b"test data"
        vec = _hash_to_vector(data, 100)
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 0.0001

    @pytest.mark.asyncio
    async def test_embed_image(
        self,
        embedding_gateway: MemoryEmbedding,
    ) -> None:
        """Test embedding an image."""
        image_bytes = b"fake image data"
        result = await embedding_gateway.embed_image(image_bytes)

        assert len(result.vector) == 1536  # Default dimensions
        assert result.model == "mock-embedding-v1"
        assert result.dimensions == 1536

    @pytest.mark.asyncio
    async def test_embed_text(
        self,
        embedding_gateway: MemoryEmbedding,
    ) -> None:
        """Test embedding text."""
        text = "Hello, world!"
        result = await embedding_gateway.embed_text(text)

        assert len(result.vector) == 1536
        assert result.usage_tokens > 0

    @pytest.mark.asyncio
    async def test_embed_document_page(
        self,
        embedding_gateway: MemoryEmbedding,
    ) -> None:
        """Test embedding a document page with text."""
        image_bytes = b"fake image"
        text = "Page text content"
        result = await embedding_gateway.embed_document_page(
            page_image=image_bytes,
            page_text=text,
        )

        assert len(result.vector) == 1536

    def test_get_dimensions(
        self,
        embedding_gateway: MemoryEmbedding,
    ) -> None:
        """Test getting dimensions."""
        assert embedding_gateway.get_dimensions() == 1536


# --------------------------------------------------------------------------
# Service Tests
# --------------------------------------------------------------------------


class TestTemplateService:
    """Tests for template service."""

    @pytest.mark.asyncio
    async def test_create_template(
        self,
        template_service: TemplateService,
        sample_bbox: TemplateBbox,
    ) -> None:
        """Test creating a template via service."""
        request = TemplateCreate(
            name="W-9 Form",
            form_type="W-9",
            bboxes=[sample_bbox],
            rules=[],
            preview_url="https://example.com/preview.png",
            tenant_id=None,
        )

        template = await template_service.create_template(request)

        assert template.id.startswith("tmpl-")
        assert template.name == "W-9 Form"
        assert template.form_type == "W-9"
        assert template.field_count == 1

    @pytest.mark.asyncio
    async def test_create_template_with_embedding(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test creating a template with embedding."""
        request = TemplateCreate(
            name="W-9 Form",
            form_type="W-9",
            bboxes=[],
            rules=[],
            preview_url=None,
            tenant_id=None,
        )
        page_image = b"fake page image"

        template = await template_service.create_template(
            request=request,
            page_image=page_image,
        )

        assert template.embedding_id is not None
        assert template.embedding_id.startswith("emb-")

    @pytest.mark.asyncio
    async def test_get_template(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test getting a template."""
        # Create first
        request = TemplateCreate(
            name="Test",
            form_type="TEST",
            bboxes=[],
            rules=[],
        )
        created = await template_service.create_template(request)

        # Get
        retrieved = await template_service.get_template(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "Test"

    @pytest.mark.asyncio
    async def test_list_templates(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test listing templates."""
        # Create templates
        for i in range(3):
            request = TemplateCreate(
                name=f"Template {i}",
                form_type="TEST",
                bboxes=[],
                rules=[],
            )
            await template_service.create_template(request)

        templates = await template_service.list_templates()
        assert len(templates) == 3

    @pytest.mark.asyncio
    async def test_update_template(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test updating a template."""
        # Create
        request = TemplateCreate(
            name="Original",
            form_type="TEST",
            bboxes=[],
            rules=[],
        )
        created = await template_service.create_template(request)

        # Update
        update_request = TemplateUpdate(
            name="Updated",
            form_type="UPDATED",
        )
        updated = await template_service.update_template(
            template_id=created.id,
            request=update_request,
        )

        assert updated is not None
        assert updated.name == "Updated"
        assert updated.form_type == "UPDATED"

    @pytest.mark.asyncio
    async def test_delete_template(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test deleting a template."""
        # Create
        request = TemplateCreate(
            name="To Delete",
            form_type="TEST",
            bboxes=[],
            rules=[],
        )
        created = await template_service.create_template(request)

        # Delete
        deleted = await template_service.delete_template(created.id)
        assert deleted is True

        # Verify deleted
        retrieved = await template_service.get_template(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_search_by_embedding(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test searching templates by embedding."""
        # Create template with embedding
        request = TemplateCreate(
            name="W-9 Form",
            form_type="W-9",
            bboxes=[],
            rules=[],
        )
        page_image = b"test image content"
        await template_service.create_template(request, page_image)

        # Generate embedding for same image and search
        embedding = await template_service._embedding.embed_document_page(page_image)
        matches = await template_service.search_by_embedding(
            page_embedding=embedding.vector,
            threshold=0.5,
        )

        assert len(matches) == 1
        assert matches[0].form_type == "W-9"

    @pytest.mark.asyncio
    async def test_match_page_image(
        self,
        template_service: TemplateService,
    ) -> None:
        """Test matching a page image to templates."""
        # Create template with embedding
        request = TemplateCreate(
            name="W-9 Form",
            form_type="W-9",
            bboxes=[],
            rules=[],
        )
        page_image = b"test image content"
        await template_service.create_template(request, page_image)

        # Match same image
        matches = await template_service.match_page_image(
            page_image=page_image,
            threshold=0.5,
        )

        assert len(matches) == 1
        assert matches[0].form_type == "W-9"
        assert matches[0].similarity_score > 0.9

    @pytest.mark.asyncio
    async def test_get_rules(
        self,
        template_service: TemplateService,
        sample_rule: TemplateRule,
    ) -> None:
        """Test getting rules for a template."""
        request = TemplateCreate(
            name="Test",
            form_type="TEST",
            bboxes=[],
            rules=[sample_rule],
        )
        created = await template_service.create_template(request)

        rules = template_service.get_rules(created.id)
        assert len(rules) == 1
        assert rules[0].field_id == "field-1"
        assert rules[0].rule_type == RuleType.REQUIRED


# --------------------------------------------------------------------------
# API Route Tests
# --------------------------------------------------------------------------


class TestTemplateRoutes:
    """Tests for template API routes."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from app.main import app
        from app.routes.templates import clear_template_singletons
        from fastapi.testclient import TestClient

        # Clear singletons before each test
        clear_template_singletons()

        return TestClient(app)

    def test_create_template(self, client) -> None:
        """Test POST /api/v2/templates."""
        response = client.post(
            "/api/v2/templates",
            json={
                "name": "W-9 Form",
                "form_type": "W-9",
                "bboxes": [],
                "rules": [],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "W-9 Form"
        assert data["data"]["form_type"] == "W-9"

    def test_list_templates(self, client) -> None:
        """Test GET /api/v2/templates."""
        # Create a template first
        client.post(
            "/api/v2/templates",
            json={"name": "Test", "form_type": "TEST"},
        )

        response = client.get("/api/v2/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] >= 1

    def test_get_template(self, client) -> None:
        """Test GET /api/v2/templates/{id}."""
        # Create a template first
        create_response = client.post(
            "/api/v2/templates",
            json={"name": "Test", "form_type": "TEST"},
        )
        template_id = create_response.json()["data"]["id"]

        response = client.get(f"/api/v2/templates/{template_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == template_id

    def test_get_template_not_found(self, client) -> None:
        """Test GET /api/v2/templates/{id} for nonexistent template."""
        response = client.get("/api/v2/templates/nonexistent")
        assert response.status_code == 404

    def test_update_template(self, client) -> None:
        """Test PUT /api/v2/templates/{id}."""
        # Create a template first
        create_response = client.post(
            "/api/v2/templates",
            json={"name": "Original", "form_type": "TEST"},
        )
        template_id = create_response.json()["data"]["id"]

        response = client.put(
            f"/api/v2/templates/{template_id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated"

    def test_delete_template(self, client) -> None:
        """Test DELETE /api/v2/templates/{id}."""
        # Create a template first
        create_response = client.post(
            "/api/v2/templates",
            json={"name": "To Delete", "form_type": "TEST"},
        )
        template_id = create_response.json()["data"]["id"]

        response = client.delete(f"/api/v2/templates/{template_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify deleted
        get_response = client.get(f"/api/v2/templates/{template_id}")
        assert get_response.status_code == 404

    def test_match_templates(self, client) -> None:
        """Test POST /api/v2/templates/match."""
        # Create a template with embedding
        page_image = b"test image"
        page_image_b64 = base64.b64encode(page_image).decode()

        client.post(
            "/api/v2/templates",
            json={
                "name": "W-9 Form",
                "form_type": "W-9",
                "page_image_base64": page_image_b64,
            },
        )

        # Match the same image
        response = client.post(
            "/api/v2/templates/match",
            json={
                "page_image_base64": page_image_b64,
                "threshold": 0.5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["matches"]) >= 1

    def test_match_templates_missing_image(self, client) -> None:
        """Test POST /api/v2/templates/match without image."""
        response = client.post(
            "/api/v2/templates/match",
            json={"threshold": 0.5},
        )
        assert response.status_code == 400

    def test_get_template_rules(self, client) -> None:
        """Test GET /api/v2/templates/{id}/rules."""
        # Create a template with rules
        rule = {
            "field_id": "field-1",
            "rule_type": "required",
            "rule_config": {"message": "Required"},
        }
        create_response = client.post(
            "/api/v2/templates",
            json={
                "name": "Test",
                "form_type": "TEST",
                "rules": [rule],
            },
        )
        template_id = create_response.json()["data"]["id"]

        response = client.get(f"/api/v2/templates/{template_id}/rules")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 1
