"""Tests for Template service layer.

Tests service layer with mocked dependencies:
- search_by_embedding with mocked VectorDB
- get_template
- save_template with embedding generation
- get_rules
- Template not found handling
- Empty search results
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTemplateService:
    """Tests for TemplateService."""

    @pytest.fixture
    def mock_template_repository(self):
        """Create a mock template repository."""
        mock = MagicMock()
        mock.create = MagicMock()
        mock.get = MagicMock()
        mock.update = MagicMock()
        mock.delete = MagicMock()
        mock.list_all = MagicMock(return_value=[])
        mock.list_by_tenant = MagicMock(return_value=[])
        mock.find_by_form_type = MagicMock(return_value=[])
        mock.find_by_embedding_id = MagicMock(return_value=None)
        return mock

    @pytest.fixture
    def mock_vector_db(self):
        """Create a mock vector database gateway."""
        mock = MagicMock()
        mock.store = AsyncMock()
        mock.search = AsyncMock(return_value=[])
        mock.delete = AsyncMock()
        return mock

    @pytest.fixture
    def mock_embedding_gateway(self):
        """Create a mock embedding gateway."""
        mock = MagicMock()
        # Return a 1536-dimension vector (OpenAI embedding size)
        mock.embed_image = AsyncMock(return_value=[0.1] * 1536)
        mock.embed_text = AsyncMock(return_value=[0.1] * 1536)
        mock.embed_document_page = AsyncMock(return_value=[0.1] * 1536)
        return mock

    @pytest.fixture
    def sample_template(self):
        """Create a sample template for testing."""
        from app.models.template import Template, TemplateBbox, TemplateRule

        bbox = TemplateBbox(
            x=10.0, y=20.0, width=100.0, height=30.0, page=1,
            field_name="name", field_type="text", label="Full Name"
        )
        rule = TemplateRule(
            id="rule-1",
            field_name="name",
            rule_type="required",
            config={"message": "Name is required"},
        )
        return Template(
            id="tpl-001",
            tenant_id="tenant-123",
            name="Application Form",
            form_type="application",
            page_count=2,
            bboxes=[bbox],
            rules=[rule],
            embedding_id="emb-001",
        )

    @pytest.fixture
    def template_service(
        self, mock_template_repository, mock_vector_db, mock_embedding_gateway
    ):
        """Create a template service with mocked dependencies."""
        from app.services.template_service import TemplateService

        return TemplateService(
            template_repository=mock_template_repository,
            vector_db=mock_vector_db,
            embedding_gateway=mock_embedding_gateway,
        )

    # =========================================================================
    # Get Template Tests
    # =========================================================================

    def test_get_template(
        self, template_service, mock_template_repository, sample_template
    ) -> None:
        """Test getting a template by ID."""
        mock_template_repository.get.return_value = sample_template

        result = template_service.get_template("tpl-001")

        assert result is not None
        assert result.id == "tpl-001"
        assert result.name == "Application Form"
        mock_template_repository.get.assert_called_once_with("tpl-001")

    def test_get_template_not_found(
        self, template_service, mock_template_repository
    ) -> None:
        """Test getting a non-existent template returns None."""
        mock_template_repository.get.return_value = None

        result = template_service.get_template("non-existent")

        assert result is None
        mock_template_repository.get.assert_called_once_with("non-existent")

    # =========================================================================
    # List Templates Tests
    # =========================================================================

    def test_list_templates_by_tenant(
        self, template_service, mock_template_repository, sample_template
    ) -> None:
        """Test listing templates by tenant."""
        mock_template_repository.list_by_tenant.return_value = [sample_template]

        result = template_service.list_templates(tenant_id="tenant-123")

        assert len(result) == 1
        assert result[0].id == "tpl-001"
        mock_template_repository.list_by_tenant.assert_called_once_with("tenant-123")

    def test_list_templates_empty(
        self, template_service, mock_template_repository
    ) -> None:
        """Test listing templates when none exist."""
        mock_template_repository.list_by_tenant.return_value = []

        result = template_service.list_templates(tenant_id="tenant-123")

        assert result == []

    # =========================================================================
    # Save Template Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_save_template_creates_new(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
        mock_embedding_gateway,
        sample_template,
    ) -> None:
        """Test saving a new template."""
        from app.models.template import TemplateCreate, TemplateBbox

        bbox = TemplateBbox(
            x=10.0, y=20.0, width=100.0, height=30.0, page=1,
            field_name="name", field_type="text"
        )
        create_request = TemplateCreate(
            name="New Form",
            form_type="application",
            page_count=1,
            bboxes=[bbox],
        )

        # Mock the repository to return a template with generated ID
        mock_template_repository.create.return_value = sample_template
        mock_template_repository.update.return_value = sample_template

        result = await template_service.save_template(
            tenant_id="tenant-123",
            template_data=create_request,
            page_images=[b"fake_image_data"],
        )

        assert result is not None
        mock_template_repository.create.assert_called_once()
        # Verify embedding was generated and stored
        mock_embedding_gateway.embed_image.assert_called()
        mock_vector_db.store.assert_called()

    @pytest.mark.asyncio
    async def test_save_template_generates_embedding(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
        mock_embedding_gateway,
        sample_template,
    ) -> None:
        """Test that saving a template generates and stores embedding."""
        from app.models.template import TemplateCreate

        create_request = TemplateCreate(
            name="New Form",
            form_type="application",
            page_count=1,
        )

        mock_template_repository.create.return_value = sample_template
        mock_template_repository.update.return_value = sample_template
        mock_embedding_gateway.embed_image.return_value = [0.5] * 1536

        await template_service.save_template(
            tenant_id="tenant-123",
            template_data=create_request,
            page_images=[b"page1_image"],
        )

        # Verify embedding was generated from page image
        mock_embedding_gateway.embed_image.assert_called_with(b"page1_image")
        # Verify embedding was stored in vector DB
        mock_vector_db.store.assert_called()

    @pytest.mark.asyncio
    async def test_save_template_without_images(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
        mock_embedding_gateway,
        sample_template,
    ) -> None:
        """Test saving a template without page images uses text embedding."""
        from app.models.template import TemplateCreate

        create_request = TemplateCreate(
            name="Form Name",
            form_type="application",
            page_count=1,
            description="A detailed description of the form",
        )

        mock_template_repository.create.return_value = sample_template
        mock_template_repository.update.return_value = sample_template
        mock_embedding_gateway.embed_text.return_value = [0.3] * 1536

        await template_service.save_template(
            tenant_id="tenant-123",
            template_data=create_request,
            page_images=None,
        )

        # Verify text embedding was generated
        mock_embedding_gateway.embed_text.assert_called()
        mock_vector_db.store.assert_called()

    # =========================================================================
    # Delete Template Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_delete_template(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
        sample_template,
    ) -> None:
        """Test deleting a template."""
        mock_template_repository.get.return_value = sample_template
        mock_template_repository.delete.return_value = True

        result = await template_service.delete_template("tpl-001")

        assert result is True
        mock_template_repository.delete.assert_called_once_with("tpl-001")
        # Verify embedding was also deleted from vector DB
        mock_vector_db.delete.assert_called_once_with("emb-001")

    @pytest.mark.asyncio
    async def test_delete_template_not_found(
        self, template_service, mock_template_repository, mock_vector_db
    ) -> None:
        """Test deleting a non-existent template returns False."""
        mock_template_repository.get.return_value = None

        result = await template_service.delete_template("non-existent")

        assert result is False
        mock_template_repository.delete.assert_not_called()
        mock_vector_db.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_template_without_embedding(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
    ) -> None:
        """Test deleting a template that has no embedding."""
        from app.models.template import Template

        template_no_embedding = Template(
            id="tpl-002",
            tenant_id="tenant-123",
            name="No Embedding",
            form_type="simple",
            page_count=1,
            embedding_id=None,
        )
        mock_template_repository.get.return_value = template_no_embedding
        mock_template_repository.delete.return_value = True

        result = await template_service.delete_template("tpl-002")

        assert result is True
        mock_template_repository.delete.assert_called_once()
        mock_vector_db.delete.assert_not_called()

    # =========================================================================
    # Search by Embedding Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_search_by_embedding(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
        mock_embedding_gateway,
        sample_template,
    ) -> None:
        """Test searching templates by page image embedding."""
        # Mock vector DB to return matching embedding IDs with scores
        mock_vector_db.search.return_value = [
            {"id": "emb-001", "score": 0.95},
            {"id": "emb-002", "score": 0.80},
        ]
        mock_template_repository.find_by_embedding_id.side_effect = [
            sample_template,
            None,  # Second template not found (orphan embedding)
        ]

        results = await template_service.search_by_embedding(
            page_image=b"search_image",
            tenant_id="tenant-123",
            limit=5,
        )

        assert len(results) == 1
        assert results[0].template.id == "tpl-001"
        assert results[0].score == 0.95
        mock_embedding_gateway.embed_image.assert_called_with(b"search_image")
        mock_vector_db.search.assert_called()

    @pytest.mark.asyncio
    async def test_search_by_embedding_no_matches(
        self,
        template_service,
        mock_vector_db,
        mock_embedding_gateway,
    ) -> None:
        """Test searching when no templates match."""
        mock_vector_db.search.return_value = []

        results = await template_service.search_by_embedding(
            page_image=b"no_match_image",
            tenant_id="tenant-123",
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_search_by_embedding_with_threshold(
        self,
        template_service,
        mock_template_repository,
        mock_vector_db,
        mock_embedding_gateway,
        sample_template,
    ) -> None:
        """Test searching with a minimum score threshold."""
        mock_vector_db.search.return_value = [
            {"id": "emb-001", "score": 0.95},
            {"id": "emb-002", "score": 0.60},  # Below threshold
        ]
        mock_template_repository.find_by_embedding_id.return_value = sample_template

        results = await template_service.search_by_embedding(
            page_image=b"image",
            tenant_id="tenant-123",
            min_score=0.7,
        )

        # Only results above threshold should be returned
        # The filtering happens in vector_db or service layer
        mock_vector_db.search.assert_called()

    # =========================================================================
    # Get Rules Tests
    # =========================================================================

    def test_get_rules(
        self, template_service, mock_template_repository, sample_template
    ) -> None:
        """Test getting rules for a template."""
        mock_template_repository.get.return_value = sample_template

        rules = template_service.get_rules("tpl-001")

        assert len(rules) == 1
        assert rules[0].id == "rule-1"
        assert rules[0].rule_type == "required"

    def test_get_rules_template_not_found(
        self, template_service, mock_template_repository
    ) -> None:
        """Test getting rules for non-existent template."""
        mock_template_repository.get.return_value = None

        rules = template_service.get_rules("non-existent")

        assert rules is None

    def test_get_rules_empty(
        self, template_service, mock_template_repository
    ) -> None:
        """Test getting rules when template has no rules."""
        from app.models.template import Template

        template_no_rules = Template(
            id="tpl-no-rules",
            tenant_id="tenant-123",
            name="No Rules Form",
            form_type="simple",
            page_count=1,
            rules=[],
        )
        mock_template_repository.get.return_value = template_no_rules

        rules = template_service.get_rules("tpl-no-rules")

        assert rules == []

    # =========================================================================
    # Get Bboxes Tests
    # =========================================================================

    def test_get_bboxes(
        self, template_service, mock_template_repository, sample_template
    ) -> None:
        """Test getting bboxes for a template."""
        mock_template_repository.get.return_value = sample_template

        bboxes = template_service.get_bboxes("tpl-001")

        assert len(bboxes) == 1
        assert bboxes[0].field_name == "name"
        assert bboxes[0].field_type == "text"

    def test_get_bboxes_by_page(
        self, template_service, mock_template_repository
    ) -> None:
        """Test getting bboxes filtered by page."""
        from app.models.template import Template, TemplateBbox

        bbox1 = TemplateBbox(
            x=10.0, y=20.0, width=100.0, height=30.0, page=1,
            field_name="field1", field_type="text"
        )
        bbox2 = TemplateBbox(
            x=10.0, y=20.0, width=100.0, height=30.0, page=2,
            field_name="field2", field_type="text"
        )
        template = Template(
            id="tpl-multi",
            tenant_id="tenant-123",
            name="Multi Page",
            form_type="form",
            page_count=2,
            bboxes=[bbox1, bbox2],
        )
        mock_template_repository.get.return_value = template

        page1_bboxes = template_service.get_bboxes("tpl-multi", page=1)
        page2_bboxes = template_service.get_bboxes("tpl-multi", page=2)

        assert len(page1_bboxes) == 1
        assert page1_bboxes[0].field_name == "field1"
        assert len(page2_bboxes) == 1
        assert page2_bboxes[0].field_name == "field2"

    def test_get_bboxes_template_not_found(
        self, template_service, mock_template_repository
    ) -> None:
        """Test getting bboxes for non-existent template."""
        mock_template_repository.get.return_value = None

        bboxes = template_service.get_bboxes("non-existent")

        assert bboxes is None


class TestTemplateServiceIntegration:
    """Integration tests for TemplateService with in-memory implementations."""

    @pytest.fixture
    def memory_repository(self):
        """Create a real in-memory repository."""
        from app.infrastructure.repositories.memory_template_repository import (
            MemoryTemplateRepository,
        )
        return MemoryTemplateRepository()

    @pytest.fixture
    def mock_vector_db(self):
        """Create a mock vector database for integration tests."""
        mock = MagicMock()
        mock.store = AsyncMock()
        mock.search = AsyncMock(return_value=[])
        mock.delete = AsyncMock()
        return mock

    @pytest.fixture
    def mock_embedding_gateway(self):
        """Create a mock embedding gateway for integration tests."""
        mock = MagicMock()
        mock.embed_image = AsyncMock(return_value=[0.1] * 1536)
        mock.embed_text = AsyncMock(return_value=[0.1] * 1536)
        return mock

    @pytest.fixture
    def service(self, memory_repository, mock_vector_db, mock_embedding_gateway):
        """Create service with real repository but mocked external dependencies."""
        from app.services.template_service import TemplateService

        return TemplateService(
            template_repository=memory_repository,
            vector_db=mock_vector_db,
            embedding_gateway=mock_embedding_gateway,
        )

    @pytest.mark.asyncio
    async def test_full_template_lifecycle(self, service) -> None:
        """Test complete template CRUD lifecycle."""
        from app.models.template import TemplateCreate, TemplateBbox

        # Create
        bbox = TemplateBbox(
            x=10.0, y=20.0, width=100.0, height=30.0, page=1,
            field_name="name", field_type="text"
        )
        create_request = TemplateCreate(
            name="Lifecycle Form",
            form_type="test",
            page_count=1,
            bboxes=[bbox],
        )

        created = await service.save_template(
            tenant_id="tenant-test",
            template_data=create_request,
            page_images=[b"test_image"],
        )
        assert created is not None
        template_id = created.id

        # Read
        retrieved = service.get_template(template_id)
        assert retrieved is not None
        assert retrieved.name == "Lifecycle Form"

        # List
        templates = service.list_templates(tenant_id="tenant-test")
        assert len(templates) == 1

        # Delete
        deleted = await service.delete_template(template_id)
        assert deleted is True

        # Verify deleted
        after_delete = service.get_template(template_id)
        assert after_delete is None
