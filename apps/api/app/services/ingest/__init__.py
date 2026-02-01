"""Ingest service for PDF normalization and metadata extraction.

This service handles:
- PDF validation (broken files, password protection, etc.)
- Metadata extraction (page count, dimensions, rotation)
- Page rendering for preview images (LLM/OCR processing)

Architecture:
- IngestService: Main service orchestrating the ingest workflow
- Ports: Protocol interfaces (PdfReaderPort, StoragePort)
- Adapters: Concrete implementations (PyMuPdfAdapter, LocalStorageAdapter)
- Domain: Pure validation rules and business logic
"""

from app.models.ingest import (
    DocumentMeta,
    IngestError,
    IngestErrorCode,
    IngestRequest,
    IngestResult,
    PageMeta,
    RenderedPage,
)
from app.services.ingest.adapters import LocalStorageAdapter, PyMuPdfAdapter
from app.services.ingest.ports import PdfReaderPort, StoragePort
from app.services.ingest.service import IngestService

__all__ = [
    # Models (re-exported from app.models.ingest)
    "DocumentMeta",
    "IngestError",
    "IngestErrorCode",
    "IngestRequest",
    "IngestResult",
    "PageMeta",
    "RenderedPage",
    # Service
    "IngestService",
    # Ports
    "PdfReaderPort",
    "StoragePort",
    # Adapters
    "PyMuPdfAdapter",
    "LocalStorageAdapter",
]
