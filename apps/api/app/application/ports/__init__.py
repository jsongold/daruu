"""Application ports (interfaces).

Ports define the contracts between the application layer and external systems.
Infrastructure adapters implement these interfaces, allowing the application
to be decoupled from specific technologies.

Port types:
- LLMGateway: Interface for LLM operations (label linking, ambiguity resolution)
- OCRGateway: Interface for OCR text extraction
- StorageGateway: Interface for file/document storage operations
- VectorDBGateway: Interface for vector database operations (template matching)
- CacheGateway: Interface for caching operations (session state, rate limiting)
- EmbeddingGateway: Interface for generating embeddings (visual/text)
"""

from app.application.ports.cache_gateway import CacheGateway
from app.application.ports.embedding_gateway import EmbeddingGateway
from app.application.ports.llm_gateway import LLMGateway
from app.application.ports.ocr_gateway import OCRGateway
from app.application.ports.storage_gateway import StorageGateway
from app.application.ports.vector_db_gateway import VectorDBGateway

__all__ = [
    "CacheGateway",
    "EmbeddingGateway",
    "LLMGateway",
    "OCRGateway",
    "StorageGateway",
    "VectorDBGateway",
]
