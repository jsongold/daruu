"""Application layer - Use cases and ports (interfaces).

This layer contains:
- Use cases: Application-specific business rules
- Ports: Interfaces that define how the application interacts with external systems

The application layer depends only on the domain layer and defines
interfaces (ports) that infrastructure adapters implement.
"""

from app.application.ports import (
    LLMGateway,
    OCRGateway,
    StorageGateway,
)
from app.application.use_cases import (
    AnalyzeDocumentUseCase,
    ExtractValuesUseCase,
    FillDocumentUseCase,
)

__all__ = [
    # Ports (interfaces)
    "LLMGateway",
    "OCRGateway",
    "StorageGateway",
    # Use cases
    "AnalyzeDocumentUseCase",
    "ExtractValuesUseCase",
    "FillDocumentUseCase",
]
