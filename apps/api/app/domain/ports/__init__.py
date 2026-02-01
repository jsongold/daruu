"""Domain ports - re-exports from application layer.

All port interfaces are defined in app.application.ports.
This module provides a convenience import path from the domain layer.

All external services must implement these interfaces.
This ensures swappability without changing business logic.
"""

from app.application.ports import (
    CacheGateway,
    EmbeddingGateway,
    LLMGateway,
    OCRGateway,
    StorageGateway,
    VectorDBGateway,
)

# Alias names for backward compatibility
StoragePort = StorageGateway
LLMPort = LLMGateway
VectorDBPort = VectorDBGateway
CachePort = CacheGateway
EmbeddingPort = EmbeddingGateway
OCRPort = OCRGateway

__all__ = [
    # Gateway names (preferred)
    "CacheGateway",
    "EmbeddingGateway",
    "LLMGateway",
    "OCRGateway",
    "StorageGateway",
    "VectorDBGateway",
    # Port aliases
    "CachePort",
    "EmbeddingPort",
    "LLMPort",
    "OCRPort",
    "StoragePort",
    "VectorDBPort",
]
