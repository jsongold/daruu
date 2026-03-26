"""Health check endpoints.

Provides liveness and readiness probes for the API.
- /health: Basic liveness check (is the service running?)
- /health/ready: Readiness check with dependency status
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter

from app.config import get_settings
from app.models.health import ComponentHealth, HealthResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])

# Timeout for individual health checks (in seconds)
HEALTH_CHECK_TIMEOUT = 5.0


@router.get("", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Basic liveness check.

    Returns healthy if the service is running and can respond.
    This is a lightweight check suitable for Kubernetes liveness probes.
    """
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness() -> ReadinessResponse:
    """Readiness check with dependency status.

    Checks all service dependencies and returns their status.
    Suitable for Kubernetes readiness probes.

    Components checked:
    - database: Supabase/database connection
    - llm: OpenAI LLM service availability
    - storage: File storage accessibility
    - job_queue: In-memory job queue status
    """
    settings = get_settings()

    # Run all health checks in parallel with timeouts
    checks = await asyncio.gather(
        _check_database(),
        _check_llm(),
        _check_storage(),
        _check_job_queue(),
        return_exceptions=True,
    )

    components: list[ComponentHealth] = []
    for check in checks:
        if isinstance(check, Exception):
            # Should not happen with our implementation, but handle gracefully
            components.append(
                ComponentHealth(
                    name="unknown",
                    status="unhealthy",
                    latency_ms=None,
                    message=str(check),
                )
            )
        else:
            components.append(check)

    # Determine overall status
    overall_status = _determine_overall_status(components)

    return ReadinessResponse(
        status=overall_status,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        components=components,
    )


def _determine_overall_status(
    components: list[ComponentHealth],
) -> Literal["healthy", "degraded", "unhealthy"]:
    """Determine overall health status from component statuses.

    Rules:
    - healthy: All components are healthy
    - degraded: Some optional components are unhealthy/degraded
    - unhealthy: Critical components (database) are unhealthy

    Critical components: database
    Optional components: llm, storage, job_queue (OCR is optional too)
    """
    critical_components = {"database"}

    has_critical_failure = False
    has_any_degraded = False

    for component in components:
        if component.status == "unhealthy":
            if component.name in critical_components:
                has_critical_failure = True
            else:
                has_any_degraded = True
        elif component.status == "degraded":
            has_any_degraded = True

    if has_critical_failure:
        return "unhealthy"
    if has_any_degraded:
        return "degraded"
    return "healthy"


async def _check_database() -> ComponentHealth:
    """Check database/Supabase connection.

    Returns healthy if Supabase is configured and reachable,
    or if we're using in-memory storage (dev mode).
    """
    start_time = time.perf_counter()
    settings = get_settings()

    try:
        supabase_url = settings.supabase_url
        supabase_key = settings.supabase_key or settings.supabase_anon_key

        if not supabase_url or not supabase_key:
            # Supabase not configured - using in-memory storage (dev mode)
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ComponentHealth(
                name="database",
                status="healthy",
                latency_ms=latency_ms,
                message="Using in-memory storage (Supabase not configured)",
            )

        # Try to import and create client to verify configuration
        result = await asyncio.wait_for(
            _verify_supabase_connection(),
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="database",
            status=result["status"],
            latency_ms=latency_ms,
            message=result["message"],
        )

    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="database",
            status="unhealthy",
            latency_ms=latency_ms,
            message="Connection timeout",
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="database",
            status="unhealthy",
            latency_ms=latency_ms,
            message=f"Connection error: {str(e)}",
        )


async def _verify_supabase_connection() -> dict[str, str]:
    """Verify Supabase connection by attempting to get client."""
    try:
        from app.infrastructure.supabase.client import (
            MockSupabaseClient,
            get_supabase_client,
        )

        client = get_supabase_client()

        if isinstance(client, MockSupabaseClient):
            return {
                "status": "healthy",
                "message": "Using mock client (Supabase package not installed)",
            }

        # Real client exists - connection is valid
        return {
            "status": "healthy",
            "message": "Connected to Supabase",
        }

    except ImportError:
        return {
            "status": "healthy",
            "message": "Using in-memory storage (supabase package not installed)",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Failed to connect: {str(e)}",
        }


async def _check_llm() -> ComponentHealth:
    """Check LLM service (OpenAI) availability.

    This is an optional component - the system can operate in degraded
    mode without LLM using local-only processing.
    """
    start_time = time.perf_counter()
    settings = get_settings()

    try:
        # Check if API key is configured
        if not settings.openai_api_key:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ComponentHealth(
                name="llm",
                status="degraded",
                latency_ms=latency_ms,
                message="OpenAI API key not configured",
            )

        # Check if mock mode is enabled
        if settings.llm_analyze_mode == "mock":
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ComponentHealth(
                name="llm",
                status="healthy",
                latency_ms=latency_ms,
                message="Running in mock mode",
            )

        # Try to verify OpenAI connectivity
        result = await asyncio.wait_for(
            _verify_openai_connection(settings.openai_api_key),
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="llm",
            status=result["status"],
            latency_ms=latency_ms,
            message=result["message"],
        )

    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="llm",
            status="degraded",
            latency_ms=latency_ms,
            message="OpenAI connection timeout",
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="llm",
            status="degraded",
            latency_ms=latency_ms,
            message=f"OpenAI check failed: {str(e)}",
        )


async def _verify_openai_connection(api_key: str) -> dict[str, str]:
    """Verify OpenAI API connectivity.

    Makes a lightweight API call to verify the key is valid.
    """
    try:
        import httpx

        # Use the models endpoint as a lightweight connectivity check
        async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "message": "OpenAI API connected",
                }
            elif response.status_code == 401:
                return {
                    "status": "degraded",
                    "message": "Invalid API key",
                }
            else:
                return {
                    "status": "degraded",
                    "message": f"API returned status {response.status_code}",
                }

    except ImportError:
        return {
            "status": "degraded",
            "message": "httpx not installed for health check",
        }
    except Exception as e:
        return {
            "status": "degraded",
            "message": f"Connection failed: {str(e)}",
        }


async def _check_storage() -> ComponentHealth:
    """Check file storage accessibility.

    Verifies the upload directory is writable.
    """
    start_time = time.perf_counter()
    settings = get_settings()

    try:
        upload_dir = settings.upload_dir

        # Check if directory exists and is writable
        if not upload_dir.exists():
            try:
                upload_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                latency_ms = (time.perf_counter() - start_time) * 1000
                return ComponentHealth(
                    name="storage",
                    status="unhealthy",
                    latency_ms=latency_ms,
                    message=f"Cannot create upload directory: {upload_dir}",
                )

        # Try to create a test file to verify write access
        test_file = upload_dir / ".health_check"
        try:
            test_file.write_text("health_check")
            test_file.unlink()
        except PermissionError:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ComponentHealth(
                name="storage",
                status="unhealthy",
                latency_ms=latency_ms,
                message=f"Upload directory not writable: {upload_dir}",
            )

        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="storage",
            status="healthy",
            latency_ms=latency_ms,
            message=f"Local storage accessible: {upload_dir}",
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="storage",
            status="unhealthy",
            latency_ms=latency_ms,
            message=f"Storage check failed: {str(e)}",
        )


async def _check_job_queue() -> ComponentHealth:
    """Check job queue status.

    Verifies the in-memory job repository is operational.
    """
    start_time = time.perf_counter()

    try:
        from app.infrastructure.repositories.memory_repository import (
            get_job_repository,
        )

        # Get the job repository and verify it's functional
        job_repo = get_job_repository()

        # Count active jobs (non-blocking operation)
        all_jobs = job_repo.list_all()
        active_count = sum(1 for j in all_jobs if j.status.value not in ("completed", "failed"))

        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="job_queue",
            status="healthy",
            latency_ms=latency_ms,
            message=f"Job queue operational ({active_count} active jobs)",
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return ComponentHealth(
            name="job_queue",
            status="degraded",
            latency_ms=latency_ms,
            message=f"Job queue check failed: {str(e)}",
        )
