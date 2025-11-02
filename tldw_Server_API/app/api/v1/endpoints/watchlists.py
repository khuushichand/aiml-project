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
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, UploadFile, File, Form, Request
from fastapi.responses import PlainTextResponse, HTMLResponse, Response
from loguru import logger
from jinja2.sandbox import SandboxedEnvironment

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User
from tldw_Server_API.app.api.v1.API_Deps.Watchlists_DB_Deps import get_watchlists_db_for_user
from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job
from tldw_Server_API.app.core.Watchlists import template_store
from tldw_Server_API.app.core.Watchlists.opml import parse_opml, generate_opml
from tldw_Server_API.app.core.Watchlists.fetchers import fetch_rss_feed, fetch_site_items_with_rules
from tldw_Server_API.app.core.Watchlists.filters import normalize_filters as _normalize_job_filters, evaluate_filters as _evaluate_filters
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope as _get_scope
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool as _get_db_pool
# Lazy/optional notifications import: avoid blocking router load if optional deps fail
try:
    from tldw_Server_API.app.core.Notifications import NotificationsService  # type: ignore
except Exception:
    class NotificationsService:  # type: ignore
        def __init__(self, *, user_id: int, user_email: Optional[str] = None) -> None:
            self.user_id = user_id
            self.user_email = user_email

        async def deliver_email(
            self,
            *,
            subject: str,
            html_body: str,
            text_body: Optional[str],
            recipients: Optional[List[str]],
            attachments: Optional[List[Dict[str, Any]]] = None,
            fallback_to_user_email: bool = True,
        ) -> Any:
            # Minimal shim for tests; report skipped
            return type("_Result", (), {"channel": "email", "status": "skipped", "details": {"reason": "notifications_unavailable"}})()

        def deliver_chatbook(
            self,
            *,
            title: str,
            content: str,
            description: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
            document_type: Any = None,
            provider: str = "watchlists",
            model: str = "watchlists",
            conversation_id: Optional[int] = None,
        ) -> Any:
            return type("_Result", (), {"channel": "chatbook", "status": "skipped", "details": {"reason": "notifications_unavailable"}})()
from tldw_Server_API.app.api.v1.schemas.watchlists_schemas import (
    Source, SourceCreateRequest, SourceUpdateRequest, SourcesListResponse, SourcesBulkCreateRequest,
    SourcesBulkCreateResponse, SourcesBulkCreateItem,
    Group, GroupCreateRequest, GroupUpdateRequest, GroupsListResponse,
    Tag, TagsListResponse,
    Job, JobCreateRequest, JobUpdateRequest, JobsListResponse,
    Run, RunsListResponse, RunDetail,
    PreviewItem, PreviewResponse,
    ScrapedItem, ScrapedItemsListResponse, ScrapedItemUpdateRequest,
    WatchlistOutput, WatchlistOutputCreateRequest, WatchlistOutputsListResponse,
    WatchlistTemplateCreateRequest, WatchlistTemplateDetail, WatchlistTemplateListResponse, WatchlistTemplateSummary,
    WatchlistFiltersPayload, WatchlistFilter, SourcesImportResponse, SourcesImportItem,
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


def _normalize_filters_payload(raw_json: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw_json:
        return None
    try:
        data = json.loads(raw_json)
        if isinstance(data, dict):
            # Ensure key exists
            if "filters" not in data:
                data["filters"] = []
            return data
        if isinstance(data, list):
            return {"filters": data}
    except Exception:
        return None
    return None


# ---- Rate limit helpers (test-aware) ----
import functools
from tldw_Server_API.app.api.v1.API_Deps.rate_limiting import limiter as _limiter


def _limits_disabled_now() -> bool:
    try:
        return (
            os.getenv("WATCHLISTS_DISABLE_RATE_LIMITS", "").strip().lower() in {"1", "true", "yes", "on"}
            or os.getenv("PYTEST_CURRENT_TEST") is not None
            or os.getenv("TLDW_TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
            or os.getenv("TEST_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
        )
    except Exception:
        return False


def _optional_limit(rate: str):
    def _decorator(func):
        if _limiter is None or _limits_disabled_now():
            return func
        wrapped = _limiter.limit(rate)(func)

        @functools.wraps(func)
        async def _inner(*args, **kwargs):  # type: ignore
            if _limits_disabled_now():
                return await func(*args, **kwargs)
            req = kwargs.get("request", None)
            try:
                from starlette.requests import Request as _StarReq  # type: ignore
                if not isinstance(req, _StarReq):
                    return await func(*args, **kwargs)
            except Exception:
                return await func(*args, **kwargs)
            return await wrapped(*args, **kwargs)

        return _inner

    return _decorator


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
            line += f" - {itm.summary}"
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
            entry += f" - {summary_text}"
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
    job_filters = None
    try:
        jf = getattr(job_row, "job_filters_json", None)
        if jf:
            parsed = json.loads(jf)
            # Normalize to {"filters": [...]} shape
            if isinstance(parsed, dict):
                job_filters = {"filters": list(parsed.get("filters") or [])}
            elif isinstance(parsed, list):
                job_filters = {"filters": parsed}
    except Exception:
        job_filters = None
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
        "job_filters": job_filters,
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
_YT_HOST_RE = re.compile(r"(^|\.)youtube\.com$|(^|\.)youtu\.be$", re.IGNORECASE)


def _is_youtube_url(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        # Strip leading 'www.'
        if host.startswith("www."):
            host = host[4:]
        return bool(_YT_HOST_RE.search(host))
    except Exception:
        return False


def _is_youtube_feed_url(url: str) -> bool:
    """Accept only canonical YouTube RSS feed URLs.

    Allowed forms:
      - https://www.youtube.com/feeds/videos.xml?channel_id=...
      - https://www.youtube.com/feeds/videos.xml?playlist_id=...
      - https://www.youtube.com/feeds/videos.xml?user=...
    """
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
        path_ok = u.path.lower().startswith("/feeds/videos.xml")
        if not path_ok:
            return False
        raw_qs = parse_qs(u.query or "")
        # Treat query keys case-insensitively (CHANNEL_ID, LIST, USER, etc.)
        qs = {str(k).lower(): v for k, v in raw_qs.items()}
        return any(k in qs for k in ("channel_id", "playlist_id", "user"))
    except Exception:
        return False


def _normalize_youtube_feed_url(url: str) -> Optional[str]:
    """Attempt to normalize some YouTube URLs to canonical feed URLs.

    Supports channel, playlist, and user URL forms. Other forms are not normalized.
    """
    try:
        from urllib.parse import urlparse, parse_qs
        u = urlparse(url)
        raw_qs = parse_qs(u.query or "")
        # Normalize query keys to lowercase for case-insensitive lookup
        qs = {str(k).lower(): v for k, v in raw_qs.items()}
        parts = [p for p in (u.path or "").split("/") if p]
        # playlist
        if "list" in qs and qs["list"]:
            return f"https://www.youtube.com/feeds/videos.xml?playlist_id={qs['list'][0]}"
        # channel
        if len(parts) >= 2 and parts[0].lower() == "channel":
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={parts[1]}"
        # user
        if len(parts) >= 2 and parts[0].lower() == "user":
            return f"https://www.youtube.com/feeds/videos.xml?user={parts[1]}"
    except Exception:
        return None
    return None


def _validate_youtube_feed_or_raise(url: str, source_type: str) -> None:
    if str(source_type).lower() != "rss":
        return
    if _is_youtube_url(url) and not _is_youtube_feed_url(url):
        # Actionable error with canonical patterns
        raise HTTPException(
            status_code=400,
            detail=(
                "invalid_youtube_rss_url: use canonical feed URLs; "
                "channel → https://www.youtube.com/feeds/videos.xml?channel_id=..., "
                "playlist → https://www.youtube.com/feeds/videos.xml?playlist_id=..."
            ),
        )

@router.post("/sources", response_model=Source, summary="Create a source")
async def create_source(
    payload: SourceCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    try:
        # Backend normalization/validation for YouTube-as-RSS
        url_str = str(payload.url)
        orig_url_for_log = url_str
        if str(payload.source_type).lower() == "rss" and _is_youtube_url(url_str) and not _is_youtube_feed_url(url_str):
            normalized = _normalize_youtube_feed_url(url_str)
            if normalized:
                url_str = normalized
                try:
                    if response is not None:
                        response.headers["X-YouTube-Normalized"] = "1"
                        response.headers["X-YouTube-Canonical-URL"] = url_str
                except Exception:
                    pass
                try:
                    logger.debug(f"watchlists.create_source: normalized YouTube URL {orig_url_for_log} -> {url_str}")
                except Exception:
                    pass
            else:
                _validate_youtube_feed_or_raise(url_str, str(payload.source_type))
        row = db.create_source(
            name=payload.name,
            url=url_str,
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
    except HTTPException:
        # Propagate validation/HTTP errors unchanged
        raise
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


# OPML import/export placed before /sources/{source_id} to avoid route conflicts
@router.get("/sources/export", summary="Export sources to OPML")
async def export_sources_opml(
    tag: Optional[List[str]] = Query(None, description="Filter by tag(s)"),
    group: Optional[List[int]] = Query(None, description="Filter by group id(s) (OR semantics)"),
    type: Optional[str] = Query(None, description="Filter by source_type (rss/site)"),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    # Base selection
    if group:
        try:
            rows = db.list_sources_by_group_ids([int(g) for g in group])
        except Exception:
            rows = []
        # Apply tag filter manually (AND semantics)
        if tag:
            needed = [t.strip().lower() for t in tag if t and str(t).strip()]
            def _has_all_tags(src) -> bool:
                src_tags = [str(t).strip().lower() for t in (getattr(src, "tags", []) or [])]
                return all(n in src_tags for n in needed)
            rows = [r for r in rows if _has_all_tags(r)]
    else:
        rows, _ = db.list_sources(q=None, tag_names=tag, limit=10000, offset=0)
    # Build OPML items (rss sources only)
    items: List[Dict[str, Any]] = []
    for r in rows:
        if type and str(r.source_type).lower() != type.lower():
            continue
        if str(r.source_type).lower() != "rss":
            continue
        items.append({"name": r.name, "url": r.url, "html_url": None})
    xml = generate_opml(items)
    return Response(content=xml, media_type="application/xml")


@router.post("/sources/import", response_model=SourcesImportResponse, summary="Import sources from OPML")
@_optional_limit("10/minute")
async def import_sources_opml(
    request: Request,
    file: UploadFile = File(...),
    active: bool = Form(True),
    tags: Optional[List[str]] = Form(None),
    group_id: Optional[int] = Form(None),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    content = await file.read()
    entries = parse_opml(content)
    items: List[SourcesImportItem] = []
    created = skipped = errors = 0
    default_tags = tags or []
    for e in entries:
        if not e.url:
            items.append(SourcesImportItem(url="", name=e.name, status="error", error="missing_url"))
            errors += 1
            continue
        try:
            row = db.create_source(
                name=e.name or e.url,
                url=e.url,
                source_type="rss",
                active=bool(active),
                settings_json=None,
                tags=default_tags,
                group_ids=([group_id] if group_id else []),
            )
            items.append(SourcesImportItem(url=e.url, name=row.name, id=row.id, status="created"))
            created += 1
        except Exception as exc:
            items.append(SourcesImportItem(url=e.url, name=e.name, status="skipped", error=str(exc)))
            skipped += 1
    # Best-effort rate-limit header
    if not _limits_disabled_now():
        try:
            if response is not None:
                response.headers.setdefault("X-RateLimit-Limit", "10/minute")
                return SourcesImportResponse(items=items, total=(created + skipped + errors), created=created, skipped=skipped, errors=errors)
        except Exception:
            pass
        try:
            from fastapi.responses import JSONResponse
            payload = {
                "items": [i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in items],
                "total": (created + skipped + errors),
                "created": created,
                "skipped": skipped,
                "errors": errors,
            }
            return JSONResponse(content=payload, headers={"X-RateLimit-Limit": "10/minute"})
        except Exception:
            pass
    return SourcesImportResponse(items=items, total=(created + skipped + errors), created=created, skipped=skipped, errors=errors)

# (moved above /sources/{source_id})


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
    response: Response = None,  # type: ignore[assignment]
):
    # Determine target source_type/url for validation
    try:
        existing = db.get_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found")
    target_type = str(payload.source_type) if (getattr(payload, "source_type", None) is not None) else str(existing.source_type)
    target_url = str(payload.url) if (getattr(payload, "url", None) is not None) else str(existing.url)
    # Normalize/validate when target_type is rss and URL is YouTube
    if target_type.lower() == "rss" and _is_youtube_url(target_url) and not _is_youtube_feed_url(target_url):
        orig_url_for_log = target_url
        normalized = _normalize_youtube_feed_url(target_url)
        if normalized:
            target_url = normalized
            if payload.url is not None:
                try:
                    payload.url = type(payload.url)(target_url)  # type: ignore[call-arg]
                except Exception:
                    pass
            try:
                if response is not None:
                    response.headers["X-YouTube-Normalized"] = "1"
                    response.headers["X-YouTube-Canonical-URL"] = target_url
            except Exception:
                pass
            try:
                logger.debug(f"watchlists.update_source: normalized YouTube URL {orig_url_for_log} -> {target_url}")
            except Exception:
                pass
        else:
            _validate_youtube_feed_or_raise(target_url, target_type)
    patch = payload.model_dump(exclude_unset=True)
    if "settings" in patch:
        patch["settings_json"] = json.dumps(patch.pop("settings")) if patch.get("settings") is not None else None
    # Coerce pydantic types to primitives for DB layer
    if "url" in patch and patch["url"] is not None:
        try:
            patch["url"] = str(patch["url"])
        except Exception:
            pass
    row = db.update_source(source_id, patch)
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


@router.post(




















    "/sources/bulk",
    response_model=SourcesBulkCreateResponse,
    summary="Bulk create sources with per-entry status",
    description=(
        "Creates multiple sources and returns per-entry status. "
        "Each item is either created or returns an error with reason.\n\n"
        "Validation: When `source_type=\"rss\"` and the URL is a YouTube link, only canonical RSS feeds "
        "are accepted (e.g., https://www.youtube.com/feeds/videos.xml?channel_id=..., playlist_id=..., user=...). "
        "Non-feed YouTube URLs are rejected per-entry with error `invalid_youtube_rss_url`. "
        "Tags must be non-empty strings; invalid tags are rejected per-entry with `invalid_tag_names`."
    ),
)
async def bulk_create_sources(
    payload: SourcesBulkCreateRequest,
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    items: List[SourcesBulkCreateItem] = []
    created_count = 0
    errors_count = 0
    for s in payload.sources:
        # Normalize/Validate YouTube-as-RSS for each entry; collect per-entry error instead of silent skip
        try:
            url_str = str(s.url)
            if str(s.source_type).lower() == "rss" and _is_youtube_url(url_str) and not _is_youtube_feed_url(url_str):
                normalized = _normalize_youtube_feed_url(url_str)
                if normalized:
                    url_str = normalized
                    try:
                        logger.debug(f"watchlists.bulk_create_sources: normalized YouTube URL {s.url} -> {url_str}")
                    except Exception:
                        pass
                else:
                    _validate_youtube_feed_or_raise(url_str, str(s.source_type))
        except HTTPException as ve:
            items.append(
                SourcesBulkCreateItem(
                    name=s.name,
                    url=str(s.url),
                    status="error",
                    error=str(ve.detail),
                    source_type=str(s.source_type),
                )
            )
            errors_count += 1
            continue

        # Validate tag name shape (no empty/whitespace-only names)
        try:
            if s.tags is not None:
                invalid_tags = [t for t in s.tags if (not isinstance(t, str) or not t.strip())]
                if invalid_tags:
                    items.append(
                        SourcesBulkCreateItem(
                            name=s.name,
                            url=str(s.url),
                            status="error",
                            error=f"invalid_tag_names: {invalid_tags}",
                            source_type=str(s.source_type),
                        )
                    )
                    errors_count += 1
                    continue
        except Exception:
            items.append(
                SourcesBulkCreateItem(
                    name=s.name,
                    url=str(s.url),
                    status="error",
                    error="tag_validation_failed",
                    source_type=str(s.source_type),
                )
            )
            errors_count += 1
            continue

        # Validate group_ids existence per-entry
        try:
            if s.group_ids:
                missing: List[int] = []
                for gid in s.group_ids:
                    try:
                        db.get_group(int(gid))
                    except KeyError:
                        missing.append(int(gid))
                if missing:
                    items.append(
                        SourcesBulkCreateItem(
                            name=s.name,
                            url=str(s.url),
                            status="error",
                            error=f"group_not_found: {missing}",
                            source_type=str(s.source_type),
                        )
                    )
                    errors_count += 1
                    continue
        except Exception as e:
            items.append(
                SourcesBulkCreateItem(
                    name=s.name,
                    url=str(s.url),
                    status="error",
                    error="group_validation_failed",
                    source_type=str(s.source_type),
                )
            )
            errors_count += 1
            continue

        try:
            row = db.create_source(
                name=s.name,
                url=url_str if ('url_str' in locals()) else str(s.url),
                source_type=str(s.source_type),
                active=s.active,
                settings_json=(json.dumps(s.settings) if s.settings else None),
                tags=s.tags or [],
                group_ids=s.group_ids or [],
            )
            # Echo request name for stable per-entry mapping, even on idempotent creates
            items.append(
                SourcesBulkCreateItem(
                    id=row.id,
                    name=s.name,
                    url=row.url,
                    status="created",
                    source_type=row.source_type,  # type: ignore[assignment]
                )
            )
            created_count += 1
        except Exception as e:
            logger.debug(f"bulk create error: {e}")
            items.append(
                SourcesBulkCreateItem(
                    name=s.name,
                    url=str(s.url),
                    status="error",
                    error="source_create_failed",
                    source_type=str(s.source_type),
                )
            )
            errors_count += 1

    return SourcesBulkCreateResponse(
        items=items,
        total=len(items),
        created=created_count,
        errors=errors_count,
    )


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
        jf_json = None
        try:
            if payload.job_filters and isinstance(payload.job_filters.model_dump(), dict):
                jf_json = json.dumps(payload.job_filters.model_dump())
        except Exception:
            jf_json = None
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
            job_filters_json=jf_json,
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
        job_filters=_normalize_filters_payload(getattr(row, "job_filters_json", None)),
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
    )


@router.post("/jobs/{job_id}/preview", response_model=PreviewResponse, summary="Preview candidates and filter decisions without ingestion")
async def preview_job(
    job_id: int = Path(..., ge=1),
    limit: int = Query(20, ge=1, le=200, description="Max candidates to return across all sources"),
    per_source: int = Query(10, ge=1, le=100, description="Max candidates per source"),
    include_content: bool = Query(False, description="Reserved; previews return summary only for now"),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        job = db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")

    # Resolve sources for job scope (IDs, tags, groups)
    scope = {}
    try:
        scope = json.loads(job.scope_json or "{}") if job.scope_json else {}
    except Exception:
        scope = {}

    selected: Dict[int, Any] = {}
    for sid in map(int, scope.get("sources", []) or []):
        try:
            r = db.get_source(sid)
            if int(r.active or 0) == 1:
                selected[int(r.id)] = r
        except Exception:
            continue
    tag_names = scope.get("tags") or []
    if tag_names:
        rows, _ = db.list_sources(q=None, tag_names=tag_names, limit=10000, offset=0)
        for r in rows:
            if int(r.active or 0) == 1:
                selected[int(r.id)] = r
    group_ids = scope.get("groups") or []
    if group_ids:
        try:
            rows = db.list_sources_by_group_ids(group_ids)
            for r in rows:
                if int(r.active or 0) == 1:
                    selected[int(r.id)] = r
        except Exception:
            pass
    sources = list(selected.values())

    # Load job filters and include-only gating default
    raw_filters = {}
    try:
        raw_filters = json.loads(job.job_filters_json or "{}") if getattr(job, "job_filters_json", None) else {}
    except Exception:
        raw_filters = {}
    job_filters = _normalize_job_filters(raw_filters)

    async def _org_require_include_default() -> bool:
        try:
            scope_ctx = _get_scope()
            org_id = getattr(scope_ctx, "effective_org_id", None) if scope_ctx else None
            if org_id is not None:
                pool = await _get_db_pool()
                row = await pool.fetchone("SELECT metadata FROM organizations WHERE id = ?", int(org_id))
                if row is not None:
                    meta = row.get("metadata")
                    if isinstance(meta, str):
                        meta = json.loads(meta)
                    if isinstance(meta, dict):
                        watch = meta.get("watchlists") if isinstance(meta.get("watchlists"), dict) else {}
                        if isinstance(watch, dict) and isinstance(watch.get("require_include_default"), bool):
                            return bool(watch.get("require_include_default"))
                        flat = meta.get("watchlists_require_include_default")
                        if isinstance(flat, bool):
                            return flat
        except Exception:
            pass
        try:
            return str(os.getenv("WATCHLISTS_REQUIRE_INCLUDE_DEFAULT", "")).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            return False

    include_rules_exist = any((str(f.get("action")) == "include") for f in job_filters)
    job_require_include = None
    if isinstance(raw_filters, dict) and "require_include" in raw_filters:
        try:
            job_require_include = bool(raw_filters.get("require_include"))
        except Exception:
            job_require_include = None
    org_default = await _org_require_include_default()
    effective_require_include = job_require_include if (job_require_include is not None) else org_default
    include_gating_active = bool(effective_require_include and include_rules_exist)

    # Collect candidates
    items: List[PreviewItem] = []
    total_ingestable = 0
    total_filtered = 0
    test_mode = os.getenv("TEST_MODE", "").lower() in {"1", "true", "yes"}

    for src in sources:
        if len(items) >= limit:
            break
        per_items: List[Dict[str, Any]] = []
        try:
            if str(src.source_type).lower() == "rss":
                if test_mode:
                    per_items = [{
                        "title": "Test Item",
                        "url": "https://example.com/test",
                        "summary": "Preview sample",
                        "published": datetime.now(timezone.utc).isoformat(),
                        "author": None,
                    }]
                else:
                    feed = await fetch_rss_feed(str(src.url), etag=None, last_modified=None, tenant_id=str(current_user.id))
                    per_items = feed.get("items") or []
            else:
                if test_mode:
                    per_items = [{
                        "title": "Site Item",
                        "url": getattr(src, "url", None) or "https://example.com/",
                        "summary": "Preview sample",
                        "content": "",
                        "author": None,
                    }]
                else:
                    cfg = {}
                    try:
                        cfg = json.loads(src.settings_json or "{}") if getattr(src, "settings_json", None) else {}
                    except Exception:
                        cfg = {}
                    per_items = await fetch_site_items_with_rules(str(src.url), rules=cfg.get("scrape_rules") or {}, limit=per_source)
        except Exception:
            per_items = []

        taken = 0
        for it in per_items:
            if len(items) >= limit or taken >= per_source:
                break
            title = it.get("title")
            link = it.get("url") or it.get("link")
            summary = it.get("summary") or it.get("content")
            published = it.get("published") or it.get("published_at")

            candidate = {
                "title": title,
                "summary": summary,
                "content": None,
                "author": it.get("author"),
                "published_at": published,
            }
            action, meta = _evaluate_filters(job_filters, candidate)
            # Determine final decision with include-only gating
            if action == "exclude":
                decision = "filtered"
            elif include_gating_active and action != "include":
                decision = "filtered"
            else:
                decision = "ingest"
            flagged = (action == "flag")
            if decision == "ingest":
                total_ingestable += 1
            else:
                total_filtered += 1
            items.append(
                PreviewItem(
                    source_id=int(src.id),
                    source_type=str(src.source_type),  # type: ignore[arg-type]
                    url=link,
                    title=title,
                    summary=summary if not include_content else summary,
                    published_at=published,
                    decision=decision,  # type: ignore[arg-type]
                    matched_action=action,  # type: ignore[arg-type]
                    matched_filter_key=(meta.get("key") if isinstance(meta, dict) else None),
                    flagged=flagged,
                )
            )
            taken += 1

    return PreviewResponse(items=items, total=len(items), ingestable=total_ingestable, filtered=total_filtered)


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
                job_filters=_normalize_filters_payload(getattr(r, "job_filters_json", None)),
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
        job_filters=(json.loads(r.job_filters_json or "{}") if getattr(r, "job_filters_json", None) else None),
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
    if "job_filters" in patch:
        patch["job_filters_json"] = json.dumps(patch.pop("job_filters") or {})
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
        job_filters=_normalize_filters_payload(getattr(r, "job_filters_json", None)),
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


@router.patch("/jobs/{job_id}/filters", response_model=WatchlistFiltersPayload, summary="Replace job filters")
@_optional_limit("30/minute")
async def replace_job_filters(
    request: Request,
    job_id: int = Path(..., ge=1),
    payload: WatchlistFiltersPayload = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    try:
        db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")
    updated = db.set_job_filters(job_id, payload.model_dump())
    # Normalize and return
    try:
        parsed = json.loads(updated.job_filters_json or "{}") if getattr(updated, "job_filters_json", None) else {"filters": []}
    except Exception:
        parsed = {"filters": []}
    # Best-effort rate-limit header for visibility
    try:
        if response is not None and not _limits_disabled_now():
            response.headers.setdefault("X-RateLimit-Limit", "30/minute")
    except Exception:
        pass
    return WatchlistFiltersPayload(**parsed) if isinstance(parsed, dict) else WatchlistFiltersPayload(filters=[])


@router.post("/jobs/{job_id}/filters:add", response_model=WatchlistFiltersPayload, summary="Append job filters")
@_optional_limit("30/minute")
async def append_job_filters(
    request: Request,
    job_id: int = Path(..., ge=1),
    payload: WatchlistFiltersPayload = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    try:
        current = db.get_job_filters(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found")
    existing = list(current.get("filters") or [])
    to_add = payload.filters or []
    new_filters = existing + [f.model_dump() if hasattr(f, "model_dump") else f for f in to_add]
    db.set_job_filters(job_id, {"filters": new_filters})
    try:
        if response is not None and not _limits_disabled_now():
            response.headers.setdefault("X-RateLimit-Limit", "30/minute")
    except Exception:
        pass
    return WatchlistFiltersPayload(filters=[WatchlistFilter(**f) if isinstance(f, dict) else f for f in new_filters])


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
    has_more = (offset + len(items)) < int(total or 0)
    return RunsListResponse(items=items, total=total, has_more=has_more)


@router.get("/runs", response_model=RunsListResponse, summary="List runs across all jobs")
async def list_runs_global(
    q: Optional[str] = Query(None, description="Filter by job name/description, run status, or run id (text)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    rows, total = db.list_runs(q=q, limit=limit, offset=offset)
    items = [
        Run(
            id=r.id,
            job_id=r.job_id,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            stats=(json.loads(r.stats_json or "{}") if r.stats_json else None),
            error_msg=r.error_msg,
        )
        for r in rows
    ]
    has_more = (offset + len(items)) < int(total or 0)
    return RunsListResponse(items=items, total=total, has_more=has_more)


@router.get("/runs/export.csv", response_class=PlainTextResponse, summary="Export runs as CSV (global or by job)")
async def export_runs_csv(
    scope: str = Query("global", pattern="^(global|job)$"),
    job_id: Optional[int] = Query(None, ge=1),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=1000),
    include_tallies: bool = Query(False, description="When true, include a filter_tallies_json column per row"),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    """Return a CSV export of runs with basic counters.

    Columns: id,job_id,status,started_at,finished_at,items_found,items_ingested,filters_include,filters_exclude,filters_flag
    """
    limit = size
    offset = (page - 1) * limit
    if scope == "job":
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id_required")
        rows, total = db.list_runs_for_job(job_id, limit=limit, offset=offset)
    else:
        rows, total = db.list_runs(q=q, limit=limit, offset=offset)
    headers = [
        "id",
        "job_id",
        "status",
        "started_at",
        "finished_at",
        "items_found",
        "items_ingested",
        "filters_include",
        "filters_exclude",
        "filters_flag",
    ]
    if include_tallies:
        headers.append("filter_tallies_json")
    out_lines = [",".join(headers)]
    for r in rows:
        try:
            stats = json.loads(r.stats_json or "{}") if r.stats_json else {}
        except Exception:
            stats = {}
        vals = [
            str(r.id),
            str(r.job_id),
            json.dumps(r.status or ""),
            json.dumps(r.started_at or ""),
            json.dumps(r.finished_at or ""),
            str(int((stats or {}).get("items_found", 0) or 0)),
            str(int((stats or {}).get("items_ingested", 0) or 0)),
            str(int(((stats.get("filters_actions") or {}).get("include", 0)) if isinstance(stats, dict) else 0)),
            str(int(((stats.get("filters_actions") or {}).get("exclude", 0)) if isinstance(stats, dict) else 0)),
            str(int(((stats.get("filters_actions") or {}).get("flag", 0)) if isinstance(stats, dict) else 0)),
        ]
        if include_tallies:
            try:
                tallies = stats.get("filter_tallies") if isinstance(stats, dict) else None
                vals.append(json.dumps(tallies or {}))
            except Exception:
                vals.append("{}")
        out_lines.append(",".join(vals))
    filename = f"watchlists_runs_{scope}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    # Include lightweight pagination metadata parity via header
    try:
        has_more = (offset + len(rows)) < int(total or 0)
    except Exception:
        has_more = False
    return PlainTextResponse(
        "\n".join(out_lines),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Has-More": "true" if has_more else "false",
        },
    )

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
    include_tallies: bool = Query(False, description="When true, include filter_tallies in the response"),
    filtered_sample_max: int = Query(5, ge=0, le=50, description="Optional number of filtered items to include as a sample"),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    """Return a summarized view of run stats and logs.

    Note: Per-filter tallies are retained in the raw run stats (GET /watchlists/runs/{run_id})
    under the key `filter_tallies` for detailed analysis. This detail view returns
    flattened totals (filters_include/exclude/flag) for quick inspection.
    """
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
    # Build stats for detail view, including filter totals when present
    detail_stats: Dict[str, int] = {"items_found": items_found, "items_ingested": items_ingested}
    try:
        if isinstance(stats.get("filters_matched"), int):
            detail_stats["filters_matched"] = int(stats.get("filters_matched") or 0)
        fa = stats.get("filters_actions")
        if isinstance(fa, dict):
            for k in ("include", "exclude", "flag"):
                v = fa.get(k)
                if isinstance(v, int):
                    detail_stats[f"filters_{k}"] = int(v)
    except Exception:
        pass
    # Optional tallies
    tallies_out = None
    if include_tallies:
        try:
            tallies = stats.get("filter_tallies")
            if isinstance(tallies, dict):
                # Coerce values to int
                tallies_out = {str(k): int(v) for k, v in tallies.items() if isinstance(k, (str, int)) and isinstance(v, (int, float))}
        except Exception:
            tallies_out = None

    # Optional filtered items sample for triage
    filtered_sample = None
    if filtered_sample_max and filtered_sample_max > 0:
        try:
            rows, _ = db.list_items(run_id=run_id, status="filtered", limit=int(filtered_sample_max), offset=0)
            filtered_sample = [
                {
                    "id": it.id,
                    "title": it.title,
                    "url": it.url,
                    "status": it.status,
                }
                for it in rows
            ]
        except Exception:
            filtered_sample = None

    # Expose filter debug max knob via header for visibility
    try:
        debug_max_env = int(os.getenv("WATCHLISTS_FILTER_DEBUG_MAX", "100") or 100)
        if response is not None:
            response.headers["X-Watchlists-Filter-Debug-Max"] = str(debug_max_env)
    except Exception:
        pass

    return RunDetail(
        id=r.id,
        job_id=r.job_id,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        stats=detail_stats,
        filter_tallies=tallies_out,
        error_msg=r.error_msg,
        log_text=log_text,
        log_path=r.log_path,
        truncated=truncated,
        filtered_sample=filtered_sample,
    )


# --------------------
# CSV Exports (Admin convenience)
# --------------------



@router.get("/runs/{run_id}/tallies.csv", response_class=PlainTextResponse, summary="Export filter tallies for a run as CSV")
async def export_run_tallies_csv(
    run_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        r = db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found")
    try:
        stats = json.loads(r.stats_json or "{}") if r.stats_json else {}
    except Exception:
        stats = {}
    tallies = stats.get("filter_tallies") if isinstance(stats, dict) else None
    headers = ["run_id", "filter_key", "count"]
    out_lines = [",".join(headers)]
    if isinstance(tallies, dict):
        for k, v in tallies.items():
            try:
                out_lines.append(",".join([str(run_id), json.dumps(str(k)), str(int(v))]))
            except Exception:
                continue
    filename = f"watchlists_run_{run_id}_tallies_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    return PlainTextResponse("\n".join(out_lines), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})


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
