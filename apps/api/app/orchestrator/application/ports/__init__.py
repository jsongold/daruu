"""Port interfaces for the orchestrator application layer.

Ports define the contracts for external dependencies. Implementations
are provided in the infrastructure layer. This separation allows:

1. Easy testing with mock implementations
2. Swapping implementations without changing business logic
3. Clear dependency boundaries
"""

from app.orchestrator.application.ports.service_gateway import ServiceGateway
from app.orchestrator.application.ports.task_queue import TaskQueue
from app.orchestrator.application.ports.pipeline_services import (
    AdjustServicePort,
    ExtractServicePort,
    FillServicePort,
    IngestServicePort,
    MappingServicePort,
    ReviewServicePort,
    StructureLabellingServicePort,
)

__all__ = [
    # Gateway ports
    "ServiceGateway",
    "TaskQueue",
    # Pipeline service ports
    "AdjustServicePort",
    "ExtractServicePort",
    "FillServicePort",
    "IngestServicePort",
    "MappingServicePort",
    "ReviewServicePort",
    "StructureLabellingServicePort",
]
