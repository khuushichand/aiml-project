from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import get_current_user
from tldw_Server_API.app.core.Jobs.manager import JobManager

router = APIRouter()


class PruneRequest(BaseModel):
    statuses: List[str] = Field(default_factory=lambda: ["completed", "failed", "cancelled"], description="Statuses to prune")
    older_than_days: int = Field(ge=1, le=3650, default=30, description="Delete jobs older than N days")

    @validator("statuses", each_item=True)
    def _norm_status(cls, v: str) -> str:
        v = str(v or "").strip().lower()
        allowed = {"queued", "processing", "completed", "failed", "cancelled"}
        if v not in allowed:
            raise ValueError(f"Unsupported status: {v}")
        return v


class PruneResponse(BaseModel):
    deleted: int


@router.post("/jobs/prune", response_model=PruneResponse)
async def prune_jobs_endpoint(req: PruneRequest, user=Depends(get_current_user)) -> PruneResponse:
    """Delete jobs matching statuses and older than threshold.

    Requires authentication. Use cautiously.
    """
    try:
        jm = JobManager()
        deleted = jm.prune_jobs(statuses=req.statuses, older_than_days=req.older_than_days)
        return PruneResponse(deleted=deleted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prune failed: {e}")


class QueueStatsResponse(BaseModel):
    domain: str
    queue: str
    job_type: str
    queued: int
    processing: int


@router.get("/jobs/stats", response_model=list[QueueStatsResponse])
async def get_jobs_stats(
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    job_type: Optional[str] = None,
    user=Depends(get_current_user),
):
    """Aggregate counts grouped by domain/queue/job_type for the WebUI."""
    try:
        jm = JobManager()
        stats = jm.get_queue_stats(domain=domain, queue=queue, job_type=job_type)
        return [QueueStatsResponse(**s) for s in stats]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {e}")
