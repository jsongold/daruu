"""Health check models."""

from typing import Literal

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    """Health status for a single component/dependency."""

    name: str = Field(..., description="Component name")
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Component health status"
    )
    latency_ms: float | None = Field(
        None, description="Response latency in milliseconds"
    )
    message: str | None = Field(None, description="Additional status message")

    model_config = {"frozen": True}


class HealthResponse(BaseModel):
    """Health check response for liveness probe."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall health status"
    )
    version: str = Field(..., description="Application version")
    timestamp: str = Field(..., description="ISO 8601 timestamp")

    model_config = {"frozen": True}


class ReadinessResponse(BaseModel):
    """Readiness check response with component details."""

    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ..., description="Overall readiness status"
    )
    version: str = Field(..., description="Application version")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    components: list[ComponentHealth] = Field(
        default_factory=list, description="Individual component health statuses"
    )

    model_config = {"frozen": True}
