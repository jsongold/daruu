"""Domain models for the Structure/Labelling service."""

from app.services.structure_labelling.domain.models import (
    BoxCandidate,
    DetectedStructures,
    EvidenceKind,
    LabelCandidate,
    LinkedField,
    StructureEvidence,
    TableCandidate,
    TableCell,
    TextBlock,
)

__all__ = [
    "BoxCandidate",
    "DetectedStructures",
    "EvidenceKind",
    "LabelCandidate",
    "LinkedField",
    "StructureEvidence",
    "TableCandidate",
    "TableCell",
    "TextBlock",
]
