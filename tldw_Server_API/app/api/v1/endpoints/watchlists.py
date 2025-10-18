from __future__ import annotations

"""
Watchlists API (sources, groups/tags, jobs, runs)

Implements minimal CRUD and semantics per PRD:
- Tag name→id mapping (accept names, resolve/create internally, return names)
- Bulk sources endpoint at /watchlists/sources/bulk

Scraping and scheduling are stubbed; runs are created on trigger.
"""

from typing import Any, Dict, List, Optional
import json

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.Watchlists_DB_Deps import get_watchlists_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.schemas.watchlists_schemas import (
    Source, SourceCreateRequest, SourceUpdateRequest, SourcesListResponse, SourcesBulkCreateRequest,
    Group, GroupCreateRequest, GroupUpdateRequest, GroupsListResponse,
    Tag, TagsListResponse,
    Job, JobCreateRequest, JobUpdateRequest, JobsListResponse,
    Run, RunsListResponse,
)


router = APIRouter(prefix="/watchlists", tags=["watchlists"])


# ---- Helpers ----
def _normalize_tz(tz: Optional[str]) -> str:
    # Accept PRD-style 'UTC+8' and 'UTC-5' and map to IANA Etc/GMT offsets
    if not tz or tz.upper() == "UTC":
        return "UTC"
    t = tz.strip().upper()
    if t.startswith("UTC+") or t.startswith("UTC-"):
        try:
            sign = 1 if t[3] == "+" else -1
            hours = int(t[4:])
            # Etc/GMT sign is inverted: GMT-8 equals UTC+8
            etc_offset = -sign * hours
            return f"Etc/GMT{('+' if etc_offset>0 else '')}{etc_offset}" if etc_offset != 0 else "Etc/GMT"
        except Exception:
            return "UTC"
    return tz


def _compute_next_run(cron: Optional[str], timezone: Optional[str]) -> Optional[str]:
    if not cron:
        return None
    try:
        from apscheduler.triggers.cron import CronTrigger
        tz = _normalize_tz(timezone) or "UTC"
        trigger = CronTrigger.from_crontab(cron, timezone=tz)
        from datetime import datetime
        now = datetime.now(trigger.timezone)
        nxt = trigger.get_next_fire_time(None, now)
        return nxt.isoformat() if nxt else None
    except Exception:
        return None


# --------------------
# Sources
# --------------------
@router.post("/sources", response_model=Source, summary="Create a source")
async def create_source(
    payload: SourceCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        row = db.create_source(
            name=payload.name,
            url=str(payload.url),
            source_type=str(payload.source_type),
            active=payload.active,
            settings_json=(json.dumps(payload.settings) if payload.settings else None),
            tags=payload.tags or [],
            group_ids=payload.group_ids or [],
        )
    except Exception as e:
        logger.error(f"create_source failed: {e}")
        raise HTTPException(status_code=400, detail="source_create_failed")
    return Source(
        id=row.id,
        name=row.name,
        url=row.url,
        source_type=row.source_type,  # type: ignore[assignment]
        active=bool(row.active),
        tags=row.tags,
        settings=(json.loads(row.settings_json) if row.settings_json else None),
        last_scraped_at=row.last_scraped_at,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/sources", response_model=SourcesListResponse, summary="List sources")
async def list_sources(
    q: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None, description="Filter by tag names (AND semantics)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_sources(q=q, tag_names=tags, limit=limit, offset=offset)
    items: List[Source] = []
    for r in rows:
        items.append(
            Source(
                id=r.id,
                name=r.name,
                url=r.url,
                source_type=r.source_type,  # type: ignore[assignment]
                active=bool(r.active),
                tags=r.tags,
                settings=(json.loads(r.settings_json) if r.settings_json else None),
                last_scraped_at=r.last_scraped_at,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return SourcesListResponse(items=items, total=total)


@router.get("/sources/{source_id}", response_model=Source, summary="Get source")
async def get_source(
    source_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        r = db.get_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found")
    return Source(
        id=r.id,
        name=r.name,
        url=r.url,
        source_type=r.source_type,  # type: ignore[assignment]
        active=bool(r.active),
        tags=r.tags,
        settings=(json.loads(r.settings_json) if r.settings_json else None),
        last_scraped_at=r.last_scraped_at,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.patch("/sources/{source_id}", response_model=Source, summary="Update source")
async def update_source(
    source_id: int = Path(..., ge=1),
    payload: SourceUpdateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    patch = payload.model_dump(exclude_unset=True)
    if "settings" in patch:
        patch["settings_json"] = json.dumps(patch.pop("settings")) if patch.get("settings") is not None else None
    try:
        row = db.update_source(source_id, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found")
    # tags replacement
    if payload.tags is not None:
        try:
            tags = db.set_source_tags(source_id, payload.tags)
            row.tags = tags  # type: ignore[attr-defined]
        except Exception:
            pass
    return Source(
        id=row.id,
        name=row.name,
        url=row.url,
        source_type=row.source_type,  # type: ignore[assignment]
        active=bool(row.active),
        tags=getattr(row, "tags", []),
        settings=(json.loads(row.settings_json) if row.settings_json else None),
        last_scraped_at=row.last_scraped_at,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.delete("/sources/{source_id}", summary="Delete source")
async def delete_source(
    source_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    ok = db.delete_source(source_id)
    if not ok:
        raise HTTPException(status_code=404, detail="source_not_found")
    return {"success": True}


@router.post("/sources/bulk", response_model=SourcesListResponse, summary="Bulk create sources")
async def bulk_create_sources(
    payload: SourcesBulkCreateRequest,
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    created: List[Source] = []
    for s in payload.sources:
        try:
            row = db.create_source(
                name=s.name,
                url=str(s.url),
                source_type=str(s.source_type),
                active=s.active,
                settings_json=(json.dumps(s.settings) if s.settings else None),
                tags=s.tags or [],
                group_ids=s.group_ids or [],
            )
            created.append(
                Source(
                    id=row.id,
                    name=row.name,
                    url=row.url,
                    source_type=row.source_type,  # type: ignore[assignment]
                    active=bool(row.active),
                    tags=row.tags,
                    settings=(json.loads(row.settings_json) if row.settings_json else None),
                    last_scraped_at=row.last_scraped_at,
                    status=row.status,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        except Exception as e:
            logger.debug(f"bulk create skipped one source: {e}")
            continue
    return SourcesListResponse(items=created, total=len(created))


# --------------------
# Tags
# --------------------
@router.get("/tags", response_model=TagsListResponse, summary="List tags")
async def list_tags(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_tags(q=q, limit=limit, offset=offset)
    return TagsListResponse(items=[Tag(id=r.id, name=r.name) for r in rows], total=total)


# --------------------
# Groups
# --------------------
@router.post("/groups", response_model=Group, summary="Create group")
async def create_group(
    payload: GroupCreateRequest,
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        row = db.create_group(name=payload.name, description=payload.description, parent_group_id=payload.parent_group_id)
    except Exception:
        raise HTTPException(status_code=400, detail="group_create_failed")
    return Group(id=row.id, name=row.name, description=row.description, parent_group_id=row.parent_group_id)


@router.get("/groups", response_model=GroupsListResponse, summary="List groups")
async def list_groups(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_groups(q=q, limit=limit, offset=offset)
    return GroupsListResponse(items=[Group(id=r.id, name=r.name, description=r.description, parent_group_id=r.parent_group_id) for r in rows], total=total)


@router.patch("/groups/{group_id}", response_model=Group, summary="Update group")
async def update_group(
    group_id: int = Path(..., ge=1),
    payload: GroupUpdateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        row = db.update_group(group_id, payload.model_dump(exclude_unset=True))
    except KeyError:
        raise HTTPException(status_code=404, detail="group_not_found")
    return Group(id=row.id, name=row.name, description=row.description, parent_group_id=row.parent_group_id)


@router.delete("/groups/{group_id}", summary="Delete group")
async def delete_group(
    group_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    ok = db.delete_group(group_id)
    if not ok:
        raise HTTPException(status_code=404, detail="group_not_found")
    return {"success": True}


# --------------------
# Jobs and runs
# --------------------
@router.post("/jobs", response_model=Job, summary="Create job")
async def create_job(
    payload: JobCreateRequest,
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        row = db.create_job(
            name=payload.name,
            description=payload.description,
            scope_json=json.dumps(payload.scope or {}),
            schedule_expr=payload.schedule_expr,
            schedule_timezone=payload.timezone,
            active=payload.active,
            max_concurrency=payload.max_concurrency,
            per_host_delay_ms=payload.per_host_delay_ms,
            retry_policy_json=json.dumps(payload.retry_policy or {}),
            output_prefs_json=json.dumps(payload.output_prefs or {}),
        )
    except Exception as e:
        logger.error(f"create_job failed: {e}")
        raise HTTPException(status_code=400, detail="job_create_failed")
    # Compute and persist next_run_at; register with workflows scheduler
    try:
        next_run = _compute_next_run(row.schedule_expr, row.schedule_timezone)
        if next_run:
            db.set_job_history(row.id, next_run_at=next_run)
            row = db.get_job(row.id)
    except Exception:
        pass
    # Register schedule with workflows scheduler for persistence/rehydration
    try:
        if row.schedule_expr:
            from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
            svc = get_workflows_scheduler()
            sid = svc.create(
                tenant_id=str(getattr(current_user, "tenant_id", "default")),
                user_id=str(current_user.id),
                workflow_id=None,
                name=f"watchlist:{row.id}:{row.name}",
                cron=row.schedule_expr,
                timezone=_normalize_tz(row.schedule_timezone) or "UTC",
                inputs={"watchlist_job_id": row.id},
                run_mode="async",
                validation_mode="block",
                enabled=bool(row.active),
                concurrency_mode="queue",
                misfire_grace_sec=300,
                coalesce=True,
            )
            db.set_job_schedule_id(row.id, sid)
            row = db.get_job(row.id)
    except Exception as e:
        logger.debug(f"Watchlists: schedule registration skipped: {e}")

    return Job(
        id=row.id,
        name=row.name,
        description=row.description,
        scope=(json.loads(row.scope_json or "{}")),
        schedule_expr=row.schedule_expr,
        timezone=row.schedule_timezone,
        active=bool(row.active),
        max_concurrency=row.max_concurrency,
        per_host_delay_ms=row.per_host_delay_ms,
        retry_policy=(json.loads(row.retry_policy_json or "{}")),
        output_prefs=(json.loads(row.output_prefs_json or "{}")),
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
    )


@router.get("/jobs", response_model=JobsListResponse, summary="List jobs")
async def list_jobs(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_jobs(q=q, limit=limit, offset=offset)
    items: List[Job] = []
    for r in rows:
        items.append(
            Job(
                id=r.id,
                name=r.name,
                description=r.description,
                scope=(json.loads(r.scope_json or "{}")),
                schedule_expr=r.schedule_expr,
                timezone=r.schedule_timezone,
                active=bool(r.active),
                max_concurrency=r.max_concurrency,
                per_host_delay_ms=r.per_host_delay_ms,
                retry_policy=(json.loads(r.retry_policy_json or "{}")),
                output_prefs=(json.loads(r.output_prefs_json or "{}")),
                created_at=r.created_at,
                updated_at=r.updated_at,
                last_run_at=r.last_run_at,
                next_run_at=r.next_run_at,
            )
        )
    return JobsListResponse(items=items, total=total)


@router.get("/jobs/{job_id}", response_model=Job, summary="Get job")
async def get_job(
    job_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        r = db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")
    return Job(
        id=r.id,
        name=r.name,
        description=r.description,
        scope=(json.loads(r.scope_json or "{}")),
        schedule_expr=r.schedule_expr,
        timezone=r.schedule_timezone,
        active=bool(r.active),
        max_concurrency=r.max_concurrency,
        per_host_delay_ms=r.per_host_delay_ms,
        retry_policy=(json.loads(r.retry_policy_json or "{}")),
        output_prefs=(json.loads(r.output_prefs_json or "{}")),
        created_at=r.created_at,
        updated_at=r.updated_at,
        last_run_at=r.last_run_at,
        next_run_at=r.next_run_at,
    )


@router.patch("/jobs/{job_id}", response_model=Job, summary="Update job")
async def update_job(
    job_id: int = Path(..., ge=1),
    payload: JobUpdateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    patch = payload.model_dump(exclude_unset=True)
    if "scope" in patch:
        patch["scope_json"] = json.dumps(patch.pop("scope") or {})
    if "retry_policy" in patch:
        patch["retry_policy_json"] = json.dumps(patch.pop("retry_policy") or {})
    if "output_prefs" in patch:
        patch["output_prefs_json"] = json.dumps(patch.pop("output_prefs") or {})
    try:
        r = db.update_job(job_id, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")
    # Update next_run_at if schedule changed
    try:
        if any(k in patch for k in ("schedule_expr", "schedule_timezone")):
            next_run = _compute_next_run(r.schedule_expr, r.schedule_timezone)
            db.set_job_history(job_id, next_run_at=next_run)
            r = db.get_job(job_id)
    except Exception:
        pass
    # Sync with workflows scheduler (create/update/enable/disable)
    try:
        from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
        svc = get_workflows_scheduler()
        if r.wf_schedule_id:
            upd: Dict[str, Any] = {}
            if "schedule_expr" in patch:
                upd["cron"] = r.schedule_expr or "* * * * *"
            if "schedule_timezone" in patch:
                upd["timezone"] = _normalize_tz(r.schedule_timezone) or "UTC"
            if "active" in patch:
                upd["enabled"] = bool(r.active)
            if upd:
                svc.update(r.wf_schedule_id, upd)
        else:
            if r.schedule_expr:
                sid = svc.create(
                    tenant_id=str(getattr(current_user, "tenant_id", "default")),
                    user_id=str(current_user.id),
                    workflow_id=None,
                    name=f"watchlist:{r.id}:{r.name}",
                    cron=r.schedule_expr,
                    timezone=_normalize_tz(r.schedule_timezone) or "UTC",
                    inputs={"watchlist_job_id": r.id},
                    run_mode="async",
                    validation_mode="block",
                    enabled=bool(r.active),
                    concurrency_mode="queue",
                    misfire_grace_sec=300,
                    coalesce=True,
                )
                db.set_job_schedule_id(r.id, sid)
                r = db.get_job(r.id)
    except Exception as e:
        logger.debug(f"Watchlists: schedule sync skipped: {e}")
    return Job(
        id=r.id,
        name=r.name,
        description=r.description,
        scope=(json.loads(r.scope_json or "{}")),
        schedule_expr=r.schedule_expr,
        timezone=r.schedule_timezone,
        active=bool(r.active),
        max_concurrency=r.max_concurrency,
        per_host_delay_ms=r.per_host_delay_ms,
        retry_policy=(json.loads(r.retry_policy_json or "{}")),
        output_prefs=(json.loads(r.output_prefs_json or "{}")),
        created_at=r.created_at,
        updated_at=r.updated_at,
        last_run_at=r.last_run_at,
        next_run_at=r.next_run_at,
    )


@router.delete("/jobs/{job_id}", summary="Delete job")
async def delete_job(
    job_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    # Try to delete linked schedule if present
    try:
        r = db.get_job(job_id)
        if getattr(r, "wf_schedule_id", None):
            from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
            get_workflows_scheduler().delete(r.wf_schedule_id)  # type: ignore[arg-type]
    except Exception:
        pass
    ok = db.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job_not_found")
    return {"success": True}


@router.post("/jobs/{job_id}/run", response_model=Run, summary="Trigger a run (stub)")
async def trigger_run(
    job_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    media_db = Depends(get_media_db_for_user),
):
    # Minimal stub: create a run row, set queued status.
    try:
        # Ensure job exists
        job = db.get_job(job_id)
        run = db.create_run(job_id, status="queued")
        # Update job history (last_run_at now, next_run_at by cron)
        from datetime import datetime, timezone as _tz
        last = datetime.utcnow().replace(tzinfo=_tz.utc).isoformat()
        next_run = _compute_next_run(job.schedule_expr, job.schedule_timezone)
        db.set_job_history(job_id, last_run_at=last, next_run_at=next_run)
        # Optionally submit via workflows scheduler (best-effort)
        if getattr(job, "wf_schedule_id", None):
            try:
                from tldw_Server_API.app.api.v1.endpoints.scheduler_workflows import run_now as _run_now_handler  # for scope checks we bypass API
            except Exception:
                pass
            try:
                from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
                svc = get_workflows_scheduler()
                s = svc.get(job.wf_schedule_id)
                if s:
                    core = await __import__("tldw_Server_API.app.core.Scheduler", fromlist=["create_scheduler"]).create_scheduler()
                    payload = {
                        "workflow_id": s.workflow_id,
                        "inputs": __import__("json").loads(s.inputs_json or "{}"),
                        "user_id": s.user_id,
                        "tenant_id": s.tenant_id,
                        "mode": s.run_mode,
                        "validation_mode": s.validation_mode,
                    }
                    await core.submit("workflow_run", payload=payload, queue_name="workflows", metadata={"user_id": s.user_id})
            except Exception as e:
                logger.debug(f"Watchlists: run-now via scheduler skipped: {e}")
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")
    except Exception as e:
        logger.error(f"trigger_run failed: {e}")
        raise HTTPException(status_code=500, detail="run_trigger_failed")
    return Run(
        id=run.id,
        job_id=run.job_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stats=None,
        error_msg=run.error_msg,
    )


@router.get("/jobs/{job_id}/runs", response_model=RunsListResponse, summary="List runs for a job")
async def list_runs_for_job(
    job_id: int = Path(..., ge=1),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_runs_for_job(job_id, limit=limit, offset=offset)
    items = [Run(id=r.id, job_id=r.job_id, status=r.status, started_at=r.started_at, finished_at=r.finished_at, stats=(json.loads(r.stats_json or "{}") if r.stats_json else None), error_msg=r.error_msg) for r in rows]
    return RunsListResponse(items=items, total=total)


@router.get("/runs/{run_id}", response_model=Run, summary="Get a run")
async def get_run(
    run_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        r = db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found")
    return Run(id=r.id, job_id=r.job_id, status=r.status, started_at=r.started_at, finished_at=r.finished_at, stats=(json.loads(r.stats_json or "{}") if r.stats_json else None), error_msg=r.error_msg)
