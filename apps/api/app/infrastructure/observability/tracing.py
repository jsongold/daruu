"""OpenTelemetry tracing for pipeline stages.

This module provides distributed tracing capabilities for the daru-pdf pipeline.
Traces are propagated through the pipeline stages to enable end-to-end visibility.

The tracing is non-blocking and designed to have minimal performance impact.
If OpenTelemetry dependencies are not available, tracing operations become no-ops.

Pipeline Stages Traced:
- Ingest -> StructureLabelling -> Mapping -> Extract -> Adjust -> Fill -> Review

Usage:
    from app.infrastructure.observability.tracing import get_tracer, trace_stage

    tracer = get_tracer("orchestrator")
    with tracer.start_as_current_span("run_pipeline") as span:
        span.set_attribute("job_id", job_id)
        # ... pipeline execution

    # Decorator usage
    @trace_stage("ingest")
    async def execute_ingest(job: JobContext) -> StageResult:
        # ... ingest logic
"""

from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

# Type variable for generic function decorator
F = TypeVar("F", bound=Callable[..., Any])

# Module-level flag to track if tracing is available
_TRACING_AVAILABLE = False
_tracer_provider = None


def _check_tracing_available() -> bool:
    """Check if OpenTelemetry dependencies are available."""
    try:
        from opentelemetry import trace  # noqa: F401
        from opentelemetry.sdk.trace import TracerProvider  # noqa: F401

        return True
    except ImportError:
        return False


_TRACING_AVAILABLE = _check_tracing_available()


def init_tracing(
    service_name: str = "daru-pdf-api",
    endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> None:
    """Initialize OpenTelemetry tracing.

    Args:
        service_name: Name of the service for trace identification.
        endpoint: OTLP exporter endpoint (optional, uses console if not provided).
        sample_rate: Sampling rate (0.0 to 1.0). Default is 1.0 (trace everything).
    """
    global _tracer_provider

    if not _TRACING_AVAILABLE:
        return

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

    # Create resource with service info
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "0.1.0",
        }
    )

    # Create sampler based on sample rate
    sampler = TraceIdRatioBased(sample_rate)

    # Create and set tracer provider
    _tracer_provider = TracerProvider(resource=resource, sampler=sampler)

    # Add exporter based on configuration
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            exporter = OTLPSpanExporter(endpoint=endpoint)
            _tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            # OTLP exporter not available, skip
            pass
    # Note: ConsoleSpanExporter is intentionally NOT used by default
    # as it creates extremely verbose JSON output in logs.
    # Enable only when OTEL_TRACE_CONSOLE=1 is set for local debugging.

    trace.set_tracer_provider(_tracer_provider)


def shutdown_tracing() -> None:
    """Shutdown tracing and flush any pending spans."""
    global _tracer_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None


class NoOpSpan:
    """No-op span implementation when tracing is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        """No-op set attribute."""
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """No-op add event."""
        pass

    def set_status(self, status: Any) -> None:
        """No-op set status."""
        pass

    def record_exception(self, exception: Exception) -> None:
        """No-op record exception."""
        pass

    def end(self) -> None:
        """No-op end span."""
        pass

    def __enter__(self) -> "NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class NoOpTracer:
    """No-op tracer implementation when OpenTelemetry is not available."""

    def start_as_current_span(
        self,
        name: str,
        **kwargs: Any,
    ) -> NoOpSpan:
        """Return a no-op span context manager."""
        return NoOpSpan()

    @contextmanager
    def start_span(
        self,
        name: str,
        **kwargs: Any,
    ) -> Generator[NoOpSpan, None, None]:
        """Return a no-op span context manager."""
        yield NoOpSpan()


def get_tracer(name: str = "daru-pdf") -> Any:
    """Get a tracer instance for the given name.

    Args:
        name: Tracer name (typically module or component name).

    Returns:
        OpenTelemetry tracer if available, otherwise a no-op tracer.
    """
    if not _TRACING_AVAILABLE:
        return NoOpTracer()

    from opentelemetry import trace

    return trace.get_tracer(name)


def get_current_span() -> Any:
    """Get the current active span.

    Returns:
        Current span if tracing is available and a span is active, otherwise NoOpSpan.
    """
    if not _TRACING_AVAILABLE:
        return NoOpSpan()

    from opentelemetry import trace

    span = trace.get_current_span()
    if span is None:
        return NoOpSpan()
    return span


def set_span_attribute(key: str, value: Any) -> None:
    """Set an attribute on the current span.

    Args:
        key: Attribute key.
        value: Attribute value.
    """
    span = get_current_span()
    span.set_attribute(key, value)


def trace_stage(
    stage_name: str,
    extract_job_id: Callable[..., str | None] | None = None,
) -> Callable[[F], F]:
    """Decorator to trace a pipeline stage execution.

    Creates a span for the stage and automatically records:
    - Stage name
    - Job ID (if extract_job_id provided or job_id in kwargs)
    - Duration
    - Success/failure status
    - Exceptions

    Args:
        stage_name: Name of the pipeline stage (e.g., "ingest", "extract").
        extract_job_id: Optional function to extract job_id from arguments.

    Returns:
        Decorated function with tracing.

    Example:
        @trace_stage("extract")
        async def execute_extract(job: JobContext) -> StageResult:
            # job_id is automatically extracted from job.id
            ...

        @trace_stage("custom", extract_job_id=lambda x: x.get("id"))
        async def custom_handler(data: dict) -> Result:
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer("pipeline")
            span_name = f"pipeline.{stage_name}"

            # Extract job_id
            job_id = None
            if extract_job_id is not None:
                job_id = extract_job_id(*args, **kwargs)
            elif "job_id" in kwargs:
                job_id = kwargs["job_id"]
            elif args and hasattr(args[0], "id"):
                # First argument might be a job context
                job_id = getattr(args[0], "id", None)

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("pipeline.stage", stage_name)
                if job_id:
                    span.set_attribute("job.id", job_id)

                try:
                    result = await func(*args, **kwargs)

                    # Record success
                    span.set_attribute("pipeline.success", True)

                    # Extract result info if available
                    if hasattr(result, "success"):
                        span.set_attribute("result.success", result.success)
                    if hasattr(result, "issues"):
                        span.set_attribute("result.issues_count", len(result.issues))

                    return result
                except Exception as e:
                    span.set_attribute("pipeline.success", False)
                    span.record_exception(e)
                    if _TRACING_AVAILABLE:
                        from opentelemetry.trace import StatusCode

                        span.set_status(StatusCode.ERROR, str(e))
                    raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer("pipeline")
            span_name = f"pipeline.{stage_name}"

            # Extract job_id
            job_id = None
            if extract_job_id is not None:
                job_id = extract_job_id(*args, **kwargs)
            elif "job_id" in kwargs:
                job_id = kwargs["job_id"]
            elif args and hasattr(args[0], "id"):
                job_id = getattr(args[0], "id", None)

            with tracer.start_as_current_span(span_name) as span:
                span.set_attribute("pipeline.stage", stage_name)
                if job_id:
                    span.set_attribute("job.id", job_id)

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("pipeline.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("pipeline.success", False)
                    span.record_exception(e)
                    if _TRACING_AVAILABLE:
                        from opentelemetry.trace import StatusCode

                        span.set_status(StatusCode.ERROR, str(e))
                    raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


@contextmanager
def trace_operation(
    operation_name: str,
    job_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Context manager for tracing arbitrary operations.

    Args:
        operation_name: Name of the operation being traced.
        job_id: Optional job ID for correlation.
        attributes: Optional additional attributes to record.

    Yields:
        The span object for adding attributes during execution.

    Example:
        with trace_operation("validate_fields", job_id=job.id) as span:
            span.set_attribute("field_count", len(fields))
            # ... validation logic
    """
    tracer = get_tracer("daru-pdf")

    with tracer.start_as_current_span(operation_name) as span:
        if job_id:
            span.set_attribute("job.id", job_id)
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span
