"""Pipeline service port interfaces for orchestrator.

These protocols define the contracts for calling pipeline services.
Each service has a dedicated port interface to maintain clean separation
and enable testing with mock implementations.

Service Architecture (per PRD):
- Orchestrator calls Services via these ports
- Services may internally use Agents (LLM reasoning)
- Services may internally use other Services (deterministic operations)
- Orchestrator only knows about contracts (input/output), not implementation

Pipeline Sequence:
Ingest -> Structure/Labelling -> Mapping -> Extract -> Adjust -> Fill -> Review
"""

from typing import Protocol

from app.models.adjust.models import AdjustRequest, AdjustResult
from app.models.extract.models import ExtractRequest, ExtractResult
from app.models.fill.models import FillRequest, FillResult
from app.models.ingest.models import IngestRequest, IngestResult
from app.models.mapping.models import MappingRequest, MappingResult
from app.models.review.models import ReviewRequest, ReviewResult
from app.models.structure_labelling.models import (
    StructureLabellingRequest,
    StructureLabellingResult,
)


class IngestServicePort(Protocol):
    """Port for calling the Ingest service.

    The Ingest service handles:
    - PDF validation and normalization
    - Page rendering to images for downstream processing
    - Metadata extraction (page count, dimensions, rotation)

    This is a deterministic service (no LLM/Agent).
    """

    async def ingest(self, request: IngestRequest) -> IngestResult:
        """Ingest a PDF document.

        Validates the document, extracts metadata, and renders
        pages to images for downstream processing.

        Args:
            request: Ingest request with document ID and reference.

        Returns:
            IngestResult with metadata, artifacts, and any errors.
        """
        ...


class StructureLabellingServicePort(Protocol):
    """Port for calling the Structure/Labelling service.

    The Structure/Labelling service handles:
    - Document structure detection (boxes, tables, text regions)
    - Label-to-position linking (uses FieldLabellingAgent internally)
    - Field identification with confidence scores

    This service internally uses FieldLabellingAgent for LLM reasoning.
    """

    async def process(self, request: StructureLabellingRequest) -> StructureLabellingResult:
        """Process a document for structure detection and field labelling.

        Analyzes the document structure and links labels to
        field positions using LLM reasoning.

        Args:
            request: Structure labelling request with page images and candidates.

        Returns:
            StructureLabellingResult with detected fields and evidence.
        """
        ...


class MappingServicePort(Protocol):
    """Port for calling the Mapping service.

    The Mapping service handles:
    - Source-to-target field correspondence
    - String similarity matching (deterministic)
    - Ambiguity resolution (uses MappingAgent internally)
    - User rule application

    This service internally uses MappingAgent for LLM reasoning.
    """

    async def map_fields(self, request: MappingRequest) -> MappingResult:
        """Generate field mappings from source to target.

        Matches source fields to target fields using string matching
        and LLM reasoning for ambiguous cases.

        Args:
            request: Mapping request with source/target fields and options.

        Returns:
            MappingResult with mappings and followup questions.
        """
        ...


class ExtractServicePort(Protocol):
    """Port for calling the Extract service.

    The Extract service handles:
    - Native PDF text extraction (deterministic)
    - OCR for images/scanned content (deterministic via OcrService)
    - Ambiguity resolution (uses ValueExtractionAgent internally)
    - Value normalization

    This service internally uses OcrService and ValueExtractionAgent.
    """

    async def extract(self, request: ExtractRequest) -> ExtractResult:
        """Extract values from a document.

        Extracts field values using native text, OCR, and LLM
        for ambiguity resolution.

        Args:
            request: Extract request with document and field definitions.

        Returns:
            ExtractResult with extractions and evidence.
        """
        ...


class AdjustServicePort(Protocol):
    """Port for calling the Adjust service.

    The Adjust service handles:
    - Bbox corrections for overflow/overlap
    - Coordinate adjustment based on anchors
    - Render parameter optimization

    This is a deterministic service (no LLM/Agent).
    """

    async def adjust(self, request: AdjustRequest) -> AdjustResult:
        """Perform field bbox adjustments.

        Analyzes issues and generates patches to resolve
        overflow and overlap problems.

        Args:
            request: Adjust request with fields, issues, and page metadata.

        Returns:
            AdjustResult with patches and confidence updates.
        """
        ...


class FillServicePort(Protocol):
    """Port for calling the Fill service.

    The Fill service handles:
    - AcroForm field filling (deterministic)
    - Overlay text rendering (deterministic)
    - PDF merging

    This is a deterministic service (no LLM/Agent).
    """

    async def fill(self, request: FillRequest) -> FillResult:
        """Fill a PDF document with values.

        Fills field values into the target document using
        AcroForm or overlay method.

        Args:
            request: Fill request with document reference and values.

        Returns:
            FillResult with filled document reference.
        """
        ...


class ReviewServicePort(Protocol):
    """Port for calling the Review service.

    The Review service handles:
    - Visual inspection (PDF rendering)
    - Diff generation against original
    - Issue detection (overflow, overlap, missing values)
    - Preview artifact generation

    This is a deterministic service (no LLM/Agent).
    """

    async def review(self, request: ReviewRequest) -> ReviewResult:
        """Review a filled document for issues.

        Renders the document, generates diffs, and detects
        issues for final validation.

        Args:
            request: Review request with document refs and fields.

        Returns:
            ReviewResult with issues and preview artifacts.
        """
        ...
