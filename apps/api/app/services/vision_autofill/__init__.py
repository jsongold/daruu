"""Vision Autofill Service package.

This package provides LLM vision-based form autofill capabilities.
"""

from app.services.vision_autofill.models import (
    FieldInfo,
    FilledField,
    VisionAutofillRequest,
    VisionAutofillResponse,
)
from app.services.vision_autofill.prompts import (
    AUTOFILL_SYSTEM_PROMPT,
    build_autofill_prompt,
    format_data_sources,
)
from app.services.vision_autofill.service import (
    VisionAutofillService,
    get_vision_autofill_service,
)

__all__ = [
    # Models
    "FieldInfo",
    "FilledField",
    "VisionAutofillRequest",
    "VisionAutofillResponse",
    # Prompts
    "AUTOFILL_SYSTEM_PROMPT",
    "build_autofill_prompt",
    "format_data_sources",
    # Service
    "VisionAutofillService",
    "get_vision_autofill_service",
]
