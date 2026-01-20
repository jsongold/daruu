from __future__ import annotations

from typing import Any, Protocol

from app.models.template_schema import DraftTemplate
from app.services.pdf_render import RenderedPage


class AnalysisStrategy(Protocol):
    """Interface for LLM analysis strategies."""

    async def analyze(
        self, pages: list[RenderedPage], schema_json: dict[str, Any]
    ) -> DraftTemplate:
        """
        Analyze the rendered PDF pages and return a DraftTemplate.

        Args:
            pages: List of rendered PDF pages (images + metadata).
            schema_json: JSON schema of the DraftTemplate for the LLM to follow.

        Returns:
            DraftTemplate: The analyzed template structure.
        """
        ...
