"""Factory functions for creating service instances.

These factories create configured service instances with all
their dependencies wired up properly.
"""

from typing import cast

from app.services.extract import ExtractService
from app.services.extract.adapters import PdfPlumberTextAdapter
from app.agents.extract import LangChainValueExtractionAgent
from app.services.extract.ports import OcrServicePort
from app.orchestrator.adapters.extract_service_adapter import (
    ExtractServiceAdapter,
)
from app.orchestrator.application.ports.pipeline_services import (
    AdjustServicePort,
    ExtractServicePort,
    FillServicePort,
    IngestServicePort,
    MappingServicePort,
    ReviewServicePort,
    StructureLabellingServicePort,
)

# Import services
from app.services.ingest.service import IngestService
from app.services.ingest.adapters import PyMuPdfAdapter, LocalStorageAdapter as IngestStorageAdapter
from app.services.structure_labelling.service import StructureLabellingService
from app.services.structure_labelling.adapters import (
    OpenCVStructureDetector,
    LocalPageImageLoader,
)
from app.services.mapping.service import MappingService
from app.services.mapping.adapters import RapidFuzzStringMatcher, InMemoryTemplateHistory
from app.services.adjust.service import AdjustService
from app.services.adjust.adapters import SimpleOverlapDetector
from app.services.fill.service import FillService
from app.services.fill.adapters import (
    PyMuPdfReaderAdapter as FillPdfReader,
    PyMuPdfAcroFormAdapter,
    ReportlabOverlayAdapter,
    PyMuPdfMergerAdapter,
    LocalStorageAdapter as FillStorageAdapter,
    ReportlabMeasureAdapter,
)
from app.services.review.service import ReviewService
from app.services.review.adapters import (
    PyMuPdfRenderer,
    OpenCVDiffGenerator,
    RuleBasedIssueDetector,
    LocalPreviewStorage,
)

# Import request/result types for adapters
from app.models.ingest.models import IngestRequest, IngestResult
from app.models.structure_labelling.models import (
    StructureLabellingRequest,
    StructureLabellingResult,
)
from app.models.mapping.models import MappingRequest, MappingResult
from app.models.adjust.models import AdjustRequest, AdjustResult
from app.models.fill.models import FillRequest, FillResult
from app.models.review.models import ReviewRequest, ReviewResult


class NullOcrService:
    """Null object pattern for OCR service when OCR is not available.
    
    This implements OcrServicePort but always returns None,
    indicating that OCR is not available. The ExtractService
    will handle this gracefully by skipping OCR extraction.
    """

    async def recognize(
        self,
        image_data: bytes,
        page: int,
        region: None = None,
        language: str = "ja+en",
    ) -> None:
        """Return None to indicate OCR is not available."""
        return None

    async def recognize_region(
        self,
        image_data: bytes,
        page: int,
        bbox: None,
        language: str = "ja+en",
    ) -> None:
        """Return None to indicate OCR is not available."""
        return None


def create_extract_service() -> ExtractService:
    """Create a configured ExtractService instance.

    Returns:
        ExtractService with all adapters wired up
    """
    # Create adapters
    native_extractor = PdfPlumberTextAdapter()
    # OCR adapter - using null object for now since OCR is not fully implemented
    # In production, this would be PaddleOcrAdapter() or TesseractAdapter()
    ocr_service = cast(OcrServicePort, NullOcrService())
    extraction_agent = LangChainValueExtractionAgent()

    # Create service
    return ExtractService(
        native_extractor=native_extractor,
        ocr_service=ocr_service,
        extraction_agent=extraction_agent,
    )


def create_extract_service_port() -> ExtractServicePort:
    """Create an ExtractServicePort implementation.

    Returns:
        ExtractServicePort adapter wrapping ExtractService
    """
    extract_service = create_extract_service()
    return ExtractServiceAdapter(extract_service)


# =============================================================================
# Service Adapters that wrap services to implement port interfaces
# =============================================================================


class IngestServiceAdapter:
    """Adapter that makes IngestService conform to IngestServicePort."""

    def __init__(self, service: IngestService) -> None:
        self._service = service

    async def ingest(self, request: IngestRequest) -> IngestResult:
        """Ingest a PDF document."""
        return await self._service.ingest(request)


class StructureLabellingServiceAdapter:
    """Adapter that makes StructureLabellingService conform to StructureLabellingServicePort."""

    def __init__(self, service: StructureLabellingService) -> None:
        self._service = service

    async def process(self, request: StructureLabellingRequest) -> StructureLabellingResult:
        """Process a document for structure detection and field labelling."""
        return await self._service.process(request)


class MappingServiceAdapter:
    """Adapter that makes MappingService conform to MappingServicePort."""

    def __init__(self, service: MappingService) -> None:
        self._service = service

    async def map_fields(self, request: MappingRequest) -> MappingResult:
        """Generate field mappings from source to target."""
        return await self._service.map_fields(request)


class AdjustServiceAdapter:
    """Adapter that makes AdjustService conform to AdjustServicePort."""

    def __init__(self, service: AdjustService) -> None:
        self._service = service

    async def adjust(self, request: AdjustRequest) -> AdjustResult:
        """Perform field bbox adjustments."""
        return await self._service.adjust(request)


class FillServiceAdapter:
    """Adapter that makes FillService conform to FillServicePort."""

    def __init__(self, service: FillService) -> None:
        self._service = service

    async def fill(self, request: FillRequest) -> FillResult:
        """Fill a PDF document with values."""
        return await self._service.fill(request)


class ReviewServiceAdapter:
    """Adapter that makes ReviewService conform to ReviewServicePort."""

    def __init__(self, service: ReviewService) -> None:
        self._service = service

    async def review(self, request: ReviewRequest) -> ReviewResult:
        """Review a filled document for issues."""
        return await self._service.review(request)


# =============================================================================
# Factory functions for creating service instances
# =============================================================================


def create_ingest_service() -> IngestService:
    """Create a configured IngestService instance.

    Returns:
        IngestService with all adapters wired up
    """
    pdf_reader = PyMuPdfAdapter()
    storage = IngestStorageAdapter(base_path="/tmp/ingest-artifacts")
    return IngestService(pdf_reader=pdf_reader, storage=storage)


def create_ingest_service_port() -> IngestServicePort:
    """Create an IngestServicePort implementation.

    Returns:
        IngestServicePort adapter wrapping IngestService
    """
    service = create_ingest_service()
    return IngestServiceAdapter(service)


def create_structure_labelling_service() -> StructureLabellingService:
    """Create a configured StructureLabellingService instance.

    Note: This requires a FieldLabellingAgent which uses LLM.
    For now, we use a stub implementation.

    Returns:
        StructureLabellingService with all adapters wired up
    """
    from app.agents.structure_labelling import LangChainFieldLabellingAgent

    structure_detector = OpenCVStructureDetector()
    page_image_loader = LocalPageImageLoader(base_path="/tmp/ingest-artifacts")
    # Create the LLM-based field labelling agent
    field_labelling_agent = LangChainFieldLabellingAgent()
    return StructureLabellingService(
        field_labelling_agent=field_labelling_agent,
        structure_detector=structure_detector,
        page_image_loader=page_image_loader,
    )


def create_structure_labelling_service_port() -> StructureLabellingServicePort:
    """Create a StructureLabellingServicePort implementation.

    Returns:
        StructureLabellingServicePort adapter wrapping StructureLabellingService
    """
    service = create_structure_labelling_service()
    return StructureLabellingServiceAdapter(service)


def create_mapping_service() -> MappingService:
    """Create a configured MappingService instance.

    Returns:
        MappingService with all adapters wired up
    """
    from app.agents.mapping import LangChainMappingAgent

    string_matcher = RapidFuzzStringMatcher()
    template_history = InMemoryTemplateHistory()
    # Create the LLM-based mapping agent for ambiguous cases
    mapping_agent = LangChainMappingAgent()
    return MappingService(
        string_matcher=string_matcher,
        mapping_agent=mapping_agent,
        template_history=template_history,
    )


def create_mapping_service_port() -> MappingServicePort:
    """Create a MappingServicePort implementation.

    Returns:
        MappingServicePort adapter wrapping MappingService
    """
    service = create_mapping_service()
    return MappingServiceAdapter(service)


def create_adjust_service() -> AdjustService:
    """Create a configured AdjustService instance.

    Returns:
        AdjustService with all adapters wired up
    """
    overlap_detector = SimpleOverlapDetector()
    return AdjustService(overlap_detector=overlap_detector)


def create_adjust_service_port() -> AdjustServicePort:
    """Create an AdjustServicePort implementation.

    Returns:
        AdjustServicePort adapter wrapping AdjustService
    """
    service = create_adjust_service()
    return AdjustServiceAdapter(service)


def create_fill_service() -> FillService:
    """Create a configured FillService instance.

    Returns:
        FillService with all adapters wired up
    """
    pdf_reader = FillPdfReader()
    acroform_writer = PyMuPdfAcroFormAdapter()
    overlay_renderer = ReportlabOverlayAdapter()
    pdf_merger = PyMuPdfMergerAdapter()
    storage = FillStorageAdapter(base_path="/tmp/fill-artifacts")
    text_measure = ReportlabMeasureAdapter()
    return FillService(
        pdf_reader=pdf_reader,
        acroform_writer=acroform_writer,
        overlay_renderer=overlay_renderer,
        pdf_merger=pdf_merger,
        storage=storage,
        text_measure=text_measure,
    )


def create_fill_service_port() -> FillServicePort:
    """Create a FillServicePort implementation.

    Returns:
        FillServicePort adapter wrapping FillService
    """
    service = create_fill_service()
    return FillServiceAdapter(service)


def create_review_service() -> ReviewService:
    """Create a configured ReviewService instance.

    Returns:
        ReviewService with all adapters wired up
    """
    pdf_renderer = PyMuPdfRenderer()
    diff_generator = OpenCVDiffGenerator()
    issue_detector = RuleBasedIssueDetector()
    preview_storage = LocalPreviewStorage(base_path="/tmp/review-previews")
    return ReviewService(
        pdf_renderer=pdf_renderer,
        diff_generator=diff_generator,
        issue_detector=issue_detector,
        preview_storage=preview_storage,
    )


def create_review_service_port() -> ReviewServicePort:
    """Create a ReviewServicePort implementation.

    Returns:
        ReviewServicePort adapter wrapping ReviewService
    """
    service = create_review_service()
    return ReviewServiceAdapter(service)
