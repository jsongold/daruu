"""Orchestrator services for pipeline execution and control.

This module provides the core orchestration logic for the document processing pipeline:

- Orchestrator: Main coordinator for pipeline execution (UseCase layer)
- DecisionEngine: Logic for branching and loop control
- PipelineExecutor: Executes individual pipeline stages
- ServiceClient: Client for calling external Services (mock for MVP)

Service vs Agent Architecture:
- Orchestrator calls Services (not Agents directly)
- Services may internally use Agents (FieldLabellingAgent, ValueExtractionAgent, MappingAgent)
- Services may internally use other Services (OcrService, PdfWriteService, etc.)
- Agents are implemented as Ports (interfaces) for easy replacement

Clean Architecture Layers:
- domain/: Pure domain logic (termination rules, improvement calculation)
- application/: Use cases and port interfaces
- infrastructure/: HTTP clients, Redis adapters

Usage:
    from app.orchestrator import Orchestrator, OrchestratorConfig

    config = OrchestratorConfig(
        max_iterations=10,
        confidence_threshold=0.8,
        max_steps_per_run=100,
        min_improvement_rate=0.1,
        require_user_approval=False,
    )
    orchestrator = Orchestrator(config=config)

    # Run a job until blocked
    job = await orchestrator.run(job_id, RunMode.UNTIL_BLOCKED)
"""

# Core orchestration components
from app.orchestrator.decision_engine import DecisionEngine
from app.orchestrator.orchestrator import Orchestrator
from app.orchestrator.pipeline_executor import PipelineExecutor
from app.orchestrator.service_client import ServiceClient

# Domain layer
from app.orchestrator.domain import (
    TerminationAction,
    TerminationCondition,
    calculate_improvement_rate,
    calculate_issue_score,
    check_termination,
)

# Application layer - ports
from app.orchestrator.application.ports import ServiceGateway, TaskQueue

# Application layer - use cases
from app.orchestrator.application.use_cases import (
    DecideNextUseCase,
    RunPipelineUseCase,
)

# Infrastructure layer
from app.orchestrator.infrastructure import HttpServiceClient, RedisJobStore

__all__ = [
    # Core
    "DecisionEngine",
    "Orchestrator",
    "PipelineExecutor",
    "ServiceClient",
    # Domain
    "TerminationAction",
    "TerminationCondition",
    "calculate_improvement_rate",
    "calculate_issue_score",
    "check_termination",
    # Application - ports
    "ServiceGateway",
    "TaskQueue",
    # Application - use cases
    "DecideNextUseCase",
    "RunPipelineUseCase",
    # Infrastructure
    "HttpServiceClient",
    "RedisJobStore",
]
