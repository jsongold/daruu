"""Infrastructure adapters for gateway interfaces.

This module contains concrete implementations of gateway interfaces
defined in `app.application.ports`. These adapters connect the
application to external services and resources.

Current implementations:
- MemoryVectorDB: In-memory vector database for development/testing
- MemoryEmbedding: Mock embedding generator for development/testing

Production implementations would include:
- SupabaseVectorDB: pgvector-based similarity search
- OpenAIEmbedding: OpenAI embedding API
- CLIPEmbedding: CLIP visual embeddings
"""

from app.infrastructure.adapters.memory_vector_db import MemoryVectorDB
from app.infrastructure.adapters.memory_embedding import MemoryEmbedding

__all__ = [
    "MemoryVectorDB",
    "MemoryEmbedding",
]
