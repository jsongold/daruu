"""Domain rules for the Ingest service.

This module contains pure domain logic for:
- PDF validation rules
- Page rendering configuration
- Error classification
"""

from app.services.ingest.domain.rules import (
    DEFAULT_RENDER_CONFIG,
    RenderConfig,
    ValidationResult,
    classify_pdf_error,
    validate_page_range,
    validate_pdf_signature,
    validate_render_config,
)

__all__ = [
    "ValidationResult",
    "validate_page_range",
    "validate_pdf_signature",
    "validate_render_config",
    "classify_pdf_error",
    "RenderConfig",
    "DEFAULT_RENDER_CONFIG",
]
