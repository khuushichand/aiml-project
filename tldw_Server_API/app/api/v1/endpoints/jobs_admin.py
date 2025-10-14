from __future__ import annotations

from typing import List, Optional
import os
from fastapi import APIRouter, Depends, HTTPException, Request
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
    request: Request,
    user=Depends(require_admin),
    audit_service=Depends(get_audit_service_for_user),
) -> PruneResponse:
    """Delete jobs matching statuses and older than threshold.

    Requires authentication. Use cautiously.
    """
    try:
        # Pre-parse raw JSON to enforce RBAC before model validation to avoid 422s
        try:
            raw_body = await request.json()
        except Exception:
            raw_body = {}
        # Enforce domain-scoped RBAC (403) even if request body is incomplete
        _enforce_domain_scope(user, (raw_body or {}).get("domain"))
        # Now validate the request body
        req = PruneRequest(**(raw_body or {}))
        # Confirm header for destructive action (skip when dry_run)
        if not bool((raw_body or {}).get("dry_run")):
            hdr = str(request.headers.get("x-confirm", "")).lower()
            if hdr not in {"1", "true", "yes", "y", "on"}:
                raise HTTPException(status_code=400, detail="Confirmation required: set X-Confirm: true")

        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
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
    except HTTPException:
        # Preserve intended HTTP errors (e.g., RBAC 403)
        raise
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
    request: Request,
    user=Depends(require_admin),
) -> TTLSweepResponse:
    try:
        _enforce_domain_scope(user, req.domain)
        # Confirm header for destructive action
        hdr = str(request.headers.get("x-confirm", "")).lower()
        if hdr not in {"1", "true", "yes", "y", "on"}:
            raise HTTPException(status_code=400, detail="Confirmation required: set X-Confirm: true")
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
        affected = jm.apply_ttl_policies(
            age_seconds=req.age_seconds,
            runtime_seconds=req.runtime_seconds,
            action=req.action,
            domain=req.domain,
            queue=req.queue,
            job_type=req.job_type,
        )
        return TTLSweepResponse(affected=int(affected))
    except HTTPException:
        raise
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
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
        stats = jm.get_queue_stats(domain=domain, queue=queue, job_type=job_type)
        return [QueueStatsResponse(**s) for s in stats]
    except HTTPException:
        raise
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
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
    user=Depends(require_admin),
):
    try:
        _enforce_domain_scope(user, domain)
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
        rows = jm.list_jobs(
            domain=domain,
            queue=queue,
            status=status,
            owner_user_id=owner_user_id,
            job_type=job_type,
            limit=limit,
            sort_by=(sort_by or "created_at"),
            sort_order=(sort_order or "desc"),
        )
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
        # Use explicit backend/db_url selection for consistency with other admin endpoints
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
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


class BatchCancelRequest(BaseModel):
    domain: str
    queue: Optional[str] = None
    job_type: Optional[str] = None
    dry_run: bool = False


class BatchCancelResponse(BaseModel):
    affected: int


@router.post("/jobs/batch/cancel", response_model=BatchCancelResponse)
async def batch_cancel_endpoint(
    req: BatchCancelRequest,
    request: Request,
    user=Depends(require_admin),
):
    try:
        _enforce_domain_scope(user, req.domain)
        # Require confirm header unless dry_run
        if not req.dry_run:
            hdr = str(request.headers.get("x-confirm", "")).lower()
            if hdr not in {"1", "true", "yes", "y", "on"}:
                raise HTTPException(status_code=400, detail="Confirmation required: set X-Confirm: true")
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
        conn = jm._connect()
        try:
            where = ["domain = %s"] if jm.backend == "postgres" else ["domain = ?"]
            params: list = [req.domain]
            if req.queue:
                where.append("queue = %s" if jm.backend == "postgres" else "queue = ?")
                params.append(req.queue)
            if req.job_type:
                where.append("job_type = %s" if jm.backend == "postgres" else "job_type = ?")
                params.append(req.job_type)
            # Allow cancelling queued or processing (processing will be terminally cancelled)
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    if req.dry_run:
                        cur.execute(
                            f"SELECT COUNT(*) FROM jobs WHERE ({' AND '.join(where)}) AND status IN ('queued','processing')",
                            tuple(params),
                        )
                        c = cur.fetchone()
                        return BatchCancelResponse(affected=int(c[0] if c else 0))
                    # queued immediate cancel
                    cur.execute(
                        f"UPDATE jobs SET status='cancelled', cancelled_at = NOW(), cancellation_reason='batch_cancel' WHERE ({' AND '.join(where)}) AND status = 'queued'",
                        tuple(params),
                    )
                    affected = cur.rowcount or 0
                    # processing terminal cancel
                    cur.execute(
                        f"UPDATE jobs SET status='cancelled', cancelled_at = NOW(), cancellation_reason='batch_cancel', leased_until = NULL WHERE ({' AND '.join(where)}) AND status = 'processing'",
                        tuple(params),
                    )
                    affected += cur.rowcount or 0
                    return BatchCancelResponse(affected=int(affected))
            else:
                if req.dry_run:
                    cur = conn.execute(
                        f"SELECT COUNT(*) FROM jobs WHERE ({' AND '.join(where)}) AND status IN ('queued','processing')",
                        tuple(params),
                    )
                    r = cur.fetchone()
                    return BatchCancelResponse(affected=int(r[0] if r else 0))
                conn.execute(
                    f"UPDATE jobs SET status='cancelled', cancelled_at = DATETIME('now'), cancellation_reason='batch_cancel' WHERE ({' AND '.join(where)}) AND status = 'queued'",
                    tuple(params),
                )
                affected = conn.total_changes or 0
                conn.execute(
                    f"UPDATE jobs SET status='cancelled', cancelled_at = DATETIME('now'), cancellation_reason='batch_cancel', leased_until = NULL WHERE ({' AND '.join(where)}) AND status = 'processing'",
                    tuple(params),
                )
                affected += conn.total_changes or 0
                return BatchCancelResponse(affected=int(affected))
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch cancel failed: {e}")


class BatchRescheduleRequest(BaseModel):
    domain: str
    queue: Optional[str] = None
    job_type: Optional[str] = None
    delay_seconds: int = Field(ge=0, default=0)
    dry_run: bool = False


class BatchRescheduleResponse(BaseModel):
    affected: int


@router.post("/jobs/batch/reschedule", response_model=BatchRescheduleResponse)
async def batch_reschedule_endpoint(
    req: BatchRescheduleRequest,
    request: Request,
    user=Depends(require_admin),
):
    try:
        _enforce_domain_scope(user, req.domain)
        if not req.dry_run:
            hdr = str(request.headers.get("x-confirm", "")).lower()
            if hdr not in {"1", "true", "yes", "y", "on"}:
                raise HTTPException(status_code=400, detail="Confirmation required: set X-Confirm: true")
        db_url = os.getenv("JOBS_DB_URL")
        backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
        jm = JobManager(backend=backend, db_url=db_url)
        conn = jm._connect()
        try:
            where = ["domain = %s", "status = 'queued'"] if jm.backend == "postgres" else ["domain = ?", "status = 'queued'"]
            params: list = [req.domain]
            if req.queue:
                where.append("queue = %s" if jm.backend == "postgres" else "queue = ?")
                params.append(req.queue)
            if req.job_type:
                where.append("job_type = %s" if jm.backend == "postgres" else "job_type = ?")
                params.append(req.job_type)
            if jm.backend == "postgres":
                with jm._pg_cursor(conn) as cur:
                    if req.dry_run:
                        cur.execute(
                            f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where)}",
                            tuple(params),
                        )
                        r = cur.fetchone()
                        return BatchRescheduleResponse(affected=int(r[0] if r else 0))
                    cur.execute(
                        f"UPDATE jobs SET available_at = NOW() + (%s || ' seconds')::interval WHERE {' AND '.join(where)}",
                        tuple([int(req.delay_seconds)] + params),
                    )
                    return BatchRescheduleResponse(affected=int(cur.rowcount or 0))
            else:
                if req.dry_run:
                    cur = conn.execute(
                        f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where)}",
                        tuple(params),
                    )
                    r = cur.fetchone()
                    return BatchRescheduleResponse(affected=int(r[0] if r else 0))
                conn.execute(
                    f"UPDATE jobs SET available_at = DATETIME('now', ?) WHERE {' AND '.join(where)}",
                    tuple([f"+{int(req.delay_seconds)} seconds"] + params),
                )
                return BatchRescheduleResponse(affected=int(conn.total_changes or 0))
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch reschedule failed: {e}")
