"""Orchestrator service configuration."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class OrchestratorConfig(BaseSettings):
    """Configuration for the orchestrator service.

    Settings are loaded from environment variables with ORCHESTRATOR_ prefix.
    """

    # Application
    app_name: str = Field(default="Daru PDF Orchestrator")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)

    # API
    api_prefix: str = Field(default="/api/v1")
    allowed_origins: list[str] = Field(default=["*"])

    # Default thresholds
    default_confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Default confidence threshold"
    )
    default_mapping_confidence_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Default mapping confidence threshold"
    )
    default_improvement_rate_threshold: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Minimum improvement rate per iteration"
    )

    # Loop control
    default_max_iterations: int = Field(
        default=10, ge=1, le=100, description="Default maximum iterations"
    )
    max_steps_per_run: int = Field(
        default=50, ge=1, le=200, description="Maximum steps in a single run"
    )

    # Service endpoints (for calling other services)
    ingest_service_url: str = Field(
        default="http://localhost:8001", description="Ingest service URL"
    )
    structure_service_url: str = Field(
        default="http://localhost:8002", description="Structure service URL"
    )
    extraction_service_url: str = Field(
        default="http://localhost:8003", description="Extraction service URL"
    )
    fill_service_url: str = Field(default="http://localhost:8004", description="Fill service URL")

    # HTTP client settings
    service_timeout_seconds: float = Field(
        default=30.0, ge=1.0, description="Timeout for service calls"
    )
    service_retry_attempts: int = Field(
        default=3, ge=0, le=10, description="Number of retry attempts for failed service calls"
    )

    model_config = {
        "env_prefix": "ORCHESTRATOR_",
        "env_file": ".env",
        "case_sensitive": False,
    }


@lru_cache
def get_config() -> OrchestratorConfig:
    """Get cached configuration instance.

    Returns:
        OrchestratorConfig instance with settings from environment
    """
    return OrchestratorConfig()
