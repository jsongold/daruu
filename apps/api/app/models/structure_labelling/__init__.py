"""Pydantic models for the Structure/Labelling API."""

from app.models.structure_labelling.models import (
    BoxCandidateInput,
    EvidenceOutput,
    FieldOutput,
    PageImageInput,
    StructureLabellingRequest,
    StructureLabellingResult,
    TableCandidateInput,
    TextBlockInput,
)

__all__ = [
    "BoxCandidateInput",
    "EvidenceOutput",
    "FieldOutput",
    "PageImageInput",
    "StructureLabellingRequest",
    "StructureLabellingResult",
    "TableCandidateInput",
    "TextBlockInput",
]
