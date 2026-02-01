"""Application use cases.

Use cases contain application-specific business rules and orchestrate
domain entities and ports to accomplish specific tasks.

Use cases defined here:
- AnalyzeDocumentUseCase: Analyze document structure and detect fields
- ExtractValuesUseCase: Extract values from source document
- FillDocumentUseCase: Fill target document with extracted values
"""

from app.application.use_cases.analyze_document import AnalyzeDocumentUseCase
from app.application.use_cases.extract_values import ExtractValuesUseCase
from app.application.use_cases.fill_document import FillDocumentUseCase

__all__ = [
    "AnalyzeDocumentUseCase",
    "ExtractValuesUseCase",
    "FillDocumentUseCase",
]
