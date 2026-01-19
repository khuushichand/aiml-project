from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from loguru import logger

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.Watchlists_DB_Deps import get_watchlists_db_for_user
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.api.v1.schemas.collections_feeds_schemas import (
    CollectionsFeed,
    CollectionsFeedCreateRequest,
    CollectionsFeedsListResponse,
)


FEED_ORIGIN = "feed"
_FEED_JOB_KEYS = ("collections_feed_job_id", "collections_job_id")

router = APIRouter(prefix="/collections/feeds", tags=["collections-feeds"])


def _parse_settings(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _is_feed_source(settings: Dict[str, Any]) -> bool:
    if settings.get("collections_origin") == FEED_ORIGIN:
        return True
    nested = settings.get("collections")
    return isinstance(nested, dict) and nested.get("origin") == FEED_ORIGIN


def _extract_job_id(settings: Dict[str, Any]) -> Optional[int]:
    for key in _FEED_JOB_KEYS:
        val = settings.get(key)
        if val is None:
            continue
        try:
            return int(val)
        except Exception:
            continue
    nested = settings.get("collections")
    if isinstance(nested, dict) and nested.get("job_id") is not None:
        try:
            return int(nested.get("job_id"))
        except Exception:
            return None
    return None


def _sanitize_settings(settings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not settings:
        return None
    cleaned = dict(settings)
    cleaned.pop("collections_origin", None)
    for key in _FEED_JOB_KEYS:
        cleaned.pop(key, None)
    nested = cleaned.get("collections")
    if isinstance(nested, dict):
        nested = dict(nested)
        nested.pop("origin", None)
        nested.pop("job_id", None)
        if nested:
            cleaned["collections"] = nested
        else:
            cleaned.pop("collections", None)
    return cleaned or None


def _default_name(url: str) -> str:
    try:
        host = urlparse(url).hostname
    except Exception:
        host = None
    return host or url or "Feed"


def _normalize_tz(tz: Optional[str]) -> str:
    if not tz or tz.upper() == "UTC":
        return "UTC"
    t = tz.strip().upper()
    if t.startswith("UTC+") or t.startswith("UTC-"):
        try:
            sign = 1 if t[3] == "+" else -1
            hours = int(t[4:])
            etc_offset = -sign * hours
            return f"Etc/GMT{('+' if etc_offset > 0 else '')}{etc_offset}" if etc_offset != 0 else "Etc/GMT"
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


def _register_schedule(db: WatchlistsDatabase, job_row, *, current_user: User) -> None:
    if not getattr(job_row, "schedule_expr", None):
        return
    try:
        from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
        svc = get_workflows_scheduler()
        sid = svc.create(
            tenant_id=str(getattr(current_user, "tenant_id", "default")),
            user_id=str(current_user.id),
            workflow_id=None,
            name=f"watchlist:{job_row.id}:{job_row.name}",
            cron=job_row.schedule_expr,
            timezone=_normalize_tz(job_row.schedule_timezone) or "UTC",
            inputs={"watchlist_job_id": job_row.id},
            run_mode="async",
            validation_mode="block",
            enabled=bool(job_row.active),
            concurrency_mode="queue",
            misfire_grace_sec=300,
            coalesce=True,
        )
        db.set_job_schedule_id(job_row.id, sid)
        return
    except Exception as exc:
        logger.debug(f"Collections feeds schedule registration failed: {exc}")
    try:
        if job_row.schedule_expr:
            from uuid import uuid4
            from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import WorkflowsSchedulerDB
            sid = uuid4().hex
            wfdb = WorkflowsSchedulerDB(user_id=int(current_user.id))
            wfdb.create_schedule(
                id=sid,
                tenant_id=str(getattr(current_user, "tenant_id", "default")),
                user_id=str(current_user.id),
                workflow_id=None,
                name=f"watchlist:{job_row.id}:{job_row.name}",
                cron=job_row.schedule_expr,
                timezone=_normalize_tz(job_row.schedule_timezone) or "UTC",
                inputs={"watchlist_job_id": job_row.id},
                run_mode="async",
                validation_mode="block",
                enabled=bool(job_row.active),
                concurrency_mode="queue",
                misfire_grace_sec=300,
                coalesce=True,
            )
            db.set_job_schedule_id(job_row.id, sid)
    except Exception as exc:
        logger.debug(f"Collections feeds schedule DB fallback failed: {exc}")


def _to_feed_response(source_row, *, job_row=None, settings: Optional[Dict[str, Any]] = None) -> CollectionsFeed:
    settings = settings if settings is not None else _parse_settings(source_row.settings_json)
    job_id = _extract_job_id(settings)
    return CollectionsFeed(
        id=int(source_row.id),
        name=source_row.name,
        url=source_row.url,
        source_type=str(source_row.source_type or "rss"),
        origin=FEED_ORIGIN,
        tags=list(source_row.tags or []),
        active=bool(source_row.active),
        settings=_sanitize_settings(settings),
        last_scraped_at=source_row.last_scraped_at,
        etag=source_row.etag,
        last_modified=source_row.last_modified,
        defer_until=source_row.defer_until,
        status=source_row.status,
        consec_not_modified=source_row.consec_not_modified,
        created_at=source_row.created_at,
        updated_at=source_row.updated_at,
        job_id=job_row.id if job_row is not None else job_id,
        schedule_expr=getattr(job_row, "schedule_expr", None),
        timezone=getattr(job_row, "schedule_timezone", None),
        job_active=getattr(job_row, "active", None),
        next_run_at=getattr(job_row, "next_run_at", None),
        wf_schedule_id=getattr(job_row, "wf_schedule_id", None),
    )


def _load_job(db: WatchlistsDatabase, settings: Dict[str, Any]):
    job_id = _extract_job_id(settings)
    if not job_id:
        return None
    try:
        return db.get_job(job_id)
    except Exception:
        return None


@router.post("", response_model=CollectionsFeed, summary="Create a Collections feed subscription")
async def create_feed_subscription(
    payload: CollectionsFeedCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db: WatchlistsDatabase = Depends(get_watchlists_db_for_user),
) -> CollectionsFeed:
    settings = payload.settings if isinstance(payload.settings, dict) else {}
    settings = dict(settings)
    settings["collections_origin"] = FEED_ORIGIN
    name = payload.name.strip() if isinstance(payload.name, str) and payload.name.strip() else _default_name(str(payload.url))
    tags = [t for t in (payload.tags or []) if t]
    try:
        source = db.create_source(
            name=name,
            url=str(payload.url),
            source_type="rss",
            active=payload.active,
            settings_json=json.dumps(settings),
            tags=tags,
            group_ids=None,
        )
    except Exception as exc:
        logger.error(f"collections_feeds_create_source_failed: {exc}")
        raise HTTPException(status_code=400, detail="feed_create_failed")

    try:
        job = db.create_job(
            name=f"Feed: {name}",
            description=f"Collections feed subscription for {source.url}",
            scope_json=json.dumps({"sources": [int(source.id)]}),
            schedule_expr=payload.schedule_expr,
            schedule_timezone=payload.timezone,
            active=payload.active,
            max_concurrency=None,
            per_host_delay_ms=None,
            retry_policy_json=json.dumps({}),
            output_prefs_json=json.dumps({"collections_origin": FEED_ORIGIN}),
            job_filters_json=None,
        )
    except Exception as exc:
        logger.error(f"collections_feeds_create_job_failed: {exc}")
        try:
            db.delete_source(int(source.id))
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="feed_create_failed")

    settings["collections_feed_job_id"] = int(job.id)
    try:
        db.update_source(int(source.id), {"settings_json": json.dumps(settings)})
        source = db.get_source(int(source.id))
    except Exception:
        pass
    next_run = _compute_next_run(job.schedule_expr, job.schedule_timezone)
    if next_run:
        db.set_job_history(job_id=int(job.id), next_run_at=next_run)
        job = db.get_job(int(job.id))
    _register_schedule(db, job, current_user=current_user)
    job = db.get_job(int(job.id))
    return _to_feed_response(source, job_row=job, settings=settings)


@router.get("", response_model=CollectionsFeedsListResponse, summary="List Collections feed subscriptions")
async def list_feed_subscriptions(
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db: WatchlistsDatabase = Depends(get_watchlists_db_for_user),
) -> CollectionsFeedsListResponse:
    offset = max(0, (page - 1) * size)
    limit = max(size, 100)
    collected: List[Tuple[Any, Dict[str, Any]]] = []
    total_sources = 0
    fetch_offset = 0
    while True:
        rows, total = db.list_sources(q=q, tag_names=None, limit=limit, offset=fetch_offset)
        total_sources = total
        if not rows:
            break
        for row in rows:
            settings = _parse_settings(row.settings_json)
            if not _is_feed_source(settings):
                continue
            collected.append((row, settings))
        fetch_offset += limit
        if fetch_offset >= total_sources:
            break
    total = len(collected)
    paged = collected[offset: offset + size]
    items: List[CollectionsFeed] = []
    for row, settings in paged:
        job = _load_job(db, settings)
        items.append(_to_feed_response(row, job_row=job, settings=settings))
    return CollectionsFeedsListResponse(items=items, total=total)


@router.get("/{feed_id}", response_model=CollectionsFeed, summary="Get a Collections feed subscription")
async def get_feed_subscription(
    feed_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db: WatchlistsDatabase = Depends(get_watchlists_db_for_user),
) -> CollectionsFeed:
    try:
        source = db.get_source(feed_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="feed_not_found")
    settings = _parse_settings(source.settings_json)
    if not _is_feed_source(settings):
        raise HTTPException(status_code=404, detail="feed_not_found")
    job = _load_job(db, settings)
    return _to_feed_response(source, job_row=job, settings=settings)


@router.delete("/{feed_id}", summary="Delete a Collections feed subscription")
async def delete_feed_subscription(
    feed_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db: WatchlistsDatabase = Depends(get_watchlists_db_for_user),
):
    try:
        source = db.get_source(feed_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="feed_not_found")
    settings = _parse_settings(source.settings_json)
    if not _is_feed_source(settings):
        raise HTTPException(status_code=404, detail="feed_not_found")
    job_id = _extract_job_id(settings)
    if job_id:
        try:
            job = db.get_job(job_id)
            if getattr(job, "wf_schedule_id", None):
                from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
                get_workflows_scheduler().delete(job.wf_schedule_id)  # type: ignore[arg-type]
        except Exception:
            pass
        try:
            db.delete_job(job_id)
        except Exception:
            pass
    deleted = db.delete_source(feed_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="feed_not_found")
    return {"success": True}
