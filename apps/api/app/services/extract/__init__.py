"""Extract service for value extraction from PDF documents.

This service coordinates value extraction using:
1. Native PDF text extraction (deterministic)
2. OCR processing (deterministic)
3. LLM-assisted ambiguity resolution (ValueExtractionAgent)

Service vs Agent:
- ExtractService: Deterministic coordination of extraction pipeline
- OcrService: Deterministic OCR processing
- ValueExtractionAgent: LLM-powered reasoning for ambiguity resolution

Clean Architecture:
- ports.py: Port interfaces for dependency injection
- service.py: Main ExtractService implementation
- adapters.py: Concrete adapter implementations
- domain/: Domain models and value objects

NOTE: Agent implementations are in app.agents.extract, not here.
Import agents as:
    from app.agents.extract import LangChainValueExtractionAgent
"""

from app.services.extract.adapters import (
    PaddleOcrAdapter,
    PdfPlumberTextAdapter,
    TesseractAdapter,
)
from app.services.extract.ports import (
    NativeTextExtractorPort,
    OcrServicePort,
    ValueExtractionAgentPort,
)
from app.services.extract.service import ExtractService

__all__ = [
    # Service
    "ExtractService",
    # Ports
    "NativeTextExtractorPort",
    "OcrServicePort",
    "ValueExtractionAgentPort",
    # Adapters
    "PdfPlumberTextAdapter",
    "PaddleOcrAdapter",
    "TesseractAdapter",
]
