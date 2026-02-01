"""Jobs router for the Orchestrator service."""

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs() -> dict[str, Any]:
    """List all jobs."""
    return {"jobs": [], "total": 0}


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    """Get a specific job by ID."""
    return {"job_id": job_id, "status": "not_found", "message": "Job not found"}
