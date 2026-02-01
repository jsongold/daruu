"""Template service package.

Provides business logic for template management and matching.

Components:
- TemplateService: Main service for template CRUD and matching operations
"""

from app.services.template.service import TemplateService

__all__ = [
    "TemplateService",
]
