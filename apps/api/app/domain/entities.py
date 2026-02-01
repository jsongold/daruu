"""Domain entities - Core business objects.

This module re-exports entities from the models package to maintain
backward compatibility. The entities follow immutable patterns
(frozen=True in Pydantic models).

Domain Rules:
- All entities are immutable (frozen)
- Entities should not depend on infrastructure
- Domain logic should be pure (same input -> same output)
"""

# Re-export from existing models to maintain backward compatibility
# while establishing Clean Architecture boundaries

from app.models.common import BBox
from app.models.document import Document, DocumentMeta, DocumentType
from app.models.evidence import Evidence
from app.models.field import FieldModel, FieldType, Mapping
from app.models.job import (
    Activity,
    ActivityAction,
    Extraction,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobMode,
    JobStatus,
)

__all__ = [
    # Common value objects
    "BBox",
    # Document entities
    "Document",
    "DocumentMeta",
    "DocumentType",
    # Evidence entities
    "Evidence",
    # Field entities
    "FieldModel",
    "FieldType",
    "Mapping",
    # Job entities
    "Activity",
    "ActivityAction",
    "Extraction",
    "Issue",
    "IssueSeverity",
    "IssueType",
    "JobContext",
    "JobMode",
    "JobStatus",
]
