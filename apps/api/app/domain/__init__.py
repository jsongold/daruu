"""Domain layer - Core entities and domain rules.

This layer contains the core business entities that are independent of
any external concerns (frameworks, databases, UI, etc.).

The entities here are re-exported from the models package to maintain
backward compatibility while establishing the Clean Architecture structure.
"""

from app.domain.entities import (
    # Job entities
    Activity,
    ActivityAction,
    # Common value objects
    BBox,
    # Document entities
    Document,
    DocumentMeta,
    DocumentType,
    # Evidence entities
    Evidence,
    Extraction,
    # Field entities
    FieldModel,
    FieldType,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobMode,
    JobStatus,
    Mapping,
)

__all__ = [
    # Document
    "Document",
    "DocumentMeta",
    "DocumentType",
    # Field
    "FieldModel",
    "FieldType",
    "Mapping",
    # Evidence
    "Evidence",
    # Job
    "Activity",
    "ActivityAction",
    "Extraction",
    "Issue",
    "IssueSeverity",
    "IssueType",
    "JobContext",
    "JobMode",
    "JobStatus",
    # Common
    "BBox",
]
