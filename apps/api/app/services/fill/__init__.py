"""Fill service for PDF form filling and text overlay.

This service handles:
- AcroForm field filling for PDF forms
- Text overlay generation for non-form PDFs
- Text layout and rendering rules
- Merge operations for filled documents

This is a deterministic Service (no Agent/LLM):
- Same input always produces the same output
- All text rendering rules are algorithmic
- Unit testable with predictable results
"""

from app.models.fill import (
    FieldFillResult,
    FillError,
    FillErrorCode,
    FillIssue,
    FillMethod,
    FillRequest,
    FillResult,
    FillValue,
    IssueSeverity,
    IssueType,
    RenderArtifact,
    RenderParams,
)
from app.services.fill.adapters import (
    LocalStorageAdapter,
    PyMuPdfAcroFormAdapter,
    PyMuPdfMergerAdapter,
    PyMuPdfReaderAdapter,
    ReportlabMeasureAdapter,
    ReportlabOverlayAdapter,
)
from app.services.fill.ports import (
    AcroFormWriterPort,
    OverlayRendererPort,
    PdfMergerPort,
    PdfReaderPort,
    StoragePort,
    TextMeasurePort,
)
from app.services.fill.service import FillService

__all__ = [
    # Service
    "FillService",
    # Ports (interfaces)
    "AcroFormWriterPort",
    "OverlayRendererPort",
    "PdfMergerPort",
    "PdfReaderPort",
    "StoragePort",
    "TextMeasurePort",
    # Adapters (implementations)
    "LocalStorageAdapter",
    "PyMuPdfAcroFormAdapter",
    "PyMuPdfMergerAdapter",
    "PyMuPdfReaderAdapter",
    "ReportlabMeasureAdapter",
    "ReportlabOverlayAdapter",
    # Models (re-exported for convenience)
    "FieldFillResult",
    "FillError",
    "FillErrorCode",
    "FillIssue",
    "FillMethod",
    "FillRequest",
    "FillResult",
    "FillValue",
    "IssueSeverity",
    "IssueType",
    "RenderArtifact",
    "RenderParams",
]
