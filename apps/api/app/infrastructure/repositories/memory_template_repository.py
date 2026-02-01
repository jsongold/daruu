"""In-memory template repository implementation.

MVP implementation for testing and development.
Data is stored in memory and lost when the application restarts.

For production, use a database-backed implementation (e.g., Supabase).
"""

from datetime import datetime, timezone

from app.models.template import Template
from app.repositories.template_repository import TemplateRepository


class MemoryTemplateRepository:
    """In-memory implementation of TemplateRepository.

    Stores templates in a dictionary keyed by ID.
    Thread-safe for single-process use (no async locking needed
    since dict operations are atomic in CPython).

    Example:
        repo = MemoryTemplateRepository()
        template = Template(id="t-1", name="W-9", ...)
        created = repo.create(template)
        retrieved = repo.get("t-1")
    """

    def __init__(self) -> None:
        """Initialize the repository with empty storage."""
        self._templates: dict[str, Template] = {}

    def create(self, template: Template) -> Template:
        """Create a new template record.

        Args:
            template: Template entity to create.

        Returns:
            The template as stored (unchanged).
        """
        self._templates[template.id] = template
        return template

    def get(self, template_id: str) -> Template | None:
        """Get a template by ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            Template if found, None otherwise.
        """
        return self._templates.get(template_id)

    def list_by_tenant(self, tenant_id: str | None = None) -> list[Template]:
        """List templates, optionally filtered by tenant.

        Args:
            tenant_id: Optional tenant ID to filter by.

        Returns:
            List of templates matching the criteria, sorted by name.
        """
        templates = [
            t for t in self._templates.values() if t.tenant_id == tenant_id
        ]
        return sorted(templates, key=lambda t: t.name)

    def update(self, template: Template) -> Template:
        """Update an existing template.

        Creates a new immutable template with updated values.

        Args:
            template: Template entity with updated values.

        Returns:
            Updated Template entity.

        Raises:
            ValueError: If template with given ID doesn't exist.
        """
        if template.id not in self._templates:
            raise ValueError(f"Template not found: {template.id}")

        # Update the updated_at timestamp (immutable pattern)
        updated_template = Template(
            id=template.id,
            name=template.name,
            form_type=template.form_type,
            bboxes=template.bboxes,
            rules=template.rules,
            embedding_id=template.embedding_id,
            preview_url=template.preview_url,
            field_count=template.field_count,
            created_at=template.created_at,
            updated_at=datetime.now(timezone.utc),
            tenant_id=template.tenant_id,
        )

        self._templates[template.id] = updated_template
        return updated_template

    def delete(self, template_id: str) -> bool:
        """Delete a template by ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            True if deleted, False if not found.
        """
        if template_id in self._templates:
            del self._templates[template_id]
            return True
        return False

    def find_by_form_type(
        self,
        form_type: str,
        tenant_id: str | None = None,
    ) -> list[Template]:
        """Find templates by form type.

        Args:
            form_type: Form type identifier (case-insensitive).
            tenant_id: Optional tenant ID to filter by.

        Returns:
            List of templates matching the form type, sorted by name.
        """
        form_type_lower = form_type.lower()
        templates = [
            t
            for t in self._templates.values()
            if t.form_type.lower() == form_type_lower and t.tenant_id == tenant_id
        ]
        return sorted(templates, key=lambda t: t.name)

    def exists(self, template_id: str) -> bool:
        """Check if a template exists.

        Args:
            template_id: Unique template identifier.

        Returns:
            True if template exists, False otherwise.
        """
        return template_id in self._templates

    def clear(self) -> None:
        """Clear all templates from storage.

        Useful for testing.
        """
        self._templates.clear()


# Type assertion to verify protocol compliance
_assert_template_repo: TemplateRepository = MemoryTemplateRepository()
