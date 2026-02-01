"""Structured logging with correlation IDs for pipeline observability.

This module provides structured logging using structlog, with automatic
correlation ID (job_id) propagation for request tracing.

Features:
- Structured JSON logging for production (Google Cloud Logging compatible)
- Human-readable console output for development
- Automatic job_id correlation
- Integration with OpenTelemetry trace context
- Context variables for request-scoped data
- Severity field for GCP log levels

Usage:
    from app.infrastructure.observability.logging import get_logger

    # Get logger with job context
    logger = get_logger("orchestrator", job_id=job_id)
    logger.info("Pipeline started", stage="ingest", document_id=doc_id)

    # Output (JSON for production):
    # {"timestamp":"2024-01-15T10:30:00Z","severity":"INFO","message":"Pipeline started",
    #  "logger":"orchestrator","job_id":"abc-123","stage":"ingest","document_id":"doc-456",
    #  "trace_id":"abc123...","span_id":"def456..."}

    # Without job context
    logger = get_logger("startup")
    logger.info("Application started", version="0.1.0")
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variable for job_id propagation
_job_id_context: ContextVar[str | None] = ContextVar("job_id", default=None)

# Check if structlog is available
_STRUCTLOG_AVAILABLE = False

try:
    import structlog
    from structlog.types import EventDict, WrappedLogger

    _STRUCTLOG_AVAILABLE = True
except ImportError:
    pass

# Map Python log levels to Google Cloud Logging severity
_LEVEL_TO_SEVERITY = {
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
    "exception": "ERROR",
}


class LoggingConfig:
    """Configuration for logging setup.

    Attributes:
        json_format: If True, output JSON format (for production).
        log_level: Minimum log level to output.
        include_trace_id: Include OpenTelemetry trace ID if available.
        timestamp_format: Format for timestamps in output.
    """

    json_format: bool = True
    log_level: str = "INFO"
    include_trace_id: bool = True
    timestamp_format: str = "iso"

    def __init__(
        self,
        json_format: bool = True,
        log_level: str = "INFO",
        include_trace_id: bool = True,
    ) -> None:
        self.json_format = json_format
        self.log_level = log_level
        self.include_trace_id = include_trace_id


# Global config
_config = LoggingConfig()


def configure_logging(
    json_format: bool = True,
    log_level: str = "INFO",
    include_trace_id: bool = True,
) -> None:
    """Configure logging settings.

    Args:
        json_format: If True, output JSON format (recommended for production).
        log_level: Minimum log level ("DEBUG", "INFO", "WARNING", "ERROR").
        include_trace_id: Include OpenTelemetry trace ID in logs.
    """
    global _config
    _config = LoggingConfig(
        json_format=json_format,
        log_level=log_level,
        include_trace_id=include_trace_id,
    )


def _add_job_id(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor to add job_id from context."""
    job_id = _job_id_context.get()
    if job_id is not None:
        event_dict["job_id"] = job_id
    return event_dict


def _add_trace_id(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor to add OpenTelemetry trace ID."""
    if not _config.include_trace_id:
        return event_dict

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None:
            ctx = span.get_span_context()
            if ctx.is_valid:
                event_dict["trace_id"] = format(ctx.trace_id, "032x")
                event_dict["span_id"] = format(ctx.span_id, "016x")
    except ImportError:
        pass

    return event_dict


def _add_timestamp(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor to add ISO timestamp."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def _add_severity(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor to add GCP-compatible severity field.

    Maps Python log levels to Google Cloud Logging severity levels.
    Removes the redundant 'level' field.
    """
    # Get the log level from the event dict (added by add_log_level)
    level = event_dict.pop("level", "info")
    event_dict["severity"] = _LEVEL_TO_SEVERITY.get(level.lower(), "INFO")
    return event_dict


def _rename_event_to_message(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor to rename 'event' to 'message' for GCP compatibility."""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def _reorder_fields(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Reorder fields to put important ones first for readability.

    Desired order: timestamp, severity, message, logger, job_id, trace_id, span_id, ...rest
    """
    priority_keys = ["timestamp", "severity", "message", "logger", "job_id", "trace_id", "span_id"]
    ordered: dict[str, Any] = {}

    # Add priority keys first
    for key in priority_keys:
        if key in event_dict:
            ordered[key] = event_dict[key]

    # Add remaining keys
    for key, value in event_dict.items():
        if key not in priority_keys:
            ordered[key] = value

    return ordered


def init_logging() -> None:
    """Initialize structlog with configured processors.

    Call this once at application startup to configure the logging system.
    Configures:
    - JSON format for production (no ANSI codes, GCP-compatible)
    - Console format for development
    - Suppresses noisy third-party loggers
    - Disables pdfminer debug output
    """
    # Suppress pdfminer's verbose debug output (print statements)
    _suppress_pdfminer_debug()

    if not _STRUCTLOG_AVAILABLE:
        # Fall back to standard logging
        logging.basicConfig(
            level=getattr(logging, _config.log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stdout,
        )
        return

    # Suppress noisy third-party loggers
    _configure_third_party_loggers()

    # Build processor chain
    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_timestamp,
        _add_job_id,
        _add_trace_id,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if _config.json_format:
        # Production: Clean JSON output (no ANSI codes)
        processors = shared_processors + [
            _add_severity,
            _rename_event_to_message,
            _reorder_fields,
            structlog.processors.JSONRenderer(sort_keys=False),
        ]
    else:
        # Development: Human-readable console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to work with structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, _config.log_level),
        force=True,  # Override any existing config
    )


def _suppress_pdfminer_debug() -> None:
    """Suppress verbose debug output from PDF and multipart libraries.

    These libraries use print() statements for debug output which creates
    extremely verbose logs. This function disables debug modes.
    """
    import os
    import sys

    # Disable environment-based debug modes
    os.environ["PDFMINER_DEBUG"] = "0"
    os.environ["MULTIPART_DEBUG"] = "0"

    # Suppress pdfminer's internal debug flags
    try:
        import pdfminer.settings
        pdfminer.settings.STRICT = False
    except (ImportError, AttributeError):
        pass

    try:
        from pdfminer import psparser
        if hasattr(psparser, "STRICT"):
            psparser.STRICT = False
    except ImportError:
        pass

    # Suppress python-multipart debug output
    try:
        import multipart
        if hasattr(multipart, "multipart"):
            # Disable callbacks debug logging
            mp = multipart.multipart
            if hasattr(mp, "DEBUG"):
                mp.DEBUG = False
    except ImportError:
        pass

    # Monkey-patch to suppress verbose print statements from these libraries
    # by replacing print with a no-op for specific modules
    _suppress_module_prints()


def _suppress_module_prints() -> None:
    """Suppress print() statements from verbose libraries.

    Some libraries use print() directly for debug output instead of logging.
    This function patches the builtins.print function to filter out
    known verbose debug patterns.
    """
    import builtins

    _original_print = builtins.print

    # Patterns that indicate verbose debug output to suppress
    _suppress_patterns = (
        # pdfminer debug
        "nexttoken:",
        "add_results:",
        "nextobject:",
        "do_keyword:",
        "exec:",
        # python-multipart debug
        "Calling on_part",
        "Calling on_header",
        "Calling on_end",
        # PIL plugin imports
        "Importing ",
        "Image: failed to import",
        # OpenAI/HTTP client debug
        "Request options:",
        "Sending HTTP Request:",
        "HTTP Request:",
        "HTTP Response:",
        "Retrying request",
        "connect_tcp.started",
        "connect_tcp.complete",
        "send_request_headers",
        "send_request_body",
        "receive_response_headers",
        "receive_response_body",
        "close.started",
        "close.complete",
        # HTTP/2 header compression (hpack) debug
        "Adding",
        "Encoding",
        "Decoding",
        "Decoded",
        "Evicting",
        "Indexed",
        "sensitive:",
        "huffman:",
        "total consumed",
        # Supabase client warnings
        "Storage endpoint URL",
        "Initialized Supabase",
    )

    # Also suppress OpenTelemetry ConsoleSpanExporter output
    _suppress_otel_patterns = (
        '{"name":',  # Start of span JSON object
        '    "name":',
        '    "context":',
        '    "kind":',
        '    "parent_id":',
        '    "start_time":',
        '    "end_time":',
        '    "status":',
        '    "attributes":',
        '    "events":',
        '    "links":',
        '    "resource":',
        '"telemetry.sdk',
        '"service.name":',
        '"schema_url":',
        '        "trace_id":',
        '        "span_id":',
        '        "trace_state":',
        "SpanKind.INTERNAL",
        '"status_code":',
    )

    def _filtered_print(*args: Any, **kwargs: Any) -> None:
        """Print function that filters out verbose debug patterns."""
        if args:
            first_arg = str(args[0]).strip()
            # Check if this is a debug message to suppress
            for pattern in _suppress_patterns:
                if first_arg.startswith(pattern):
                    return  # Suppress this print
            # Check for OTEL span export patterns
            for pattern in _suppress_otel_patterns:
                if first_arg.startswith(pattern) or pattern in first_arg:
                    return  # Suppress OTEL JSON output
            # Also suppress single braces (JSON formatting)
            if first_arg in ('{', '}', '[', ']'):
                return
        _original_print(*args, **kwargs)

    builtins.print = _filtered_print


def _configure_third_party_loggers() -> None:
    """Configure third-party loggers to reduce noise.

    Suppresses verbose logging from:
    - OpenTelemetry SDK and exporters
    - urllib3 connection pool
    - httpx client
    - grpc internals
    - PDF parsing libraries (pdfminer, PyMuPDF)
    - PIL/Pillow image library
    - multipart form parsing
    """
    noisy_loggers = [
        # OpenTelemetry
        "opentelemetry",
        "opentelemetry.sdk",
        "opentelemetry.exporter",
        "opentelemetry.trace",
        "opentelemetry.metrics",
        # HTTP clients
        "urllib3",
        "urllib3.connectionpool",
        "httpx",
        "httpcore",
        # HTTP/2 header compression (extremely verbose)
        "hpack",
        "hpack.hpack",
        "hpack.table",
        "h2",
        "h2.connection",
        "h2.stream",
        "h11",
        # gRPC
        "grpc",
        "grpc._common",
        # Async
        "asyncio",
        # Uvicorn
        "uvicorn.error",
        "uvicorn.access",
        # PDF parsing - suppress verbose debug output
        "pdfminer",
        "pdfminer.pdfpage",
        "pdfminer.pdfparser",
        "pdfminer.pdfdocument",
        "pdfminer.pdfinterp",
        "pdfminer.converter",
        "pdfminer.cmapdb",
        "pdfminer.psparser",
        "pdfminer.layout",
        "fitz",  # PyMuPDF
        # Image processing
        "PIL",
        "PIL.Image",
        "PIL.PngImagePlugin",
        # Multipart form parsing
        "multipart",
        "multipart.multipart",
        "python_multipart",
        # OpenAI/LLM HTTP clients
        "openai",
        "openai._base_client",
        "openai._client",
        "openai.resources",
        "openai.types",
        "langchain",
        "langchain_core",
        "langchain_openai",
        "langgraph",
        # HTTP clients detailed
        "httpx._client",
        "httpcore._sync",
        "httpcore._async",
    ]

    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Completely silence extremely verbose loggers
    silent_loggers = [
        "pdfminer.psparser",
        "pdfminer.pdfinterp",
        "openai._base_client",  # Request/response debug
        "httpx",  # HTTP debug
        "httpcore",
        # HTTP/2 header compression - extremely noisy
        "hpack",
        "hpack.hpack",
        "hpack.table",
        "h2",
        "h11",
    ]
    for logger_name in silent_loggers:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


class SimpleLogger:
    """Simple logger fallback when structlog is not available.

    Provides the same interface as structlog bound loggers.
    """

    def __init__(self, name: str, **initial_context: Any) -> None:
        self._logger = logging.getLogger(name)
        self._context = initial_context

    def _format_message(self, event: str, **kwargs: Any) -> str:
        """Format a log message with context."""
        all_context = {**self._context, **kwargs}
        if all_context:
            context_str = " ".join(f"{k}={v}" for k, v in all_context.items())
            return f"{event} - {context_str}"
        return event

    def bind(self, **kwargs: Any) -> "SimpleLogger":
        """Create a new logger with additional context."""
        new_context = {**self._context, **kwargs}
        new_logger = SimpleLogger(self._logger.name)
        new_logger._context = new_context
        return new_logger

    def unbind(self, *keys: str) -> "SimpleLogger":
        """Create a new logger without specified context keys."""
        new_context = {k: v for k, v in self._context.items() if k not in keys}
        new_logger = SimpleLogger(self._logger.name)
        new_logger._context = new_context
        return new_logger

    def debug(self, event: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self._logger.debug(self._format_message(event, **kwargs))

    def info(self, event: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._logger.info(self._format_message(event, **kwargs))

    def warning(self, event: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._logger.warning(self._format_message(event, **kwargs))

    def error(self, event: str, **kwargs: Any) -> None:
        """Log an error message."""
        self._logger.error(self._format_message(event, **kwargs))

    def exception(self, event: str, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        self._logger.exception(self._format_message(event, **kwargs))


def get_logger(
    name: str,
    job_id: str | None = None,
    **initial_context: Any,
) -> Any:
    """Get a logger instance with optional job context.

    Args:
        name: Logger name (typically module or component name).
        job_id: Optional job ID for correlation.
        **initial_context: Additional context to bind to the logger.

    Returns:
        Bound structlog logger if available, otherwise SimpleLogger.

    Example:
        logger = get_logger("orchestrator", job_id="abc-123")
        logger.info("Pipeline started", stage="ingest")

        # Add more context
        stage_logger = logger.bind(stage="extract")
        stage_logger.info("Extracting fields", field_count=5)
    """
    if job_id is not None:
        # Set job_id in context variable for processor
        _job_id_context.set(job_id)
        initial_context["job_id"] = job_id

    if _STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name).bind(**initial_context)

    return SimpleLogger(name, **initial_context)


def set_job_context(job_id: str) -> None:
    """Set the job ID in the current context.

    This is useful for setting the job context at the start of a request
    or pipeline execution, so all subsequent log calls include the job_id.

    Args:
        job_id: The job ID to set in context.
    """
    _job_id_context.set(job_id)


def clear_job_context() -> None:
    """Clear the job ID from the current context."""
    _job_id_context.set(None)


def get_job_context() -> str | None:
    """Get the current job ID from context.

    Returns:
        The job ID if set, otherwise None.
    """
    return _job_id_context.get()


class LoggerContextManager:
    """Context manager for scoped job logging context.

    Automatically sets and clears job context on enter/exit.

    Example:
        with LoggerContextManager(job_id="abc-123"):
            logger = get_logger("stage")
            logger.info("Processing")  # Automatically includes job_id
    """

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id
        self._previous_job_id: str | None = None

    def __enter__(self) -> "LoggerContextManager":
        self._previous_job_id = _job_id_context.get()
        _job_id_context.set(self._job_id)
        return self

    def __exit__(self, *args: Any) -> None:
        _job_id_context.set(self._previous_job_id)


def with_job_context(job_id: str) -> LoggerContextManager:
    """Create a context manager for scoped job context.

    Args:
        job_id: The job ID to set in context.

    Returns:
        LoggerContextManager instance.

    Example:
        with with_job_context(job_id):
            logger = get_logger("pipeline")
            logger.info("Stage started", stage="ingest")
    """
    return LoggerContextManager(job_id)
