"""Prometheus metrics for pipeline monitoring.

This module provides Prometheus metrics for monitoring the daru-pdf pipeline.
Metrics are exposed via an HTTP endpoint for scraping by Prometheus.

Metrics provided:
- Agent invocation count and latency (per agent type)
- Pipeline stage duration (per stage)
- Job completion rates (success/failure)
- Active jobs gauge
- Error counts by type

The metrics are designed to be non-blocking and have minimal performance impact.
If prometheus_client is not available, metric operations become no-ops.

Usage:
    from app.infrastructure.observability.metrics import metrics

    # Increment counter
    metrics.agent_invocation_count.labels(agent="extract", status="success").inc()

    # Observe histogram
    with metrics.pipeline_stage_duration.labels(stage="ingest").time():
        # ... stage execution

    # Or manually:
    start = time.time()
    # ... stage execution
    metrics.pipeline_stage_duration.labels(stage="ingest").observe(time.time() - start)

    # Update gauge
    metrics.active_jobs.inc()
    metrics.active_jobs.dec()

Endpoint:
    Use get_metrics_handler() to create a FastAPI route handler for /metrics.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from time import time
from typing import Any, Callable, Generator

# Check if prometheus_client is available
_METRICS_AVAILABLE = False

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _METRICS_AVAILABLE = True
except ImportError:
    pass


class NoOpMetric:
    """No-op metric implementation when prometheus_client is not available."""

    def labels(self, **kwargs: Any) -> "NoOpMetric":
        """Return self for method chaining."""
        return self

    def inc(self, amount: float = 1) -> None:
        """No-op increment."""
        pass

    def dec(self, amount: float = 1) -> None:
        """No-op decrement."""
        pass

    def set(self, value: float) -> None:
        """No-op set."""
        pass

    def observe(self, amount: float) -> None:
        """No-op observe."""
        pass

    @contextmanager
    def time(self) -> Generator[None, None, None]:
        """No-op timer context manager."""
        yield


@dataclass(frozen=True)
class MetricsConfig:
    """Configuration for metrics.

    Attributes:
        namespace: Prefix for all metric names (default: daru_pdf).
        buckets: Histogram bucket boundaries for latency metrics.
    """

    namespace: str = "daru_pdf"
    buckets: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class PipelineMetrics:
    """Container for all pipeline metrics.

    This class provides centralized access to all Prometheus metrics used
    for monitoring the daru-pdf pipeline.

    Metrics:
        agent_invocation_count: Counter for agent invocations by agent type and status.
        agent_invocation_latency: Histogram for agent invocation latency.
        pipeline_stage_duration: Histogram for pipeline stage duration.
        job_completion_total: Counter for job completions by status.
        active_jobs: Gauge for currently active jobs.
        error_count: Counter for errors by type.
    """

    def __init__(
        self,
        config: MetricsConfig | None = None,
        registry: Any | None = None,
    ) -> None:
        """Initialize metrics.

        Args:
            config: Metrics configuration.
            registry: Prometheus registry (uses default if not provided).
        """
        self._config = config or MetricsConfig()
        self._registry = registry

        if _METRICS_AVAILABLE:
            self._init_prometheus_metrics()
        else:
            self._init_noop_metrics()

    def _init_prometheus_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        ns = self._config.namespace
        registry_kwargs = {"registry": self._registry} if self._registry else {}

        # Agent invocation metrics
        self.agent_invocation_count = Counter(
            f"{ns}_agent_invocation_total",
            "Total number of agent invocations",
            ["agent", "status"],
            **registry_kwargs,
        )

        self.agent_invocation_latency = Histogram(
            f"{ns}_agent_invocation_latency_seconds",
            "Agent invocation latency in seconds",
            ["agent"],
            buckets=self._config.buckets,
            **registry_kwargs,
        )

        # Pipeline stage metrics
        self.pipeline_stage_duration = Histogram(
            f"{ns}_pipeline_stage_duration_seconds",
            "Pipeline stage duration in seconds",
            ["stage"],
            buckets=self._config.buckets,
            **registry_kwargs,
        )

        self.pipeline_stage_count = Counter(
            f"{ns}_pipeline_stage_total",
            "Total number of pipeline stage executions",
            ["stage", "status"],
            **registry_kwargs,
        )

        # Job completion metrics
        self.job_completion_total = Counter(
            f"{ns}_job_completion_total",
            "Total number of job completions",
            ["status"],
            **registry_kwargs,
        )

        self.job_duration = Histogram(
            f"{ns}_job_duration_seconds",
            "Total job duration from start to completion",
            ["mode"],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0),
            **registry_kwargs,
        )

        # Active jobs gauge
        self.active_jobs = Gauge(
            f"{ns}_active_jobs",
            "Number of currently active jobs",
            **registry_kwargs,
        )

        # Error metrics
        self.error_count = Counter(
            f"{ns}_error_total",
            "Total number of errors",
            ["type", "stage"],
            **registry_kwargs,
        )

        # Retry metrics
        self.retry_count = Counter(
            f"{ns}_retry_total",
            "Total number of retries",
            ["stage", "reason"],
            **registry_kwargs,
        )

        # Issue metrics
        self.issue_count = Counter(
            f"{ns}_issue_total",
            "Total number of issues detected",
            ["type", "severity"],
            **registry_kwargs,
        )

    def _init_noop_metrics(self) -> None:
        """Initialize no-op metrics when prometheus_client is not available."""
        noop = NoOpMetric()

        self.agent_invocation_count = noop
        self.agent_invocation_latency = noop
        self.pipeline_stage_duration = noop
        self.pipeline_stage_count = noop
        self.job_completion_total = noop
        self.job_duration = noop
        self.active_jobs = noop
        self.error_count = noop
        self.retry_count = noop
        self.issue_count = noop

    def record_agent_invocation(
        self,
        agent: str,
        status: str,
        duration: float,
    ) -> None:
        """Record an agent invocation.

        Args:
            agent: Name of the agent (e.g., "extract", "mapping").
            status: Invocation status ("success" or "failure").
            duration: Duration of the invocation in seconds.
        """
        self.agent_invocation_count.labels(agent=agent, status=status).inc()
        self.agent_invocation_latency.labels(agent=agent).observe(duration)

    def record_stage_execution(
        self,
        stage: str,
        status: str,
        duration: float,
    ) -> None:
        """Record a pipeline stage execution.

        Args:
            stage: Name of the stage (e.g., "ingest", "extract").
            status: Execution status ("success" or "failure").
            duration: Duration of the stage in seconds.
        """
        self.pipeline_stage_count.labels(stage=stage, status=status).inc()
        self.pipeline_stage_duration.labels(stage=stage).observe(duration)

    def record_job_completion(
        self,
        status: str,
        mode: str,
        duration: float,
    ) -> None:
        """Record a job completion.

        Args:
            status: Completion status ("done", "failed", "blocked").
            mode: Job mode ("transfer" or "scratch").
            duration: Total job duration in seconds.
        """
        self.job_completion_total.labels(status=status).inc()
        self.job_duration.labels(mode=mode).observe(duration)

    def record_error(self, error_type: str, stage: str) -> None:
        """Record an error occurrence.

        Args:
            error_type: Type of error (e.g., "validation", "extraction").
            stage: Stage where the error occurred.
        """
        self.error_count.labels(type=error_type, stage=stage).inc()

    def record_retry(self, stage: str, reason: str) -> None:
        """Record a retry occurrence.

        Args:
            stage: Stage being retried.
            reason: Reason for the retry (e.g., "layout_issue", "mapping_ambiguous").
        """
        self.retry_count.labels(stage=stage, reason=reason).inc()

    def record_issue(self, issue_type: str, severity: str) -> None:
        """Record an issue detection.

        Args:
            issue_type: Type of issue (e.g., "low_confidence", "layout_issue").
            severity: Issue severity (e.g., "critical", "high", "warning").
        """
        self.issue_count.labels(type=issue_type, severity=severity).inc()

    @contextmanager
    def time_stage(self, stage: str) -> Generator[None, None, None]:
        """Context manager to time a pipeline stage.

        Args:
            stage: Name of the stage being timed.

        Yields:
            None. Duration is recorded on exit.

        Example:
            with metrics.time_stage("extract"):
                # ... extraction logic
        """
        start = time()
        status = "success"
        try:
            yield
        except Exception:
            status = "failure"
            raise
        finally:
            duration = time() - start
            self.record_stage_execution(stage, status, duration)

    @contextmanager
    def time_agent(self, agent: str) -> Generator[None, None, None]:
        """Context manager to time an agent invocation.

        Args:
            agent: Name of the agent being timed.

        Yields:
            None. Duration is recorded on exit.

        Example:
            with metrics.time_agent("extract"):
                # ... agent execution
        """
        start = time()
        status = "success"
        try:
            yield
        except Exception:
            status = "failure"
            raise
        finally:
            duration = time() - start
            self.record_agent_invocation(agent, status, duration)


# Global metrics instance
metrics = PipelineMetrics()


def init_metrics(
    config: MetricsConfig | None = None,
    registry: Any | None = None,
) -> PipelineMetrics:
    """Initialize or reinitialize the global metrics instance.

    Args:
        config: Metrics configuration.
        registry: Prometheus registry to use.

    Returns:
        The initialized PipelineMetrics instance.
    """
    global metrics
    metrics = PipelineMetrics(config=config, registry=registry)
    return metrics


def get_metrics_handler() -> Callable[[], tuple[bytes, str]]:
    """Get a handler function for serving metrics.

    Returns a function that generates Prometheus metrics output.
    This can be used with FastAPI's Response class.

    Returns:
        Function that returns (content, content_type) tuple.

    Example:
        from fastapi import Response
        from app.infrastructure.observability.metrics import get_metrics_handler

        handler = get_metrics_handler()

        @app.get("/metrics")
        async def prometheus_metrics():
            content, content_type = handler()
            return Response(content=content, media_type=content_type)
    """

    def handler() -> tuple[bytes, str]:
        if not _METRICS_AVAILABLE:
            return b"# Prometheus client not available\n", "text/plain"

        content = generate_latest()
        return content, CONTENT_TYPE_LATEST

    return handler


def create_metrics_route() -> Any:
    """Create a FastAPI route for metrics endpoint.

    Returns:
        FastAPI Response with Prometheus metrics.

    Note:
        Import this function only when setting up routes,
        as it requires FastAPI to be installed.
    """
    try:
        from fastapi import Response
    except ImportError:
        raise ImportError("FastAPI is required for create_metrics_route")

    handler = get_metrics_handler()

    async def metrics_endpoint() -> Response:
        content, content_type = handler()
        return Response(content=content, media_type=content_type)

    return metrics_endpoint
