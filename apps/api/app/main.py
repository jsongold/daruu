"""FastAPI application entry point."""

import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.models import ErrorDetail, ErrorResponse
from app.routes import (
    adjust_router,
    analyze_router,
    auth_router,
    autofill_pipeline_router,
    corrections_router,
    conversations_router,
    data_sources_router,
    documents_router,
    edits_router,
    extract_router,
    extract_service_router,
    fill_router,
    fill_service_router,
    health_router,
    ingest_router,
    jobs_router,
    mapping_router,
    prompt_attempts_router,
    review_router,
    review_service_router,
    rules_router,
    structure_labelling_router,
    templates_router,
    vision_autofill_router,
)
from app.infrastructure.observability import (
    init_tracing,
    init_logging,
    shutdown_tracing,
    get_metrics_handler,
    get_logger,
    configure_logging,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    # Initialize observability
    configure_logging(
        json_format=not settings.debug,
        log_level="DEBUG" if settings.debug else "INFO",
    )
    init_logging()

    # Initialize tracing (optional, based on environment)
    otlp_endpoint = getattr(settings, "otlp_endpoint", None)
    init_tracing(
        service_name="daru-pdf-api",
        endpoint=otlp_endpoint,
        sample_rate=1.0 if settings.debug else 0.1,
    )

    logger = get_logger("main")
    logger.info(
        "Application started",
        version=settings.app_version,
        debug=settings.debug,
    )

    yield

    # Shutdown
    logger.info("Application shutting down")
    shutdown_tracing()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    openapi_description = """
## Overview

Daru PDF API provides endpoints for automated document processing, including:

- **Document Upload**: Upload PDF or image files for processing
- **Job Management**: Create and manage document processing jobs
- **Field Extraction**: Extract field values from documents using OCR and AI
- **Field Mapping**: Map fields between source and target documents
- **Review & Editing**: Review extracted values and make manual corrections
- **PDF Generation**: Generate filled PDF documents

## Job Modes

Jobs can run in two modes:

- **transfer**: Copy data from a source document to a target document
- **scratch**: Fill a target document from scratch (no source)

## Run Modes

When running a job, you can control execution:

- **step**: Execute a single step and return
- **until_blocked**: Run until user input is needed
- **until_done**: Run until completion (may auto-answer questions)

## Authentication

Authentication is optional for MVP. When enabled, use Bearer token in the Authorization header.

## Error Handling

All errors follow a consistent format with `success: false` and an `error` object containing:
- `code`: Machine-readable error code
- `message`: Human-readable description
- `field`: (optional) Field that caused the error
- `trace_id`: (optional) For debugging 500 errors
"""

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=openapi_description,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "auth",
                "description": "Authentication endpoints (optional for MVP)",
            },
            {
                "name": "documents",
                "description": "Document upload and retrieval operations",
            },
            {
                "name": "jobs",
                "description": "Job creation, execution, and management",
            },
            {
                "name": "extract",
                "description": "Field extraction from documents",
            },
            {
                "name": "fill",
                "description": "PDF form filling operations",
            },
            {
                "name": "review",
                "description": "Review, activity, and evidence operations",
            },
            {
                "name": "analyze",
                "description": "Document analysis operations",
            },
            {
                "name": "ingest",
                "description": "Document ingestion and preprocessing",
            },
            {
                "name": "mapping",
                "description": "Field mapping between documents",
            },
            {
                "name": "adjust",
                "description": "Field position and rendering adjustments",
            },
            {
                "name": "structure_labelling",
                "description": "Document structure and labelling operations",
            },
            {
                "name": "health",
                "description": "Health check and readiness probes",
            },
            {
                "name": "conversations",
                "description": "Agent Chat UI - conversation and message management (v2 API)",
            },
            {
                "name": "data-sources",
                "description": "Data sources for AI form filling (v2 API)",
            },
            {
                "name": "templates",
                "description": "Template management and matching (v2 API)",
            },
            {
                "name": "edits",
                "description": "Field editing and undo/redo operations (v2 API)",
            },
            {
                "name": "vision-autofill",
                "description": "AI-powered form autofill using data sources (v1 API)",
            },
            {
                "name": "autofill-pipeline",
                "description": "To-Be autofill pipeline: FormContextBuilder -> FillPlanner -> FormRenderer",
            },
            {
                "name": "rules",
                "description": "Rule snippet management and semantic search (v1 API)",
            },
            {
                "name": "prompt-attempts",
                "description": "Prompt tuning history for vision autofill (v1 API)",
            },
        ],
        contact={
            "name": "Daru PDF Team",
        },
        license_info={
            "name": "MIT",
        },
        servers=[
            {"url": "http://localhost:8000", "description": "Local development"},
            {"url": "https://api.daru-pdf.io", "description": "Production"},
        ],
    )

    # Latency profiling middleware — logs request timing to api.log
    # and adds Server-Timing header (visible in browser DevTools)
    class LatencyProfileMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start = time.perf_counter()
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            path = request.url.path
            method = request.method
            code = response.status_code

            # Add Server-Timing header (shows in browser DevTools > Network > Timing)
            response.headers["Server-Timing"] = f"total;dur={elapsed_ms:.1f}"

            import logging
            logging.getLogger("latency").info(
                f"{method} {path} -> {code} | {elapsed_ms:.0f}ms"
            )
            return response

    app.add_middleware(LatencyProfileMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.allowed_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Include routers with API prefix
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(documents_router, prefix=settings.api_prefix)
    app.include_router(jobs_router, prefix=settings.api_prefix)
    # New PRD-specified endpoints
    app.include_router(adjust_router, prefix=settings.api_prefix)
    app.include_router(analyze_router, prefix=settings.api_prefix)
    app.include_router(extract_router, prefix=settings.api_prefix)
    app.include_router(extract_service_router, prefix=settings.api_prefix)
    app.include_router(fill_router, prefix=settings.api_prefix)
    app.include_router(fill_service_router, prefix=settings.api_prefix)
    app.include_router(ingest_router, prefix=settings.api_prefix)
    app.include_router(mapping_router, prefix=settings.api_prefix)
    app.include_router(review_router, prefix=settings.api_prefix)
    app.include_router(review_service_router, prefix=settings.api_prefix)
    app.include_router(structure_labelling_router, prefix=settings.api_prefix)

    # Health check endpoints (at root level for k8s probes)
    app.include_router(health_router)

    # Agent Chat UI v2 API (has its own /api/v2 prefix)
    app.include_router(conversations_router)

    # Data Sources v2 API (nested under conversations)
    app.include_router(data_sources_router)

    # Template System v2 API (has its own /api/v2 prefix)
    app.include_router(templates_router)

    # Edit System v2 API (has its own /api/v2 prefix)
    app.include_router(edits_router)

    # Vision Autofill API (v1)
    app.include_router(vision_autofill_router, prefix=settings.api_prefix)

    # Autofill Pipeline API (To-Be architecture)
    app.include_router(autofill_pipeline_router, prefix=settings.api_prefix)

    # Corrections API (user correction tracking)
    app.include_router(corrections_router, prefix=settings.api_prefix)

    # Rules API (rule snippet management and search)
    app.include_router(rules_router, prefix=settings.api_prefix)

    # Prompt Attempts API (prompt tuning feature)
    app.include_router(prompt_attempts_router, prefix=settings.api_prefix)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, Any]:
        """API root endpoint."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    # Prometheus metrics endpoint
    metrics_handler = get_metrics_handler()

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        """Prometheus metrics endpoint for scraping."""
        content, content_type = metrics_handler()
        return Response(content=content, media_type=content_type)

    return app


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle request validation errors (400)."""
    errors = exc.errors()
    first_error = errors[0] if errors else {"msg": "Validation error", "loc": []}

    field = ".".join(str(loc) for loc in first_error.get("loc", [])) or None
    message = str(first_error.get("msg", "Validation error"))

    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message=message,
            field=field,
        ),
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_response.model_dump(),
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    """Handle HTTP exceptions."""
    error_code = _get_error_code(exc.status_code)

    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=error_code,
            message=str(exc.detail),
        ),
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(),
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions (500)."""
    trace_id = str(uuid4())

    # Log the full traceback (would use proper logging in production)
    settings = get_settings()
    if settings.debug:
        traceback.print_exc()

    error_response = ErrorResponse(
        success=False,
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="An internal error occurred. Please try again later.",
            trace_id=trace_id,
        ),
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(),
    )


def _get_error_code(status_code: int) -> str:
    """Map HTTP status code to error code."""
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        500: "INTERNAL_ERROR",
    }
    return code_map.get(status_code, "ERROR")


# Create the application instance
app = create_app()
