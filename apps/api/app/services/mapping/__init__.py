"""Mapping Service for Source-Target field correspondence.

This module provides:
- MappingService: Deterministic mapping + Agent call coordination
- MappingAgent: LLM-based reasoning for ambiguous mappings (via Port interface)

The service generates Mapping[] from Source/Target Field[] pairs,
supporting 1:1, 1:N, and table row mappings.
"""

from app.services.mapping.service import MappingService

__all__ = [
    "MappingService",
]
