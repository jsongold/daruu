"""FastAPI application entry point for Orchestrator Service."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_config
from app.routes import jobs_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager."""
    # Startup
    get_config()
    # Add any startup logic here (e.g., initialize connections)

    yield

    # Shutdown
    # Add any cleanup logic here


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_config()

    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        description="Orchestrator service for Daru PDF pipeline execution and loop control",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(jobs_router, prefix=config.api_prefix)

    # Health check endpoints
    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Basic liveness check for container orchestration."""
        return {
            "status": "healthy",
            "version": config.app_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/health/ready")
    async def readiness() -> dict[str, Any]:
        """Readiness check with dependency status."""
        # Add dependency checks here (e.g., service connectivity)
        return {
            "status": "healthy",
            "version": config.app_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": [],
        }

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, Any]:
        """API root endpoint."""
        return {
            "name": config.app_name,
            "version": config.app_version,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app


# Create the application instance
app = create_app()
