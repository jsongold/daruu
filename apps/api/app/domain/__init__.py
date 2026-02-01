"""Domain layer - Core entities and domain rules.

This layer contains the core business entities that are independent of
any external concerns (frameworks, databases, UI, etc.).

The entities here are re-exported from the models package to maintain
backward compatibility while establishing the Clean Architecture structure.
"""

from app.domain.entities import (
    # Document entities
    Document,
    DocumentMeta,
    DocumentType,
    # Field entities
    FieldModel,
    FieldType,
    Mapping,
    # Evidence entities
    Evidence,
    # Job entities
    Activity,
    ActivityAction,
    Extraction,
    Issue,
    IssueSeverity,
    IssueType,
    JobContext,
    JobMode,
    JobStatus,
    # Common value objects
    BBox,
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
