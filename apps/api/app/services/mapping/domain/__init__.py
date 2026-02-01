"""Domain models for the Mapping service.

Contains core domain entities that represent mapping concepts
independent of infrastructure concerns.
"""

from app.services.mapping.domain.models import (
    MappingCandidate,
    MappingDecision,
    MappingReason,
    MappingRule,
    MappingType,
)

__all__ = [
    "MappingCandidate",
    "MappingDecision",
    "MappingReason",
    "MappingRule",
    "MappingType",
]
