from __future__ import annotations

"""
Watchlists API (sources, groups/tags, jobs, runs)

Implements minimal CRUD and semantics per PRD:
- Tag name→id mapping (accept names, resolve/create internally, return names)
- Bulk sources endpoint at /watchlists/sources/bulk

Scraping and scheduling are stubbed; runs are created on trigger.
"""

from typing import Any, Dict, List, Optional, Tuple
import json
import os
import re
from datetime import datetime, timezone, timedelta
from html import escape
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from loguru import logger
from jinja2.sandbox import SandboxedEnvironment

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.Watchlists_DB_Deps import get_watchlists_db_for_user
from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job
from tldw_Server_API.app.core.Watchlists import template_store
from tldw_Server_API.app.core.Notifications import NotificationsService
from tldw_Server_API.app.api.v1.schemas.watchlists_schemas import (
    Source, SourceCreateRequest, SourceUpdateRequest, SourcesListResponse, SourcesBulkCreateRequest,
    Group, GroupCreateRequest, GroupUpdateRequest, GroupsListResponse,
    Tag, TagsListResponse,
    Job, JobCreateRequest, JobUpdateRequest, JobsListResponse,
    Run, RunsListResponse, RunDetail,
    ScrapedItem, ScrapedItemsListResponse, ScrapedItemUpdateRequest,
    WatchlistOutput, WatchlistOutputCreateRequest, WatchlistOutputsListResponse,
    WatchlistTemplateCreateRequest, WatchlistTemplateDetail, WatchlistTemplateListResponse, WatchlistTemplateSummary,
)


router = APIRouter(prefix="/watchlists", tags=["watchlists"])

DEFAULT_OUTPUT_TTL_SECONDS = int(os.getenv("WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS", "0") or 0)
TEMP_OUTPUT_TTL_SECONDS = int(os.getenv("WATCHLIST_OUTPUT_TEMP_TTL_SECONDS", "86400") or 86400)

_TEMPLATE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(expires_at: Optional[str]) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at).astimezone(timezone.utc) <= datetime.now(timezone.utc)
    except Exception:
        return False


# ---- Helpers ----
_EMAIL_TAG_RE = re.compile(r"<[^>]+>")


def _safe_int(value: Any, fallback: int) -> int:
    try:
        if value is None:
            return fallback
        return int(value)
    except Exception:
        return fallback


def _deep_merge_dict(base: Optional[Dict[str, Any]], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _build_email_bodies(content: Optional[str], fmt: str, title: str, preferred: str = "auto") -> Tuple[str, str]:
    raw = content or ""
    mode = preferred.lower()
    if mode == "auto":
        mode = "html" if fmt.lower() == "html" else "text"
    if mode == "html":
        html_body = raw or f"<p>{escape(title)}</p>"
        text_body = _EMAIL_TAG_RE.sub(" ", raw) if raw else title
        text_body = re.sub(r"\s+", " ", text_body).strip()
        return html_body, text_body or title
    text_body = raw or title
    html_body = f"<pre>{escape(raw)}</pre>" if raw else f"<p>{escape(title)}</p>"
    return html_body, text_body


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


def _row_to_scraped_item(row) -> ScrapedItem:
    tags: List[str] = []
    try:
        tags = row.tags()
    except Exception:
        raw = getattr(row, "tags_json", None)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    tags = [str(t) for t in data if isinstance(t, str)]
            except Exception:
                tags = []
    reviewed_flag = bool(getattr(row, "reviewed", 0))
    return ScrapedItem(
        id=row.id,
        run_id=row.run_id,
        job_id=row.job_id,
        source_id=row.source_id,
        media_id=getattr(row, "media_id", None),
        media_uuid=getattr(row, "media_uuid", None),
        url=getattr(row, "url", None),
        title=getattr(row, "title", None),
        summary=getattr(row, "summary", None),
        published_at=getattr(row, "published_at", None),
        tags=tags,
        status=row.status,
        reviewed=reviewed_flag,
        created_at=row.created_at,
    )


def _row_to_output(row) -> WatchlistOutput:
    metadata: Dict[str, Any] = {}
    try:
        metadata = row.metadata()
    except Exception:
        raw = getattr(row, "metadata_json", None)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    metadata = data
            except Exception:
                metadata = {}
    version = getattr(row, "version", 1)
    expires_at = getattr(row, "expires_at", None)
    if isinstance(metadata, dict):
        metadata.setdefault("version", version)
    return WatchlistOutput(
        id=row.id,
        run_id=row.run_id,
        job_id=row.job_id,
        type=row.type,
        format=row.format,
        title=getattr(row, "title", None),
        content=getattr(row, "content", None),
        storage_path=getattr(row, "storage_path", None),
        metadata=metadata if isinstance(metadata, dict) else {},
        media_item_id=getattr(row, "media_item_id", None),
        chatbook_path=getattr(row, "chatbook_path", None),
        version=version,
        expires_at=expires_at,
        expired=_is_expired(expires_at),
        created_at=row.created_at,
    )


def _items_to_markdown_lines(items: List[ScrapedItem]) -> List[str]:
    lines: List[str] = []
    for idx, itm in enumerate(items, 1):
        entry_title = itm.title or f"Item {idx}"
        if itm.url:
            line = f"{idx}. [{entry_title}]({itm.url})"
        else:
            line = f"{idx}. {entry_title}"
        if itm.summary:
            line += f" — {itm.summary}"
        lines.append(line)
    return lines


def _items_to_html_entries(items: List[ScrapedItem]) -> List[str]:
    entries: List[str] = []
    for idx, itm in enumerate(items, 1):
        title_text = escape(itm.title or f"Item {idx}")
        summary_text = escape(itm.summary or "")
        url = itm.url
        if url:
            entry = f'<li><a href="{escape(url)}">{title_text}</a>'
        else:
            entry = f"<li>{title_text}"
        if summary_text:
            entry += f" — {summary_text}"
        entry += "</li>"
        entries.append(entry)
    return entries


def _render_default_markdown(title: str, items: List[ScrapedItem]) -> str:
    lines = [f"# {title}", ""]
    lines.extend(_items_to_markdown_lines(items))
    return "\n".join(lines)


def _render_default_html(title: str, items: List[ScrapedItem]) -> str:
    body_parts = [f"<h1>{escape(title)}</h1>", "<ol>"]
    body_parts.extend(_items_to_html_entries(items))
    body_parts.append("</ol>")
    return "\n".join(body_parts)


def _job_payload(job_row: Any) -> Dict[str, Any]:
    scope = {}
    try:
        scope = json.loads(job_row.scope_json or "{}") if getattr(job_row, "scope_json", None) else {}
    except Exception:
        scope = {}
    retry_policy = {}
    try:
        retry_policy = (
            json.loads(job_row.retry_policy_json or "{}") if getattr(job_row, "retry_policy_json", None) else {}
        )
    except Exception:
        retry_policy = {}
    output_prefs = {}
    try:
        output_prefs = (
            json.loads(job_row.output_prefs_json or "{}") if getattr(job_row, "output_prefs_json", None) else {}
        )
    except Exception:
        output_prefs = {}
    return {
        "id": job_row.id,
        "name": job_row.name,
        "description": getattr(job_row, "description", None),
        "scope": scope,
        "schedule_expr": getattr(job_row, "schedule_expr", None),
        "schedule_timezone": getattr(job_row, "schedule_timezone", None),
        "active": bool(getattr(job_row, "active", True)),
        "max_concurrency": getattr(job_row, "max_concurrency", None),
        "per_host_delay_ms": getattr(job_row, "per_host_delay_ms", None),
        "retry_policy": retry_policy,
        "output_prefs": output_prefs,
    }


def _run_payload(run_row: Any) -> Dict[str, Any]:
    stats = {}
    try:
        stats = json.loads(run_row.stats_json or "{}") if getattr(run_row, "stats_json", None) else {}
    except Exception:
        stats = {}
    return {
        "id": run_row.id,
        "job_id": run_row.job_id,
        "status": run_row.status,
        "started_at": getattr(run_row, "started_at", None),
        "finished_at": getattr(run_row, "finished_at", None),
        "stats": stats,
        "error_msg": getattr(run_row, "error_msg", None),
    }


def _build_output_context(
    title: str,
    job_row: Any,
    run_row: Any,
    items: List[ScrapedItem],
) -> Dict[str, Any]:
    markdown_lines = _items_to_markdown_lines(items)
    html_entries = _items_to_html_entries(items)
    items_payload: List[Dict[str, Any]] = []
    for idx, itm in enumerate(items, 1):
        if hasattr(itm, "model_dump"):
            payload = itm.model_dump()
        else:
            payload = {
                "id": itm.id,
                "run_id": itm.run_id,
                "job_id": itm.job_id,
                "source_id": itm.source_id,
                "media_id": itm.media_id,
                "media_uuid": itm.media_uuid,
                "url": itm.url,
                "title": itm.title,
                "summary": itm.summary,
                "published_at": itm.published_at,
                "tags": itm.tags,
                "status": itm.status,
                "reviewed": itm.reviewed,
                "created_at": itm.created_at,
            }
        payload.setdefault("index", idx)
        payload.setdefault("markdown_line", markdown_lines[idx - 1])
        payload.setdefault("html_entry", html_entries[idx - 1])
        items_payload.append(payload)

    context = {
        "title": title,
        "generated_at": _utcnow_iso(),
        "job": _job_payload(job_row),
        "run": _run_payload(run_row),
        "items": items_payload,
        "items_markdown": markdown_lines,
        "items_html": html_entries,
        "item_count": len(items_payload),
    }
    return context


def _render_template_with_context(template_str: str, context: Dict[str, Any]) -> str:
    env = SandboxedEnvironment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    env.filters["markdown_link"] = lambda text, url: f"[{text}]({url})" if url else text
    template = env.from_string(template_str)
    return template.render(**context)


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
        # Ensure tags reflect payload even when source pre-exists (idempotent create)
        if payload.tags is not None:
            try:
                tags = db.set_source_tags(row.id, payload.tags)
                row.tags = tags  # type: ignore[attr-defined]
            except Exception:
                pass
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
@router.get("/settings", summary="Get watchlists defaults")
async def get_watchlist_settings(
    current_user: User = Depends(get_request_user),
):
    return {
        "default_output_ttl_seconds": DEFAULT_OUTPUT_TTL_SECONDS,
        "temporary_output_ttl_seconds": TEMP_OUTPUT_TTL_SECONDS,
    }


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
        logger.debug(f"Watchlists: schedule registration via service failed, falling back: {e}")
        # Fallback: create a persisted schedule row directly so admin can inspect linkage
        try:
            if row.schedule_expr:
                from uuid import uuid4
                sid = uuid4().hex
                from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import WorkflowsSchedulerDB
                wfdb = WorkflowsSchedulerDB(user_id=int(current_user.id))
                wfdb.create_schedule(
                    id=sid,
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
        except Exception as _e:
            logger.debug(f"Watchlists: schedule DB fallback failed: {_e}")

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
    include_internal: bool = Query(False, description="Admin-only: include scheduler linkage fields"),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        r = db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")
    is_admin = bool(getattr(current_user, "is_admin", False))
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
        wf_schedule_id=(r.wf_schedule_id if include_internal and is_admin else None),
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
                try:
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
                except Exception as _e:
                    logger.debug(f"Watchlists: schedule create during update failed, fallback: {_e}")
                    try:
                        from uuid import uuid4
                        sid = uuid4().hex
                        from tldw_Server_API.app.core.DB_Management.Workflows_Scheduler_DB import WorkflowsSchedulerDB
                        wfdb = WorkflowsSchedulerDB(user_id=int(current_user.id))
                        wfdb.create_schedule(
                            id=sid,
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
                    except Exception as __e:
                        logger.debug(f"Watchlists: schedule DB fallback during update failed: {__e}")
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


@router.post("/jobs/{job_id}/run", response_model=Run, summary="Trigger a run (executes pipeline)")
async def trigger_run(
    job_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        # Ensure job exists before execution
        db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")

    try:
        result = await run_watchlist_job(int(current_user.id), job_id)
        run_id = int(result.get("run_id"))
        run = db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=500, detail="run_lookup_failed")
    except Exception as e:
        logger.error(f"trigger_run failed: {e}")
        raise HTTPException(status_code=500, detail="run_trigger_failed")
    stats_dict: Optional[Dict[str, Any]] = None
    try:
        stats_dict = json.loads(run.stats_json or "{}") if run.stats_json else None
    except Exception:
        stats_dict = None
    return Run(
        id=run.id,
        job_id=run.job_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stats=stats_dict,
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


@router.get("/runs/{run_id}/details", response_model=RunDetail, summary="Get run details with stats and logs")
async def get_run_details(
    run_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        r = db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found")
    # Stats defaulting
    stats = {}
    try:
        stats = json.loads(r.stats_json or "{}") if r.stats_json else {}
    except Exception:
        stats = {}
    if not isinstance(stats, dict):
        stats = {}
    items_found = int(stats.get("items_found", 0) or 0)
    items_ingested = int(stats.get("items_ingested", 0) or 0)
    # Log content (best-effort; truncated)
    log_text = None
    truncated = False
    if r.log_path:
        try:
            from pathlib import Path as _Path
            p = _Path(r.log_path)
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
                max_len = 65536
                if len(content) > max_len:
                    log_text = content[-max_len:]
                    truncated = True
                else:
                    log_text = content
        except Exception:
            log_text = None
            truncated = False
    return RunDetail(
        id=r.id,
        job_id=r.job_id,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        stats={"items_found": items_found, "items_ingested": items_ingested},
        error_msg=r.error_msg,
        log_text=log_text,
        log_path=r.log_path,
        truncated=truncated,
    )


# --------------------
# Scraped items
# --------------------
@router.get("/items", response_model=ScrapedItemsListResponse, summary="List scraped items across runs")
async def list_scraped_items(
    run_id: Optional[int] = Query(None),
    job_id: Optional[int] = Query(None),
    source_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    reviewed: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="Search by title/summary substring"),
    since: Optional[str] = Query(None, description="ISO date filter (created_at >= since)"),
    until: Optional[str] = Query(None, description="ISO date filter (created_at <= until)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_items(
        run_id=run_id,
        job_id=job_id,
        source_id=source_id,
        status=status,
        reviewed=reviewed,
        search=q,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return ScrapedItemsListResponse(items=[_row_to_scraped_item(r) for r in rows], total=total)


@router.get("/items/{item_id}", response_model=ScrapedItem, summary="Get a scraped item")
async def get_scraped_item(
    item_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        row = db.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="item_not_found")
    return _row_to_scraped_item(row)


@router.patch("/items/{item_id}", response_model=ScrapedItem, summary="Update item flags")
async def update_scraped_item(
    item_id: int = Path(..., ge=1),
    payload: ScrapedItemUpdateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        row = db.update_item_flags(
            item_id,
            reviewed=payload.reviewed,
            status=payload.status,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="item_not_found")
    return _row_to_scraped_item(row)


# --------------------
# Outputs
# --------------------
@router.post("/outputs", response_model=WatchlistOutput, summary="Generate an output from scraped items")
async def create_output(
    payload: WatchlistOutputCreateRequest,
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    db.purge_expired_outputs()
    try:
        run = db.get_run(payload.run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        job = db.get_job(run.job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")

    job_prefs: Dict[str, Any] = {}
    try:
        job_prefs = (
            json.loads(job.output_prefs_json or "{}") if getattr(job, "output_prefs_json", None) else {}
        )
    except Exception:
        job_prefs = {}
    retention_spec = job_prefs.get("retention") or {}
    job_default_retention = _safe_int(retention_spec.get("default_seconds"), DEFAULT_OUTPUT_TTL_SECONDS)
    job_temp_retention = _safe_int(retention_spec.get("temporary_seconds"), TEMP_OUTPUT_TTL_SECONDS)
    template_defaults = job_prefs.get("template") or {}
    delivery_defaults = job_prefs.get("deliveries") or {}

    job_id = run.job_id
    items: List[Any]
    if payload.item_ids:
        items = db.get_items_by_ids(payload.item_ids)
        if not items:
            raise HTTPException(status_code=400, detail="items_not_found")
        if any(it.run_id != payload.run_id for it in items):
            raise HTTPException(status_code=400, detail="items_must_belong_to_run")
    else:
        items, _ = db.list_items(run_id=payload.run_id, status="ingested", limit=1000, offset=0)

    if not items:
        raise HTTPException(status_code=400, detail="no_items_available")

    item_models = [_row_to_scraped_item(it) for it in items]
    version = db.next_output_version(payload.run_id)
    job_name = getattr(job, "name", None) or f"Job-{job.id}"
    default_title = f"{job_name}-Output-{version}"
    title = payload.title or default_title

    template_name = payload.template_name or template_defaults.get("default_name")
    template_record = None
    if template_name:
        if not _TEMPLATE_NAME_RE.fullmatch(template_name):
            raise HTTPException(status_code=400, detail="invalid_template_name")
        try:
            template_record = template_store.load_template(template_name)
        except template_store.TemplateNotFoundError:
            raise HTTPException(status_code=404, detail="template_not_found")
    output_format = (
        payload.format
        or template_defaults.get("default_format")
        or (template_record.format if template_record else "md")
    )
    if output_format not in {"md", "html"}:
        raise HTTPException(status_code=400, detail="invalid_format")

    context = _build_output_context(title, job, run, item_models)
    if template_record:
        context["template_name"] = template_record.name
        if template_record.description:
            context["template_description"] = template_record.description
        try:
            content = _render_template_with_context(template_record.content, context)
        except Exception as exc:
            logger.error(f"Watchlists template render failed: {exc}")
            raise HTTPException(status_code=400, detail=f"template_render_failed: {exc}")
    else:
        if output_format == "html":
            content = _render_default_html(title, item_models)
        else:
            content = _render_default_markdown(title, item_models)

    metadata: Dict[str, Any] = {}
    if payload.metadata:
        try:
            metadata.update(payload.metadata)
        except Exception:
            pass
    metadata.update(
        {
            "item_count": len(item_models),
            "item_ids": [itm.id for itm in item_models],
            "format": output_format,
            "type": payload.type,
        }
    )
    if template_record:
        metadata["template_name"] = template_record.name
        if template_record.description:
            metadata["template_description"] = template_record.description
    metadata["version"] = version

    delivery_override = (
        payload.deliveries.model_dump(exclude_none=True) if payload.deliveries else {}
    )
    delivery_plan = (
        _deep_merge_dict(delivery_defaults, delivery_override)
        if (delivery_defaults or delivery_override)
        else {}
    )
    if delivery_plan:
        metadata["delivery_plan"] = delivery_plan

    retention = payload.retention_seconds
    if retention is None:
        retention = job_temp_retention if payload.temporary else job_default_retention
    expires_at = None
    if retention and retention > 0:
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=retention)).isoformat()
        metadata["retention_seconds"] = retention
        metadata["expires_at"] = expires_at
    metadata["temporary"] = bool(payload.temporary)
    metadata = {k: v for k, v in metadata.items() if v is not None}

    row = db.create_output(
        run_id=payload.run_id,
        job_id=job_id,
        type=payload.type,
        format=output_format,
        title=title,
        content=content,
        metadata=metadata,
        version=version,
        expires_at=expires_at,
    )
    output = _row_to_output(row)

    notifications = NotificationsService(
        user_id=int(current_user.id or 0),
        user_email=getattr(current_user, "email", None),
    )
    delivery_results: List[Dict[str, Any]] = []
    chatbook_path_update: Optional[str] = None
    metadata_update_needed = False

    if isinstance(delivery_plan, dict):
        email_cfg = delivery_plan.get("email") if isinstance(delivery_plan.get("email"), dict) else None
        if email_cfg and bool(email_cfg.get("enabled", True)):
            html_body, text_body = _build_email_bodies(
                output.content or "",
                (output.format or output_format),
                title,
                email_cfg.get("body_format", "auto"),
            )
            attachments = None
            if email_cfg.get("attach_file", True) and output.content:
                ext = "html" if (output.format or output_format) == "html" else "md"
                safe_base = (title or f"watchlist-output-{output.id}").replace("/", "_")
                attachments = [
                    {
                        "filename": f"{safe_base}.{ext}",
                        "content": (output.content or "").encode("utf-8"),
                    }
                ]
            email_result = await notifications.deliver_email(
                subject=email_cfg.get("subject") or title,
                html_body=html_body,
                text_body=text_body or None,
                recipients=email_cfg.get("recipients"),
                attachments=attachments,
                fallback_to_user_email=True,
            )
            delivery_results.append(
                {
                    "channel": email_result.channel,
                    "status": email_result.status,
                    **email_result.details,
                }
            )
            metadata_update_needed = True

        chat_cfg = delivery_plan.get("chatbook") if isinstance(delivery_plan.get("chatbook"), dict) else None
        if chat_cfg and bool(chat_cfg.get("enabled", True)):
            chat_metadata = dict(chat_cfg.get("metadata") or {})
            chat_metadata.update(
                {
                    "job_id": job_id,
                    "run_id": payload.run_id,
                    "output_id": output.id,
                    "version": version,
                }
            )
            chat_result = notifications.deliver_chatbook(
                title=chat_cfg.get("title") or title,
                content=output.content or "",
                description=chat_cfg.get("description"),
                metadata=chat_metadata,
                provider=chat_cfg.get("provider", "watchlists"),
                model=chat_cfg.get("model", "watchlists"),
                conversation_id=chat_cfg.get("conversation_id"),
            )
            delivery_results.append(
                {
                    "channel": chat_result.channel,
                    "status": chat_result.status,
                    **chat_result.details,
                }
            )
            doc_id = chat_result.details.get("document_id")
            if chat_result.status == "stored" and doc_id is not None:
                chatbook_path_update = f"generated_document:{doc_id}"
                metadata.setdefault("chatbook_document_id", doc_id)
                metadata_update_needed = True

    if delivery_results:
        metadata["deliveries"] = delivery_results
        metadata_update_needed = True
    if metadata.get("delivery_plan") == {}:
        metadata.pop("delivery_plan", None)
        metadata_update_needed = True

    metadata_for_update: Optional[Dict[str, Any]] = None
    if metadata_update_needed:
        metadata_for_update = {k: v for k, v in metadata.items() if v is not None}

    if metadata_for_update is not None or chatbook_path_update:
        updated_row = db.update_output_record(
            output.id,
            metadata=metadata_for_update,
            chatbook_path=chatbook_path_update,
        )
        output = _row_to_output(updated_row)

    return output


@router.get("/outputs", response_model=WatchlistOutputsListResponse, summary="List generated outputs")
async def list_outputs(
    run_id: Optional[int] = Query(None),
    job_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_outputs(run_id=run_id, job_id=job_id, limit=limit, offset=offset)
    return WatchlistOutputsListResponse(items=[_row_to_output(r) for r in rows], total=total)


@router.get("/outputs/{output_id}", response_model=WatchlistOutput, summary="Get output metadata")
async def get_output(
    output_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    db.purge_expired_outputs()
    try:
        row = db.get_output(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")
    output = _row_to_output(row)
    if output.expired:
        db.purge_expired_outputs()
        raise HTTPException(status_code=404, detail="output_not_found")
    return output


@router.get("/outputs/{output_id}/download", summary="Download rendered output")
async def download_output(
    output_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    db.purge_expired_outputs()
    try:
        row = db.get_output(output_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="output_not_found")
    output = _row_to_output(row)
    if output.expired:
        db.purge_expired_outputs()
        raise HTTPException(status_code=404, detail="output_not_found")
    content = output.content or ""
    fmt = output.format or "md"
    filename = (output.title or f"watchlist-output-{output_id}").replace("/", "_")
    if fmt == "html":
        headers = {"Content-Disposition": f'attachment; filename="{filename}.html"'}
        return HTMLResponse(content=content, headers=headers)
    headers = {"Content-Disposition": f'attachment; filename="{filename}.md"'}
    return PlainTextResponse(content=content, media_type="text/markdown", headers=headers)


# --------------------
# Templates
# --------------------
@router.get("/templates", response_model=WatchlistTemplateListResponse, summary="List available templates")
async def list_templates(
    current_user: User = Depends(get_request_user),
):
    records = template_store.list_templates()
    items = [
        WatchlistTemplateSummary(
            name=rec.name,
            format=rec.format,
            description=rec.description,
            updated_at=rec.updated_at,
        )
        for rec in records
    ]
    return WatchlistTemplateListResponse(items=items)


@router.get("/templates/{template_name}", response_model=WatchlistTemplateDetail, summary="Fetch a template")
async def get_template(
    template_name: str,
    current_user: User = Depends(get_request_user),
):
    if not _TEMPLATE_NAME_RE.fullmatch(template_name):
        raise HTTPException(status_code=400, detail="invalid_template_name")
    try:
        record = template_store.load_template(template_name)
    except template_store.TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="template_not_found")
    return WatchlistTemplateDetail(
        name=record.name,
        format=record.format,
        description=record.description,
        updated_at=record.updated_at,
        content=record.content,
    )


@router.post("/templates", response_model=WatchlistTemplateDetail, summary="Create or update a template")
async def create_template(
    payload: WatchlistTemplateCreateRequest,
    current_user: User = Depends(get_request_user),
):
    try:
        record = template_store.save_template(
            name=payload.name,
            fmt=payload.format,
            content=payload.content,
            description=payload.description,
            overwrite=payload.overwrite,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except template_store.TemplateExistsError:
        raise HTTPException(status_code=409, detail="template_exists")
    return WatchlistTemplateDetail(
        name=record.name,
        format=record.format,
        description=record.description,
        updated_at=record.updated_at,
        content=record.content,
    )


@router.delete("/templates/{template_name}", summary="Delete a template")
async def delete_template(
    template_name: str,
    current_user: User = Depends(get_request_user),
):
    if not _TEMPLATE_NAME_RE.fullmatch(template_name):
        raise HTTPException(status_code=400, detail="invalid_template_name")
    try:
        template_store.delete_template(template_name)
    except template_store.TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="template_not_found")
    return {"deleted": True}
