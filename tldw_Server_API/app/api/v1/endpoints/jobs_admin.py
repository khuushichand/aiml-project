from __future__ import annotations

from typing import List, Optional
import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin
from tldw_Server_API.app.api.v1.API_Deps.Audit_DB_Deps import get_audit_service_for_user
from tldw_Server_API.app.core.Audit.unified_audit_service import AuditEventType, AuditContext
from tldw_Server_API.app.core.Jobs.manager import JobManager

router = APIRouter()


def _is_truthy(v: Optional[str]) -> bool:
    return str(v or "").lower() in {"1", "true", "yes", "y", "on"}


def _enforce_domain_scope(user: dict, domain: Optional[str]) -> None:
    """Optional domain-scoped RBAC enforcement.

    Enabled when JOBS_DOMAIN_SCOPED_RBAC=true. If JOBS_REQUIRE_DOMAIN_FILTER=true,
    a domain filter must be provided. If an allowlist is configured for the user
    via JOBS_DOMAIN_ALLOWLIST_<USER_ID>, the requested domain must be in it.
    Single-user admin mode bypasses these checks.
    """
    try:
        if not _is_truthy(os.getenv("JOBS_DOMAIN_SCOPED_RBAC")):
            return
        # Single-user admin bypass, unless forced for tests
        if not _is_truthy(os.getenv("JOBS_RBAC_FORCE")):
            try:
                from tldw_Server_API.app.core.AuthNZ.settings import is_single_user_mode
                if is_single_user_mode():
                    return
            except Exception:
                pass
        uid = str(user.get("id") or "")
        if _is_truthy(os.getenv("JOBS_REQUIRE_DOMAIN_FILTER")) and not (domain and domain.strip()):
            raise HTTPException(status_code=403, detail="Domain filter is required for this operation")
        allow = os.getenv(f"JOBS_DOMAIN_ALLOWLIST_{uid}", "").strip()
        if allow:
            allowed = {d.strip() for d in allow.split(",") if d.strip()}
            if domain and domain.strip():
                if domain not in allowed:
                    raise HTTPException(status_code=403, detail=f"Not allowed for domain {domain}")
            else:
                # denying broad queries when allowlist is present and domain missing
                raise HTTPException(status_code=403, detail="Domain filter required for allowlisted admin")
    except HTTPException:
        raise
    except Exception:
        # Fail-open on unexpected RBAC errors to avoid locking out real admins
        return


class PruneRequest(BaseModel):
    statuses: List[str] = Field(default_factory=lambda: ["completed", "failed", "cancelled"], description="Statuses to prune")
    older_than_days: int = Field(ge=1, le=3650, default=30, description="Delete jobs older than N days")
    # Optional scope filters
    domain: Optional[str] = Field(default=None, description="Limit prune to a specific domain")
    queue: Optional[str] = Field(default=None, description="Limit prune to a specific queue")
    job_type: Optional[str] = Field(default=None, description="Limit prune to a specific job type")
    dry_run: bool = Field(default=False, description="When true, return count only without deleting")
    detail_top_k: int = Field(default=0, ge=0, le=100, description="When dry_run is true, optionally compute top-K groups by count")

    @validator("statuses", each_item=True)
    def _norm_status(cls, v: str) -> str:
        v = str(v or "").strip().lower()
        allowed = {"queued", "processing", "completed", "failed", "cancelled"}
        if v not in allowed:
            raise ValueError(f"Unsupported status: {v}")
        return v

    @validator("domain", "queue", "job_type", pre=True, always=True)
    def _trim_optional(cls, v: Optional[str]) -> Optional[str]:
        s = str(v or "").strip()
        return s or None

    class Config:
        schema_extra = {
            "example": {
                "statuses": ["completed", "failed"],
                "older_than_days": 30,
                "domain": "chatbooks",
                "queue": "default",
                "job_type": "export",
                "dry_run": True,
            }
        }


class PruneResponse(BaseModel):
    deleted: int


@router.post("/jobs/prune", response_model=PruneResponse)
async def prune_jobs_endpoint(
    req: PruneRequest,
    user=Depends(require_admin),
    audit_service=Depends(get_audit_service_for_user),
) -> PruneResponse:
    """Delete jobs matching statuses and older than threshold.

    Requires authentication. Use cautiously.
    """
    try:
        _enforce_domain_scope(user, req.domain)
        jm = JobManager()
        deleted = jm.prune_jobs(
            statuses=req.statuses,
            older_than_days=req.older_than_days,
            domain=req.domain,
            queue=req.queue,
            job_type=req.job_type,
            dry_run=req.dry_run,
            detail_top_k=req.detail_top_k,
        )
        # Optionally refresh gauges for a fully-scoped prune (avoid heavy recompute by default)
        try:
            if not req.dry_run and req.domain and req.queue and req.job_type and str(
                os.getenv("JOBS_UPDATE_GAUGES_ON_PRUNE", "")
            ).lower() in {"1","true","yes","y","on"}:
                jm._update_gauges(domain=req.domain, queue=req.queue, job_type=req.job_type)
        except Exception:
            pass
        # Best-effort audit logging for admin prune action
        try:
            ctx = AuditContext(
                user_id=str(user.get("id")),
                endpoint="/api/v1/jobs/prune",
                method="POST",
            )
            await audit_service.log_event(
                event_type=AuditEventType.DATA_DELETE,
                context=ctx,
                resource_type="jobs",
                action="prune",
                result="success",
                result_count=deleted,
                metadata={
                    "statuses": req.statuses,
                    "older_than_days": req.older_than_days,
                    "domain": req.domain,
                    "queue": req.queue,
                    "job_type": req.job_type,
                    "dry_run": req.dry_run,
                },
            )
        except Exception:
            # Never fail prune due to audit logging issues
            pass
        return PruneResponse(deleted=deleted)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prune failed: {e}")


class TTLSweepRequest(BaseModel):
    age_seconds: Optional[int] = Field(default=None, ge=1, description="Cancel/fail queued jobs older than this many seconds (created_at)")
    runtime_seconds: Optional[int] = Field(default=None, ge=1, description="Cancel/fail processing jobs running longer than this many seconds")
    action: str = Field(default="cancel", pattern="^(cancel|fail)$", description="Action to apply to matching jobs")
    domain: Optional[str] = Field(default=None)
    queue: Optional[str] = Field(default=None)
    job_type: Optional[str] = Field(default=None)

    class Config:
        schema_extra = {
            "example": {
                "age_seconds": 86400,
                "runtime_seconds": 7200,
                "action": "cancel",
                "domain": "chatbooks",
                "queue": "default",
                "job_type": None,
            }
        }


class TTLSweepResponse(BaseModel):
    affected: int


@router.post("/jobs/ttl/sweep", response_model=TTLSweepResponse)
async def ttl_sweep_endpoint(
    req: TTLSweepRequest,
    user=Depends(require_admin),
) -> TTLSweepResponse:
    try:
        _enforce_domain_scope(user, req.domain)
        jm = JobManager()
        affected = jm.apply_ttl_policies(
            age_seconds=req.age_seconds,
            runtime_seconds=req.runtime_seconds,
            action=req.action,
            domain=req.domain,
            queue=req.queue,
            job_type=req.job_type,
        )
        return TTLSweepResponse(affected=int(affected))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTL sweep failed: {e}")


class QueueStatsResponse(BaseModel):
    domain: str
    queue: str
    job_type: str
    queued: int
    scheduled: int
    processing: int

    class Config:
        schema_extra = {
            "example": {
                "domain": "chatbooks",
                "queue": "default",
                "job_type": "export",
                "queued": 3,
                "scheduled": 2,
                "processing": 1,
            }
        }


@router.get("/jobs/stats", response_model=list[QueueStatsResponse])
async def get_jobs_stats(
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    job_type: Optional[str] = None,
    user=Depends(require_admin),
):
    """Aggregate counts grouped by domain/queue/job_type for the WebUI."""
    try:
        _enforce_domain_scope(user, domain)
        jm = JobManager()
        stats = jm.get_queue_stats(domain=domain, queue=queue, job_type=job_type)
        return [QueueStatsResponse(**s) for s in stats]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats failed: {e}")


class JobItem(BaseModel):
    id: int
    uuid: Optional[str] = None
    domain: str
    queue: str
    job_type: str
    status: str
    priority: Optional[int] = None
    retry_count: Optional[int] = None
    max_retries: Optional[int] = None
    available_at: Optional[str] = None
    created_at: Optional[str] = None
    acquired_at: Optional[str] = None
    started_at: Optional[str] = None
    leased_until: Optional[str] = None
    completed_at: Optional[str] = None


@router.get("/jobs/list", response_model=list[JobItem])
async def list_jobs_endpoint(
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    status: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 100,
    user=Depends(require_admin),
):
    try:
        _enforce_domain_scope(user, domain)
        jm = JobManager()
        rows = jm.list_jobs(domain=domain, queue=queue, status=status, owner_user_id=owner_user_id, job_type=job_type, limit=limit)
        items: list[JobItem] = []
        for r in rows:
            # Keep minimal fields for listing
            items.append(
                JobItem(
                    id=int(r.get("id")),
                    uuid=r.get("uuid"),
                    domain=str(r.get("domain")),
                    queue=str(r.get("queue")),
                    job_type=str(r.get("job_type")),
                    status=str(r.get("status")),
                    priority=r.get("priority"),
                    retry_count=r.get("retry_count"),
                    max_retries=r.get("max_retries"),
                    available_at=str(r.get("available_at")) if r.get("available_at") is not None else None,
                    created_at=str(r.get("created_at")) if r.get("created_at") is not None else None,
                    acquired_at=str(r.get("acquired_at")) if r.get("acquired_at") is not None else None,
                    started_at=str(r.get("started_at")) if r.get("started_at") is not None else None,
                    leased_until=str(r.get("leased_until")) if r.get("leased_until") is not None else None,
                    completed_at=str(r.get("completed_at")) if r.get("completed_at") is not None else None,
                )
            )
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List failed: {e}")


class StaleGroup(BaseModel):
    domain: str
    queue: str
    count: int


@router.get("/jobs/stale", response_model=list[StaleGroup])
async def stale_processing_endpoint(
    domain: Optional[str] = None,
    queue: Optional[str] = None,
    user=Depends(require_admin),
):
    try:
        _enforce_domain_scope(user, domain)
        jm = JobManager()
        conn = jm._connect()
        out: list[StaleGroup] = []
        try:
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    where = ["status='processing'", "(leased_until IS NULL OR leased_until <= NOW())"]
                    params: list = []
                    if domain:
                        where.append("domain = %s")
                        params.append(domain)
                    if queue:
                        where.append("queue = %s")
                        params.append(queue)
                    cur.execute(
                        f"SELECT domain, queue, COUNT(*) FROM jobs WHERE {' AND '.join(where)} GROUP BY domain, queue",
                        tuple(params),
                    )
                    for (d, q, c) in cur.fetchall():
                        out.append(StaleGroup(domain=str(d), queue=str(q), count=int(c)))
            else:
                where = ["status='processing'", "(leased_until IS NULL OR leased_until <= DATETIME('now'))"]
                params2: list = []
                if domain:
                    where.append("domain = ?")
                    params2.append(domain)
                if queue:
                    where.append("queue = ?")
                    params2.append(queue)
                sql = f"SELECT domain, queue, COUNT(*) FROM jobs WHERE {' AND '.join(where)} GROUP BY domain, queue"
                for (d, q, c) in conn.execute(sql, tuple(params2)).fetchall():
                    out.append(StaleGroup(domain=str(d), queue=str(q), count=int(c)))
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stale groups failed: {e}")
