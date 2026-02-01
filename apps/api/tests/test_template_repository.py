"""Tests for Template repository.

Tests in-memory template repository:
- CRUD operations
- List by tenant
- Find by form type
- Not found cases
- Duplicate ID handling
"""

from datetime import datetime, timezone

import pytest


class TestMemoryTemplateRepository:
    """Tests for MemoryTemplateRepository."""

    @pytest.fixture
    def repository(self):
        """Create a fresh repository for each test."""
        from app.infrastructure.repositories.memory_template_repository import (
            MemoryTemplateRepository,
        )
        return MemoryTemplateRepository()

    @pytest.fixture
    def sample_template(self):
        """Sample template for testing."""
        from app.models.template import Template, TemplateBbox, TemplateRule, FieldType, RuleType

        now = datetime.now(timezone.utc)
        bbox = TemplateBbox(
            id="name", x=10.0, y=20.0, width=100.0, height=30.0, page=1,
            field_type=FieldType.TEXT, label="Full Name"
        )
        rule = TemplateRule(
            field_id="name",
            rule_type=RuleType.REQUIRED,
            rule_config={"message": "Name is required"},
        )
        return Template(
            id="tpl-001",
            tenant_id="tenant-123",
            name="Application Form",
            form_type="application",
            bboxes=(bbox,),
            rules=(rule,),
            field_count=1,
            created_at=now,
            updated_at=now,
        )

    # =========================================================================
    # Create Tests
    # =========================================================================

    def test_create_template(self, repository, sample_template) -> None:
        """Test creating a new template."""
        created = repository.create(sample_template)

        assert created.id == "tpl-001"
        assert created.tenant_id == "tenant-123"
        assert created.name == "Application Form"
        assert created.form_type == "application"
        assert len(created.bboxes) == 1
        assert len(created.rules) == 1

    def test_create_multiple_templates(self, repository) -> None:
        """Test creating multiple templates."""
        from app.models.template import Template
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        template1 = Template(
            id="tpl-001",
            tenant_id="tenant-1",
            name="Form 1",
            form_type="type1",
            created_at=now,
            updated_at=now,
        )
        template2 = Template(
            id="tpl-002",
            tenant_id="tenant-1",
            name="Form 2",
            form_type="type2",
            created_at=now,
            updated_at=now,
        )

        repository.create(template1)
        repository.create(template2)

        assert repository.get("tpl-001") is not None
        assert repository.get("tpl-002") is not None

    def test_create_template_minimal(self, repository) -> None:
        """Test creating a template with minimal data."""
        from app.models.template import Template
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        template = Template(
            id="tpl-min",
            tenant_id="tenant-123",
            name="Minimal Form",
            form_type="simple",
            created_at=now,
            updated_at=now,
        )

        created = repository.create(template)

        assert created.id == "tpl-min"
        assert created.bboxes == ()
        assert created.rules == ()
        assert created.embedding_id is None

    # =========================================================================
    # Get Tests
    # =========================================================================

    def test_get_template(self, repository, sample_template) -> None:
        """Test retrieving a template by ID."""
        repository.create(sample_template)
        retrieved = repository.get(sample_template.id)

        assert retrieved is not None
        assert retrieved.id == sample_template.id
        assert retrieved.name == sample_template.name
        assert retrieved.tenant_id == sample_template.tenant_id

    def test_get_template_not_found(self, repository) -> None:
        """Test retrieving a non-existent template returns None."""
        result = repository.get("non-existent-id")
        assert result is None

    def test_get_template_after_delete(self, repository, sample_template) -> None:
        """Test retrieving a deleted template returns None."""
        repository.create(sample_template)
        repository.delete(sample_template.id)
        result = repository.get(sample_template.id)
        assert result is None

    # =========================================================================
    # Update Tests
    # =========================================================================

    def test_update_template(self, repository, sample_template) -> None:
        """Test updating a template."""
        from app.models.template import Template

        repository.create(sample_template)

        # Create updated template with new values
        updated_template = Template(
            id=sample_template.id,
            tenant_id=sample_template.tenant_id,
            name="Updated Form",
            form_type=sample_template.form_type,
            bboxes=sample_template.bboxes,
            rules=sample_template.rules,
            created_at=sample_template.created_at,
            updated_at=sample_template.updated_at,
        )

        updated = repository.update(updated_template)

        assert updated is not None
        assert updated.id == sample_template.id
        assert updated.name == "Updated Form"
        # Other fields should remain unchanged
        assert updated.tenant_id == sample_template.tenant_id
        assert updated.form_type == sample_template.form_type

    def test_update_template_not_found_raises(self, repository) -> None:
        """Test updating a non-existent template raises ValueError."""
        from app.models.template import Template
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        template = Template(
            id="non-existent",
            name="Test",
            form_type="test",
            created_at=now,
            updated_at=now,
        )

        with pytest.raises(ValueError):
            repository.update(template)

    def test_update_template_bboxes(self, repository, sample_template) -> None:
        """Test updating template bboxes."""
        from app.models.template import Template, TemplateBbox, FieldType

        repository.create(sample_template)

        new_bbox = TemplateBbox(
            id="address", x=50.0, y=100.0, width=200.0, height=40.0, page=2,
            field_type=FieldType.TEXT
        )
        updated_template = Template(
            id=sample_template.id,
            tenant_id=sample_template.tenant_id,
            name=sample_template.name,
            form_type=sample_template.form_type,
            bboxes=sample_template.bboxes + (new_bbox,),
            rules=sample_template.rules,
            created_at=sample_template.created_at,
            updated_at=sample_template.updated_at,
        )

        updated = repository.update(updated_template)

        assert updated is not None
        assert len(updated.bboxes) == 2

    def test_update_template_rules(self, repository, sample_template) -> None:
        """Test updating template rules."""
        from app.models.template import Template, TemplateRule, RuleType

        repository.create(sample_template)

        new_rule = TemplateRule(
            field_id="email",
            rule_type=RuleType.FORMAT,
            rule_config={"pattern": r"^\S+@\S+$"},
        )
        updated_template = Template(
            id=sample_template.id,
            tenant_id=sample_template.tenant_id,
            name=sample_template.name,
            form_type=sample_template.form_type,
            bboxes=sample_template.bboxes,
            rules=sample_template.rules + (new_rule,),
            created_at=sample_template.created_at,
            updated_at=sample_template.updated_at,
        )

        updated = repository.update(updated_template)

        assert updated is not None
        assert len(updated.rules) == 2

    # =========================================================================
    # Delete Tests
    # =========================================================================

    def test_delete_template(self, repository, sample_template) -> None:
        """Test deleting a template."""
        repository.create(sample_template)
        result = repository.delete(sample_template.id)

        assert result is True
        assert repository.get(sample_template.id) is None

    def test_delete_template_not_found(self, repository) -> None:
        """Test deleting a non-existent template returns False."""
        result = repository.delete("non-existent-id")
        assert result is False

    def test_delete_template_twice(self, repository, sample_template) -> None:
        """Test deleting the same template twice."""
        repository.create(sample_template)

        first_delete = repository.delete(sample_template.id)
        second_delete = repository.delete(sample_template.id)

        assert first_delete is True
        assert second_delete is False

    # =========================================================================
    # List Tests
    # =========================================================================

    def test_list_by_tenant(self, repository) -> None:
        """Test listing templates by tenant."""
        from app.models.template import Template
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        repository.create(Template(
            id="t1", tenant_id="tenant-1", name="Form 1", form_type="type1",
            created_at=now, updated_at=now
        ))
        repository.create(Template(
            id="t2", tenant_id="tenant-2", name="Form 2", form_type="type2",
            created_at=now, updated_at=now
        ))
        repository.create(Template(
            id="t3", tenant_id="tenant-1", name="Form 3", form_type="type3",
            created_at=now, updated_at=now
        ))

        tenant1_templates = repository.list_by_tenant("tenant-1")
        tenant2_templates = repository.list_by_tenant("tenant-2")

        assert len(tenant1_templates) == 2
        assert len(tenant2_templates) == 1
        assert all(t.tenant_id == "tenant-1" for t in tenant1_templates)
        assert all(t.tenant_id == "tenant-2" for t in tenant2_templates)

    def test_list_by_tenant_empty(self, repository, sample_template) -> None:
        """Test listing templates for a tenant with no templates."""
        repository.create(sample_template)

        result = repository.list_by_tenant("tenant-nonexistent")
        assert result == []

    # =========================================================================
    # Find by Form Type Tests
    # =========================================================================

    def test_find_by_form_type(self, repository) -> None:
        """Test finding templates by form type."""
        from app.models.template import Template
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        repository.create(Template(
            id="t1", tenant_id="tenant-1", name="App Form 1", form_type="application",
            created_at=now, updated_at=now
        ))
        repository.create(Template(
            id="t2", tenant_id="tenant-1", name="Tax Form", form_type="tax",
            created_at=now, updated_at=now
        ))
        repository.create(Template(
            id="t3", tenant_id="tenant-1", name="App Form 2", form_type="application",
            created_at=now, updated_at=now
        ))

        app_templates = repository.find_by_form_type("application", tenant_id="tenant-1")
        tax_templates = repository.find_by_form_type("tax", tenant_id="tenant-1")

        assert len(app_templates) == 2
        assert len(tax_templates) == 1
        assert all(t.form_type == "application" for t in app_templates)

    def test_find_by_form_type_empty(self, repository, sample_template) -> None:
        """Test finding templates when none match."""
        repository.create(sample_template)

        result = repository.find_by_form_type("nonexistent", tenant_id=sample_template.tenant_id)
        assert result == []

    # =========================================================================
    # Exists Tests
    # =========================================================================

    def test_exists_true(self, repository, sample_template) -> None:
        """Test exists returns True for existing template."""
        repository.create(sample_template)
        assert repository.exists(sample_template.id) is True

    def test_exists_false(self, repository) -> None:
        """Test exists returns False for non-existent template."""
        assert repository.exists("non-existent-id") is False


class TestTemplateRepositoryProtocol:
    """Tests to verify repository implements the protocol correctly."""

    def test_repository_implements_protocol(self) -> None:
        """Test that MemoryTemplateRepository implements TemplateRepository protocol."""
        from app.infrastructure.repositories.memory_template_repository import (
            MemoryTemplateRepository,
        )
        from app.repositories.template_repository import TemplateRepository

        repo = MemoryTemplateRepository()
        # This should not raise if protocol is implemented correctly
        _: TemplateRepository = repo

    def test_repository_methods_exist(self) -> None:
        """Test that all required methods exist on the repository."""
        from app.infrastructure.repositories.memory_template_repository import (
            MemoryTemplateRepository,
        )

        repo = MemoryTemplateRepository()

        # Check all required methods exist
        assert hasattr(repo, "create")
        assert hasattr(repo, "get")
        assert hasattr(repo, "update")
        assert hasattr(repo, "delete")
        assert hasattr(repo, "list_by_tenant")
        assert hasattr(repo, "find_by_form_type")
        assert hasattr(repo, "exists")

        # All should be callable
        assert callable(repo.create)
        assert callable(repo.get)
        assert callable(repo.update)
        assert callable(repo.delete)
        assert callable(repo.list_by_tenant)
        assert callable(repo.find_by_form_type)
        assert callable(repo.exists)
