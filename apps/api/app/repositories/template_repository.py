"""Template repository interface (Port).

This defines the contract for template persistence operations.
Implementations can be in-memory, database, or any other storage.

Following Clean Architecture, the application layer depends on this
interface, not on concrete implementations.
"""

from typing import Protocol

from app.models.template import Template


class TemplateRepository(Protocol):
    """Repository interface for Template entities.

    This protocol defines the contract that any template storage
    implementation must satisfy. The application layer depends on
    this interface, allowing easy testing and backend swapping.

    Example:
        class PostgresTemplateRepository:
            def create(self, template: Template) -> Template: ...
            def get(self, template_id: str) -> Template | None: ...
            # etc.

        # Inject into service
        service = TemplateService(repo=PostgresTemplateRepository())
    """

    def create(self, template: Template) -> Template:
        """Create a new template record.

        Args:
            template: Template entity to create.

        Returns:
            Created Template entity (may have updated ID/timestamps).
        """
        ...

    def get(self, template_id: str) -> Template | None:
        """Get a template by ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            Template if found, None otherwise.
        """
        ...

    def list_by_tenant(self, tenant_id: str | None = None) -> list[Template]:
        """List templates, optionally filtered by tenant.

        Args:
            tenant_id: Optional tenant ID to filter by.
                       If None, returns templates with no tenant (global).

        Returns:
            List of templates matching the criteria.
        """
        ...

    def update(self, template: Template) -> Template:
        """Update an existing template.

        Args:
            template: Template entity with updated values.
                     The ID must match an existing template.

        Returns:
            Updated Template entity.

        Raises:
            ValueError: If template with given ID doesn't exist.
        """
        ...

    def delete(self, template_id: str) -> bool:
        """Delete a template by ID.

        Args:
            template_id: Unique template identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    def find_by_form_type(
        self,
        form_type: str,
        tenant_id: str | None = None,
    ) -> list[Template]:
        """Find templates by form type.

        Args:
            form_type: Form type identifier (e.g., "W-9", "I-9").
            tenant_id: Optional tenant ID to filter by.

        Returns:
            List of templates matching the form type.
        """
        ...

    def exists(self, template_id: str) -> bool:
        """Check if a template exists.

        Args:
            template_id: Unique template identifier.

        Returns:
            True if template exists, False otherwise.
        """
        ...
