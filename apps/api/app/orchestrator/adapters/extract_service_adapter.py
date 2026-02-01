"""Adapter to make ExtractService conform to ExtractServicePort.

This adapter bridges the ExtractService (domain service) with the
ExtractServicePort interface expected by the orchestrator.
"""

from app.models.extract.models import ExtractRequest, ExtractResult
from app.services.extract import ExtractService
from app.orchestrator.application.ports.pipeline_services import (
    ExtractServicePort,
)


class ExtractServiceAdapter:
    """Adapter that makes ExtractService conform to ExtractServicePort.

    This adapter wraps ExtractService and implements ExtractServicePort
    so it can be used by the orchestrator's ServiceClient.
    """

    def __init__(self, extract_service: ExtractService) -> None:
        """Initialize the adapter.

        Args:
            extract_service: The ExtractService instance to wrap
        """
        self._extract_service = extract_service

    async def extract(self, request: ExtractRequest) -> ExtractResult:
        """Extract values from a document.

        Delegates to the wrapped ExtractService.

        Args:
            request: Extract request with document and field definitions

        Returns:
            ExtractResult with extractions and evidence
        """
        return await self._extract_service.extract(request)
