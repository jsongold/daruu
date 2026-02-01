"""Observability infrastructure for the daru-pdf API.

This module provides tracing, metrics, and structured logging for pipeline stages.

Components:
- tracing: OpenTelemetry tracing with span context propagation
- metrics: Prometheus metrics for agent invocations, pipeline stages, and job completion
- logging: Structured logging with correlation IDs (job_id based)

Usage:
    from app.infrastructure.observability import (
        get_tracer,
        trace_stage,
        metrics,
        get_logger,
    )

    # Tracing
    tracer = get_tracer("orchestrator")
    with tracer.start_as_current_span("run_pipeline") as span:
        span.set_attribute("job_id", job_id)
        # ... pipeline execution

    # Metrics
    metrics.agent_invocation_count.labels(agent="extract", status="success").inc()
    metrics.pipeline_stage_duration.labels(stage="ingest").observe(duration)

    # Logging
    logger = get_logger("orchestrator", job_id=job_id)
    logger.info("Pipeline started", stage="ingest")
"""

from app.infrastructure.observability.tracing import (
    get_tracer,
    trace_stage,
    init_tracing,
    shutdown_tracing,
    get_current_span,
    set_span_attribute,
)
from app.infrastructure.observability.metrics import (
    metrics,
    init_metrics,
    get_metrics_handler,
)
from app.infrastructure.observability.logging import (
    get_logger,
    init_logging,
    configure_logging,
    with_job_context,
)

__all__ = [
    # Tracing
    "get_tracer",
    "trace_stage",
    "init_tracing",
    "shutdown_tracing",
    "get_current_span",
    "set_span_attribute",
    # Metrics
    "metrics",
    "init_metrics",
    "get_metrics_handler",
    # Logging
    "get_logger",
    "init_logging",
    "configure_logging",
    "with_job_context",
]
