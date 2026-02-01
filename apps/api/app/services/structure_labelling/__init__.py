"""Structure/Labelling Service for document structure extraction and field linking.

This service orchestrates:
1. Deterministic structure detection (boxes, tables, text regions)
2. LLM-based label-to-position linking via FieldLabellingAgent

Service vs Agent distinction:
- StructureLabellingService: Deterministic orchestration
- FieldLabellingAgent: LLM reasoning for label-to-bbox linking (REQUIRED)

Single Writer Responsibility:
- Creates/updates Field objects (name, type, bbox, anchor)
- Creates Evidence(kind=llm_linking) for audit trail

Usage:
    from app.services.structure_labelling import (
        StructureLabellingService,
        OpenCVStructureDetector,
        LocalPageImageLoader,
    )
    from app.agents.structure_labelling import LangChainFieldLabellingAgent

    agent = LangChainFieldLabellingAgent()
    detector = OpenCVStructureDetector()
    loader = LocalPageImageLoader("/data/artifacts")

    service = StructureLabellingService(agent, detector, loader)
    result = await service.process(request)
"""

from app.services.structure_labelling.adapters import (
    LocalPageImageLoader,
    MockPageImageLoader,
    MockStructureDetector,
    OpenCVStructureDetector,
)
from app.services.structure_labelling.ports import (
    FieldLabellingAgentPort,
    PageImageLoaderPort,
    StructureDetectorPort,
)
from app.services.structure_labelling.service import StructureLabellingService

# NOTE: Agent implementations are imported from app.agents, not here
# This avoids circular imports. Import agents as:
#   from app.agents.structure_labelling import LangChainFieldLabellingAgent

__all__ = [
    # Service
    "StructureLabellingService",
    # Ports (interfaces)
    "FieldLabellingAgentPort",
    "PageImageLoaderPort",
    "StructureDetectorPort",
    # Adapter implementations
    "LocalPageImageLoader",
    "MockPageImageLoader",
    "MockStructureDetector",
    "OpenCVStructureDetector",
]
