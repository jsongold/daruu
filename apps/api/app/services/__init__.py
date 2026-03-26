"""Business logic services.

This module provides:
- Services: Deterministic business logic (DocumentService, JobService, etc.)
- Pipeline Services: Full pipeline implementation

Service vs Agent Architecture:
- Services handle deterministic business logic
- Agents handle non-deterministic LLM reasoning (see app.agents)
- Orchestrator coordinates pipeline (see app.orchestrator)
- Services may internally use Agents

Pipeline Services:
- IngestService: PDF normalization and metadata extraction
- StructureLabellingService: Structure detection and field labelling
- MappingService: Source↔Target field mapping
- ExtractService: Value extraction with OCR and LLM
- AdjustService: Coordinate correction for layout issues
- FillService: PDF filling (AcroForm/overlay)
- ReviewService: Quality inspection and issue detection

NOTE: Orchestrator is now independent and should be imported from app.orchestrator:
    from app.orchestrator import Orchestrator, DecisionEngine, PipelineExecutor, ServiceClient

NOTE: Agents should be imported from app.agents:
    from app.agents.structure_labelling import LangChainFieldLabellingAgent
    from app.agents.extract import LangChainValueExtractionAgent
    from app.agents.mapping import LangChainMappingAgent

IMPORTANT: To avoid circular imports, import services directly from their modules:
    from app.services.extract import ExtractService
    from app.services.ingest import IngestService
    etc.
"""

# Only import services that don't have circular dependency issues
from app.services.document_service import DocumentService


def __getattr__(name: str):
    """Lazy import of services to avoid circular imports.

    This allows `from app.services import ExtractService` to work
    while deferring the actual import until the attribute is accessed.
    """
    if name == "AdjustService":
        from app.services.adjust import AdjustService

        return AdjustService
    elif name == "ExtractService":
        from app.services.extract import ExtractService

        return ExtractService
    elif name == "FillService":
        from app.services.fill import FillService

        return FillService
    elif name == "IngestService":
        from app.services.ingest import IngestService

        return IngestService
    elif name == "MappingService":
        from app.services.mapping import MappingService

        return MappingService
    elif name == "ReviewService":
        from app.services.review import ReviewService

        return ReviewService
    elif name == "StructureLabellingService":
        from app.services.structure_labelling import StructureLabellingService

        return StructureLabellingService
    elif name == "JobService":
        from app.services.job_service import JobService

        return JobService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Core services
    "DocumentService",
    "JobService",
    # Pipeline services
    "IngestService",
    "StructureLabellingService",
    "MappingService",
    "ExtractService",
    "AdjustService",
    "FillService",
    "ReviewService",
]
