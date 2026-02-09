"""
Watchlists API (sources, groups/tags, jobs, runs)

Implements minimal CRUD and semantics per PRD:
- Tag name→id mapping (accept names, resolve/create internally, return names)
- Bulk sources endpoint at /watchlists/sources/bulk

Scraping and scheduling are stubbed; runs are created on trigger.
"""
from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Path,  # noqa: F811
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from loguru import logger
from starlette.responses import FileResponse

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit
from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.Watchlists_DB_Deps import get_watchlists_db_for_user
from tldw_Server_API.app.core.AuthNZ.api_key_manager import get_api_key_manager
from tldw_Server_API.app.core.AuthNZ.database import get_db_pool as _get_db_pool
from tldw_Server_API.app.core.AuthNZ.ip_allowlist import (
    is_single_user_ip_allowed,
    resolve_client_ip,
)
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import (
    User,
    get_request_user,
    resolve_user_id_for_request,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.scope_context import get_scope as _get_scope
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.exceptions import TemplateValidationError
from tldw_Server_API.app.core.Streaming.streams import WebSocketStream
from tldw_Server_API.app.core.testing import is_test_mode as _is_test_mode
from tldw_Server_API.app.core.testing import is_truthy as _is_truthy
from tldw_Server_API.app.core.Watchlists import template_store
from tldw_Server_API.app.core.Watchlists.fetchers import fetch_rss_feed, fetch_site_items_with_rules
from tldw_Server_API.app.core.Watchlists.filters import evaluate_filters as _evaluate_filters
from tldw_Server_API.app.core.Watchlists.filters import normalize_filters as _normalize_job_filters
from tldw_Server_API.app.core.Watchlists.opml import generate_opml, parse_opml
from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job
from tldw_Server_API.app.core.DB_Management.backends.base import DatabaseError as _DatabaseError
from tldw_Server_API.app.services.outputs_service import (
    _build_output_filename,
    _ingest_output_to_media_db,
    _outputs_dir_for_user,
    _resolve_output_path_for_user,
    _strip_html_for_tts,
    _write_tts_audio_file,
    render_output_template,
    summarize_items_for_output,
)

# Lazy/optional notifications import: avoid blocking router load if optional deps fail
try:
    from tldw_Server_API.app.core.Notifications import NotificationsService  # type: ignore
except (ImportError, OSError):
    class NotificationsService:  # type: ignore
        def __init__(self, *, user_id: int, user_email: str | None = None) -> None:
            self.user_id = user_id
            self.user_email = user_email

        async def deliver_email(
            self,
            *,
            subject: str,
            html_body: str,
            text_body: str | None,
            recipients: list[str] | None,
            attachments: list[dict[str, Any]] | None = None,
            fallback_to_user_email: bool = True,
        ) -> Any:
            # Minimal shim for tests; report skipped
            return type("_Result", (), {"channel": "email", "status": "skipped", "details": {"reason": "notifications_unavailable"}})()

        def deliver_chatbook(
            self,
            *,
            title: str,
            content: str,
            description: str | None = None,
            metadata: dict[str, Any] | None = None,
            document_type: Any = None,
            provider: str = "watchlists",
            model: str = "watchlists",
            conversation_id: int | None = None,
        ) -> Any:
            return type("_Result", (), {"channel": "chatbook", "status": "skipped", "details": {"reason": "notifications_unavailable"}})()

from tldw_Server_API.app.api.v1.schemas.watchlists_schemas import (  # noqa: E402
    Group,
    GroupCreateRequest,
    GroupsListResponse,
    GroupUpdateRequest,
    Job,
    JobCreateRequest,
    JobsListResponse,
    JobUpdateRequest,
    PreviewItem,
    PreviewResponse,
    Run,
    RunDetail,
    RunsListResponse,
    ScrapedItem,
    ScrapedItemsListResponse,
    ScrapedItemUpdateRequest,
    Source,
    SourceCreateRequest,
    SourcesBulkCreateItem,
    SourcesBulkCreateRequest,
    SourcesBulkCreateResponse,
    SourceSeenResetResponse,
    SourceSeenStats,
    SourcesImportItem,
    SourcesImportResponse,
    SourcesListResponse,
    SourceUpdateRequest,
    Tag,
    TagsListResponse,
    WatchlistFilter,
    WatchlistFiltersPayload,
    WatchlistOutput,
    WatchlistOutputCreateRequest,
    WatchlistOutputsListResponse,
    WatchlistTemplateCreateRequest,
    WatchlistTemplateDetail,
    WatchlistTemplateListResponse,
    WatchlistTemplateSummary,
    WatchlistTemplateValidationErrorResponse,
    WatchlistTemplateVersionsResponse,
    WatchlistTemplateVersionSummary,
)

_WATCHLISTS_NONCRITICAL_EXCEPTIONS = (
    asyncio.CancelledError,
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    csv.Error,
    json.JSONDecodeError,
    re.error,
    sqlite3.Error,
    HTTPException,
)

router = APIRouter(prefix="/watchlists", tags=["watchlists"])

DEFAULT_OUTPUT_TTL_SECONDS = int(os.getenv("WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS", "0") or 0)
TEMP_OUTPUT_TTL_SECONDS = int(os.getenv("WATCHLIST_OUTPUT_TEMP_TTL_SECONDS", "86400") or 86400)
DEFAULT_TTS_BRIEF_MAX_ITEMS = int(os.getenv("WATCHLIST_OUTPUT_TTS_BRIEF_MAX_ITEMS", "10") or 10)

_TEMPLATE_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(expires_at).astimezone(timezone.utc) <= datetime.now(timezone.utc)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return False


def _normalize_filters_payload(raw_json: str | None) -> dict[str, Any] | None:
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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return None
    return None


def _normalize_output_prefs(raw_json: str | None) -> dict[str, Any]:
    if not raw_json:
        return {}
    try:
        data = json.loads(raw_json)
        return data if isinstance(data, dict) else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return {}


def _merge_output_prefs(
    base: dict[str, Any] | None,
    ingest_prefs: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base or {})
    if ingest_prefs is not None:
        merged["ingest"] = ingest_prefs
    return merged


# ---- Helpers ----
_EMAIL_TAG_RE = re.compile(r"<[^>]+>")


def _safe_int(value: Any, fallback: int) -> int:
    try:
        if value is None:
            return fallback
        return int(value)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return fallback


def _safe_float(
    value: Any,
    fallback: float | None = None,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    try:
        if value is None:
            return fallback
        parsed = float(value)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return fallback
    if minimum is not None and parsed < minimum:
        return fallback
    if maximum is not None and parsed > maximum:
        return fallback
    return parsed


def _deep_merge_dict(base: dict[str, Any] | None, override: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = dict(base or {})
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _get_group_ids(db, source_id: int) -> list[int]:
    """Fetch group IDs for a source, returning [] on failure."""
    try:
        return db.get_source_group_ids(source_id)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return []


def _is_truthy_env(raw: str | None) -> bool:
    if raw is None:
        return False
    return _is_truthy(raw.strip())


def _watchlists_runs_require_admin() -> bool:
    explicit = os.getenv("WATCHLISTS_RUNS_REQUIRE_ADMIN")
    if explicit is not None:
        return _is_truthy_env(explicit)
    # Keep parity with existing frontend toggle if backend-specific flag is absent.
    return _is_truthy_env(os.getenv("NEXT_PUBLIC_RUNS_REQUIRE_ADMIN"))


def _normalize_claim_values(raw: Any) -> list[str]:
    values = raw if isinstance(raw, (list, tuple, set)) else ([raw] if raw is not None else [])
    out: list[str] = []
    for value in values:
        text = str(value).strip().lower()
        if text:
            out.append(text)
    return out


def _is_runs_admin_user(current_user: User) -> bool:
    """
    Determine admin authorization from explicit claims only.

    Legacy profile booleans/columns like ``is_superuser`` and ``role`` are
    intentionally ignored for runs-gated and cross-user watchlists paths.
    """
    try:
        if bool(getattr(current_user, "is_admin", False)):
            return True
        if "admin" in _normalize_claim_values(getattr(current_user, "roles", [])):
            return True
        permission_values = _normalize_claim_values(getattr(current_user, "permissions", []))
        if "admin" in permission_values:
            return True
        if "*" in permission_values:
            return True
        if "system.configure" in permission_values:
            return True
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return False
    return False


def _enforce_runs_admin_if_configured(current_user: User) -> None:
    if not _watchlists_runs_require_admin():
        return
    if _is_runs_admin_user(current_user):
        return
    raise HTTPException(status_code=403, detail="watchlists_runs_admin_required")


def _watchlists_sharing_mode() -> str:
    """Resolve sharing policy for cross-user watchlists access.

    Supported values:
    - private_only: disallow cross-user access
    - admin_same_org: allow admin cross-user access only for users that share an org
    - admin_cross_user (default): allow admin-only cross-user access
    """
    raw = str(os.getenv("WATCHLIST_SHARING_MODE", "admin_cross_user") or "").strip().lower()
    normalized = raw.replace("-", "_")
    if normalized in {"private", "private_only", "none", "disabled"}:
        return "private_only"
    if normalized in {"admin_same_org", "admin_same_tenant", "org_scoped"}:
        return "admin_same_org"
    if normalized in {"admin", "admin_only", "admin_cross_user"}:
        return "admin_cross_user"
    return "admin_cross_user"


async def _resolve_user_org_ids(user_id: int) -> set[int]:
    """Resolve org membership IDs for a user (best-effort)."""
    try:
        from tldw_Server_API.app.core.AuthNZ.orgs_teams import list_org_memberships_for_user

        memberships = await list_org_memberships_for_user(int(user_id))
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return set()

    out: set[int] = set()
    for entry in memberships or []:
        try:
            org_id = int((entry or {}).get("org_id"))
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            continue
        if org_id > 0:
            out.add(org_id)
    return out


async def _resolve_target_watchlists_user_id(current_user: User, target_user_id: int | None) -> int:
    current_user_id = _safe_int(getattr(current_user, "id", None), -1)
    if current_user_id <= 0:
        raise HTTPException(status_code=500, detail="watchlists_invalid_user")
    if target_user_id is None or int(target_user_id) == current_user_id:
        return current_user_id
    sharing_mode = _watchlists_sharing_mode()
    if sharing_mode == "private_only":
        raise HTTPException(status_code=403, detail="watchlists_private_only_mode")
    if not _is_runs_admin_user(current_user):
        raise HTTPException(status_code=403, detail="watchlists_admin_required_for_target_user")
    resolved_target = int(target_user_id)
    if sharing_mode == "admin_same_org":
        actor_org_ids = await _resolve_user_org_ids(current_user_id)
        target_org_ids = await _resolve_user_org_ids(resolved_target)
        if not actor_org_ids or not target_org_ids or actor_org_ids.isdisjoint(target_org_ids):
            raise HTTPException(status_code=403, detail="watchlists_admin_same_org_required")
    return resolved_target


def _resolve_watchlists_db_for_target_user(
    current_user: User,
    current_db: WatchlistsDatabase,
    target_user_id: int,
) -> WatchlistsDatabase:
    current_user_id = _safe_int(getattr(current_user, "id", None), -1)
    if target_user_id == current_user_id:
        return current_db
    try:
        db = WatchlistsDatabase.for_user(target_user_id)
        db.ensure_schema()
        return db
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"watchlists.resolve_target_db failed for user={target_user_id}: {exc}")
        raise HTTPException(status_code=500, detail="watchlists_db_unavailable") from exc


async def _resolve_target_watchlists_context(
    *,
    current_user: User,
    current_db: WatchlistsDatabase,
    target_user_id: int | None,
) -> tuple[int, WatchlistsDatabase]:
    resolved_user_id = await _resolve_target_watchlists_user_id(current_user, target_user_id)
    target_db = _resolve_watchlists_db_for_target_user(current_user, current_db, resolved_user_id)
    return resolved_user_id, target_db


def _build_email_bodies(content: str | None, fmt: str, title: str, preferred: str = "auto") -> tuple[str, str]:
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


def _normalize_tz(tz: str | None) -> str:
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            return "UTC"
    return tz


def _compute_next_run(cron: str | None, timezone: str | None) -> str | None:
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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return None


def _row_to_scraped_item(row) -> ScrapedItem:
    tags: list[str] = []
    try:
        tags = row.tags()
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        raw = getattr(row, "tags_json", None)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    tags = [str(t) for t in data if isinstance(t, str)]
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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


def _parse_output_metadata(row) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if hasattr(row, "metadata"):
        try:
            metadata = row.metadata()
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            metadata = {}
    if not metadata:
        raw = getattr(row, "metadata_json", None)
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    metadata = data
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                metadata = {}
    return metadata if isinstance(metadata, dict) else {}


def _load_output_content(user_id: int, row) -> str | None:
    storage_path = getattr(row, "storage_path", None)
    if not storage_path:
        return None
    if str(getattr(row, "format", "")).lower() == "mp3":
        return None
    try:
        path = _resolve_output_path_for_user(user_id, storage_path)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return None
    try:
        return path.read_text(encoding="utf-8")
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return None


def _row_to_output(row, *, user_id: int | None = None, content_override: str | None = None) -> WatchlistOutput:
    metadata = _parse_output_metadata(row)
    version = metadata.get("version")
    try:
        version = int(version) if version is not None else 1
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        version = 1
    expires_at = metadata.get("expires_at") if isinstance(metadata, dict) else None
    content = content_override
    if content is None and user_id is not None:
        content = _load_output_content(user_id, row)
    return WatchlistOutput(
        id=row.id,
        run_id=int(row.run_id or 0),
        job_id=int(row.job_id or 0),
        type=row.type,
        format=row.format,
        title=getattr(row, "title", None),
        content=content,
        storage_path=getattr(row, "storage_path", None),
        metadata=metadata,
        media_item_id=getattr(row, "media_item_id", None),
        chatbook_path=getattr(row, "chatbook_path", None),
        version=version,
        expires_at=expires_at,
        expired=_is_expired(expires_at),
        created_at=row.created_at,
    )


def _items_to_markdown_lines(items: list[ScrapedItem]) -> list[str]:
    lines: list[str] = []
    for idx, itm in enumerate(items, 1):
        entry_title = itm.title or f"Item {idx}"
        line = f"{idx}. [{entry_title}]({itm.url})" if itm.url else f"{idx}. {entry_title}"
        if itm.summary:
            line += f" - {itm.summary}"
        lines.append(line)
    return lines


def _items_to_html_entries(items: list[ScrapedItem]) -> list[str]:
    entries: list[str] = []
    for idx, itm in enumerate(items, 1):
        title_text = escape(itm.title or f"Item {idx}")
        summary_text = escape(itm.summary or "")
        url = itm.url
        entry = f'<li><a href="{escape(url)}">{title_text}</a>' if url else f"<li>{title_text}"
        if summary_text:
            entry += f" - {summary_text}"
        entry += "</li>"
        entries.append(entry)
    return entries


def _render_default_markdown(title: str, items: list[ScrapedItem]) -> str:
    lines = [f"# {title}", ""]
    lines.extend(_items_to_markdown_lines(items))
    return "\n".join(lines)


def _render_default_html(title: str, items: list[ScrapedItem]) -> str:
    body_parts = [f"<h1>{escape(title)}</h1>", "<ol>"]
    body_parts.extend(_items_to_html_entries(items))
    body_parts.append("</ol>")
    return "\n".join(body_parts)


def _job_payload(job_row: Any) -> dict[str, Any]:
    scope = {}
    try:
        scope = json.loads(job_row.scope_json or "{}") if getattr(job_row, "scope_json", None) else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        scope = {}
    retry_policy = {}
    try:
        retry_policy = (
            json.loads(job_row.retry_policy_json or "{}") if getattr(job_row, "retry_policy_json", None) else {}
        )
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        retry_policy = {}
    output_prefs = {}
    try:
        output_prefs = (
            json.loads(job_row.output_prefs_json or "{}") if getattr(job_row, "output_prefs_json", None) else {}
        )
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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


def _run_payload(run_row: Any) -> dict[str, Any]:
    stats = {}
    try:
        stats = json.loads(run_row.stats_json or "{}") if getattr(run_row, "stats_json", None) else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
    items: list[ScrapedItem],
) -> dict[str, Any]:
    markdown_lines = _items_to_markdown_lines(items)
    html_entries = _items_to_html_entries(items)
    items_payload: list[dict[str, Any]] = []
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


def _render_template_with_context(template_str: str, context: dict[str, Any]) -> str:
    return render_output_template(template_str, context)


def _next_output_version_for_run(collections_db, run_id: int) -> int:
    try:
        max_version = 0
        limit = 200
        offset = 0
        while True:
            rows, _ = collections_db.list_output_artifacts(run_id=run_id, limit=limit, offset=offset)
            if not rows:
                break
            for row in rows:
                metadata = _parse_output_metadata(row)
                version = metadata.get("version")
                try:
                    version_val = int(version)
                except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                    continue
                if version_val > max_version:
                    max_version = version_val
            if len(rows) < limit:
                break
            offset += limit
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return 1
    return max_version + 1 if max_version > 0 else 1


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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return False


def _is_youtube_feed_url(url: str) -> bool:
    """Accept only canonical YouTube RSS feed URLs.

    Allowed forms:
      - https://www.youtube.com/feeds/videos.xml?channel_id=...
      - https://www.youtube.com/feeds/videos.xml?playlist_id=...
      - https://www.youtube.com/feeds/videos.xml?user=...
    """
    try:
        from urllib.parse import parse_qs, urlparse
        u = urlparse(url)
        path_ok = u.path.lower().startswith("/feeds/videos.xml")
        if not path_ok:
            return False
        raw_qs = parse_qs(u.query or "")
        # Treat query keys case-insensitively (CHANNEL_ID, LIST, USER, etc.)
        qs = {str(k).lower(): v for k, v in raw_qs.items()}
        return any(k in qs for k in ("channel_id", "playlist_id", "user"))
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return False


def _normalize_youtube_feed_url(url: str) -> str | None:
    """Attempt to normalize some YouTube URLs to canonical feed URLs.

    Supports channel, playlist, and user URL forms. Other forms are not normalized.
    """
    try:
        from urllib.parse import parse_qs, urlparse
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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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


def _forums_enabled() -> bool:
    return _is_truthy(os.getenv("WATCHLIST_FORUMS_ENABLED", ""))


def _forum_default_top_n() -> int:
    """Default number of forum links to probe when no explicit top_n is set."""
    parsed = _safe_int(os.getenv("WATCHLIST_FORUM_DEFAULT_TOP_N"), 20)
    if parsed <= 0:
        return 20
    # Keep this aligned with preview/source test limits.
    return min(parsed, 200)


def _raise_if_forum_disabled(source_type: str) -> None:
    if str(source_type).lower() == "forum" and not _forums_enabled():
        raise HTTPException(status_code=400, detail="forum_sources_disabled")


def _validate_group_ids(db: WatchlistsDatabase, group_ids: list[int] | None) -> list[int]:
    if not group_ids:
        return []
    clean: list[int] = []
    missing: list[int] = []
    for gid in group_ids:
        try:
            gid_int = int(gid)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"watchlists.group_ids: invalid group id {gid}: {exc}")
            raise HTTPException(status_code=400, detail="group_validation_failed") from exc
        try:
            db.get_group(gid_int)
        except KeyError:
            missing.append(gid_int)
        else:
            clean.append(gid_int)
    if missing:
        raise HTTPException(status_code=400, detail=f"group_not_found: {missing}")
    return clean


def _looks_like_jwt(token: str | None) -> bool:
    return isinstance(token, str) and token.count(".") == 2


async def _resolve_watchlists_ws_user_id(
    websocket: WebSocket,
    *,
    token: str | None,
    api_key: str | None,
) -> int:
    if not token:
        auth_hdr = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_hdr and auth_hdr.lower().startswith("bearer "):
            token = auth_hdr.split(" ", 1)[1].strip()
    if not api_key:
        api_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-API-KEY")

    if token and not api_key and not _looks_like_jwt(token):
        api_key = token
        token = None

    if token:
        try:
            from tldw_Server_API.app.core.AuthNZ.exceptions import InvalidTokenError, TokenExpiredError
            from tldw_Server_API.app.core.AuthNZ.jwt_service import get_jwt_service
            from tldw_Server_API.app.core.AuthNZ.session_manager import get_session_manager

            jwt_service = get_jwt_service()
            payload = await jwt_service.verify_token_async(token, token_type="access")
            session_manager = await get_session_manager()
            if await session_manager.is_token_blacklisted(token, payload.get("jti")):
                raise HTTPException(status_code=401, detail="invalid_token")
        except HTTPException:
            raise
        except (InvalidTokenError, TokenExpiredError):
            raise HTTPException(status_code=401, detail="invalid_token") from None
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            raise HTTPException(status_code=401, detail="invalid_token") from None

        sub = payload.get("user_id") or payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=401, detail="invalid_token")
        try:
            return int(sub)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            raise HTTPException(status_code=401, detail="invalid_token") from None

    if api_key:
        settings = get_settings()
        client_ip = resolve_client_ip(websocket, settings)
        if getattr(settings, "AUTH_MODE", None) == "single_user":
            allowed_keys: set[str] = set()
            primary_key = getattr(settings, "SINGLE_USER_API_KEY", None)
            if primary_key:
                allowed_keys.add(primary_key)
            test_key = os.getenv("SINGLE_USER_TEST_API_KEY")
            if test_key:
                allowed_keys.add(test_key)
            if api_key in allowed_keys and is_single_user_ip_allowed(client_ip, settings):
                return int(getattr(settings, "SINGLE_USER_FIXED_ID", 1))
            raise HTTPException(status_code=401, detail="invalid_api_key")

        api_mgr = await get_api_key_manager()
        info = await api_mgr.validate_api_key(api_key=api_key, required_scope="read", ip_address=client_ip)
        if not info:
            raise HTTPException(status_code=401, detail="invalid_api_key")
        user_id = info.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="invalid_api_key")
        return int(user_id)

    raise HTTPException(status_code=401, detail="auth_required")


def _resolve_watchlist_log_path(*, user_id: int, log_path: str | None) -> Path | None:
    if not log_path:
        return None
    try:
        base_dir = DatabasePaths.get_user_base_directory(user_id)
        try:
            base_resolved = base_dir.resolve(strict=False)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            base_resolved = base_dir
        candidate = Path(log_path)
        if not candidate.is_absolute():
            candidate = base_resolved / candidate
        try:
            candidate_resolved = candidate.resolve(strict=False)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            candidate_resolved = candidate
        try:
            candidate_resolved.relative_to(base_resolved)
        except ValueError:
            logger.warning("watchlists: log path outside user base dir: %s", candidate_resolved)
            return None
        return candidate_resolved
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        logger.debug("watchlists: log path resolve failed: %s", exc)
        return None


def _read_log_chunk(
    *,
    log_path: str | None,
    user_id: int,
    offset: int,
    max_bytes: int,
    inode: int | None,
) -> tuple[str | None, int, int | None]:
    if not log_path:
        return None, offset, inode
    try:
        path = _resolve_watchlist_log_path(user_id=user_id, log_path=log_path)
        if path is None:
            return None, offset, inode
        if not path.exists():
            return None, offset, inode
        stat = path.stat()
        current_inode = getattr(stat, "st_ino", None)
        if inode is not None and current_inode is not None and inode != current_inode:
            offset = 0
        if stat.st_size < offset:
            offset = 0
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            chunk = fh.read(max_bytes)
            offset = fh.tell()
        if not chunk:
            return None, offset, current_inode
        return chunk, offset, current_inode
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return None, offset, inode


def _read_log_tail(
    *,
    log_path: str | None,
    user_id: int,
    max_bytes: int,
) -> tuple[str | None, int, int | None, bool]:
    if not log_path:
        return None, 0, None, False
    try:
        path = _resolve_watchlist_log_path(user_id=user_id, log_path=log_path)
        if path is None:
            return None, 0, None, False
        if not path.exists():
            return None, 0, None, False
        stat = path.stat()
        inode = getattr(stat, "st_ino", None)
        start = 0
        truncated = False
        if stat.st_size > max_bytes:
            start = max(0, stat.st_size - max_bytes)
            truncated = True
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(start)
            text = fh.read(max_bytes)
            offset = fh.tell()
        if not text:
            return None, offset, inode, truncated
        return text, offset, inode, truncated
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        return None, 0, None, False

@router.post("/sources", response_model=Source, summary="Create a source")
async def create_source(
    payload: SourceCreateRequest = Body(...),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    try:
        _raise_if_forum_disabled(str(payload.source_type))
        group_ids: list[int] | None = payload.group_ids
        if group_ids is not None:
            group_ids = _validate_group_ids(db, group_ids)
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
                except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                    pass
                with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
                    logger.debug(f"watchlists.create_source: normalized YouTube URL {orig_url_for_log} -> {url_str}")
            else:
                _validate_youtube_feed_or_raise(url_str, str(payload.source_type))
        row = db.create_source(
            name=payload.name,
            url=url_str,
            source_type=str(payload.source_type),
            active=payload.active,
            settings_json=(json.dumps(payload.settings) if payload.settings else None),
            tags=payload.tags or [],
            group_ids=group_ids or [],
        )
        # Ensure tags reflect payload even when source pre-exists (idempotent create)
        if payload.tags is not None:
            try:
                tags = db.set_source_tags(row.id, payload.tags)
                row.tags = tags  # type: ignore[attr-defined]
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                pass
        if payload.group_ids is not None:
            with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
                db.set_source_groups(row.id, group_ids or [])
    except HTTPException:
        # Propagate validation/HTTP errors unchanged
        raise
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"create_source failed: {e}")
        raise HTTPException(status_code=400, detail="source_create_failed") from e
    return Source(
        id=row.id,
        name=row.name,
        url=row.url,
        source_type=row.source_type,  # type: ignore[assignment]
        active=bool(row.active),
        tags=row.tags,
        group_ids=_get_group_ids(db, row.id),
        settings=(json.loads(row.settings_json) if row.settings_json else None),
        last_scraped_at=row.last_scraped_at,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("/sources", response_model=SourcesListResponse, summary="List sources")
async def list_sources(
    q: str | None = Query(None),
    tags: list[str] | None = Query(None, description="Filter by tag names (AND semantics)"),
    groups: list[int] | None = Query(None, description="Filter by group IDs (OR semantics)"),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: list sources for another user ID.",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    limit = size
    offset = (page - 1) * limit
    rows, total = target_db.list_sources(q=q, tag_names=tags, limit=limit, offset=offset, group_ids=groups)
    # Batch-fetch group IDs to avoid N+1
    source_ids = [int(r.id) for r in rows]
    try:
        groups_map = target_db.get_source_group_ids_batch(source_ids) if source_ids else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        groups_map = {}
    items: list[Source] = []
    for r in rows:
        items.append(
            Source(
                id=r.id,
                name=r.name,
                url=r.url,
                source_type=r.source_type,  # type: ignore[assignment]
                active=bool(r.active),
                tags=r.tags,
                group_ids=groups_map.get(int(r.id), []),
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
    tag: list[str] | None = Query(None, description="Filter by tag(s)"),
    group: list[int] | None = Query(None, description="Filter by group id(s) (OR semantics)"),
    type: str | None = Query(None, description="Filter by source_type (rss/site/forum)"),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: export sources for another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    # Base selection
    if group:
        try:
            rows = target_db.list_sources_by_group_ids([int(g) for g in group])
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            rows = []
        # Apply tag filter manually (AND semantics)
        if tag:
            needed = [t.strip().lower() for t in tag if t and str(t).strip()]
            def _has_all_tags(src) -> bool:
                src_tags = [str(t).strip().lower() for t in (getattr(src, "tags", []) or [])]
                return all(n in src_tags for n in needed)
            rows = [r for r in rows if _has_all_tags(r)]
    else:
        rows, _ = target_db.list_sources(q=None, tag_names=tag, limit=10000, offset=0)
    # Build OPML items (rss sources only)
    items: list[dict[str, Any]] = []
    for r in rows:
        if type and str(r.source_type).lower() != type.lower():
            continue
        if str(r.source_type).lower() != "rss":
            continue
        items.append({"name": r.name, "url": r.url, "html_url": None})
    xml = generate_opml(items)
    return Response(content=xml, media_type="application/xml")


@router.post("/sources/import", response_model=SourcesImportResponse, summary="Import sources from OPML")
async def import_sources_opml(
    request: Request,
    file: UploadFile = File(...),
    active: bool = Form(True),
    tags: list[str] | None = Form(None),
    group_id: int | None = Form(None),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    content = await file.read()
    entries = parse_opml(content)
    if group_id is not None:
        _validate_group_ids(db, [group_id])
    items: list[SourcesImportItem] = []
    created = skipped = errors = 0
    default_tags = tags or []
    for e in entries:
        if not e.url:
            items.append(SourcesImportItem(url="", name=e.name, status="error", error="missing_url"))
            errors += 1
            continue
        url_str = e.url
        if _is_youtube_url(url_str) and not _is_youtube_feed_url(url_str):
            normalized = _normalize_youtube_feed_url(url_str)
            if normalized:
                url_str = normalized
            else:
                items.append(SourcesImportItem(url=e.url, name=e.name, status="error", error="invalid_youtube_rss_url"))
                errors += 1
                continue
        try:
            row = db.create_source(
                name=e.name or e.url,
                url=url_str,
                source_type="rss",
                active=bool(active),
                settings_json=None,
                tags=default_tags,
                group_ids=([group_id] if group_id else []),
            )
            items.append(SourcesImportItem(url=url_str, name=row.name, id=row.id, status="created"))
            created += 1
        except (*_WATCHLISTS_NONCRITICAL_EXCEPTIONS, _DatabaseError) as exc:
            items.append(SourcesImportItem(url=url_str, name=e.name, status="skipped", error=str(exc)))
            skipped += 1
    return SourcesImportResponse(items=items, total=(created + skipped + errors), created=created, skipped=skipped, errors=errors)

# (moved above /sources/{source_id})


@router.get("/sources/{source_id}", response_model=Source, summary="Get source")
async def get_source(
    source_id: int = Path(..., ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: fetch a source from another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    try:
        r = target_db.get_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found") from None
    return Source(
        id=r.id,
        name=r.name,
        url=r.url,
        source_type=r.source_type,  # type: ignore[assignment]
        active=bool(r.active),
        tags=r.tags,
        group_ids=_get_group_ids(target_db, r.id),
        settings=(json.loads(r.settings_json) if r.settings_json else None),
        last_scraped_at=r.last_scraped_at,
        status=r.status,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


@router.get(
    "/sources/{source_id}/seen",
    response_model=SourceSeenStats,
    summary="Get per-source dedup/seen state",
)
async def get_source_seen_stats(
    source_id: int = Path(..., ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: inspect seen state for another user ID.",
    ),
    keys_limit: int = Query(
        0,
        ge=0,
        le=200,
        description="Include up to N recent seen keys (0 disables key list).",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    resolved_user_id = await _resolve_target_watchlists_user_id(current_user, target_user_id)
    target_db = _resolve_watchlists_db_for_target_user(current_user, db, resolved_user_id)
    try:
        src = target_db.get_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found") from None
    stats = target_db.get_seen_item_stats(source_id)
    recent_keys: list[str] = []
    if keys_limit > 0:
        recent_keys = target_db.list_seen_item_keys(source_id, limit=keys_limit)
    return SourceSeenStats(
        source_id=int(source_id),
        user_id=int(resolved_user_id),
        seen_count=int(stats.get("seen_count") or 0),
        latest_seen_at=stats.get("latest_seen_at"),
        defer_until=getattr(src, "defer_until", None),
        consec_not_modified=getattr(src, "consec_not_modified", None),
        recent_keys=recent_keys,
    )


@router.delete(
    "/sources/{source_id}/seen",
    response_model=SourceSeenResetResponse,
    summary="Clear per-source dedup/seen state",
)
async def clear_source_seen_state(
    source_id: int = Path(..., ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: clear seen state for another user ID.",
    ),
    clear_backoff: bool = Query(
        True,
        description="Also clear source defer/backoff state when true.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    resolved_user_id = await _resolve_target_watchlists_user_id(current_user, target_user_id)
    target_db = _resolve_watchlists_db_for_target_user(current_user, db, resolved_user_id)
    try:
        target_db.get_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found") from None
    cleared = target_db.clear_seen_items(source_id)
    cleared_backoff = False
    if clear_backoff:
        cleared_backoff = target_db.reset_source_backoff_state(source_id)
    return SourceSeenResetResponse(
        source_id=int(source_id),
        user_id=int(resolved_user_id),
        cleared=int(cleared),
        cleared_backoff=bool(cleared_backoff),
    )


@router.post("/sources/{source_id}/test", response_model=PreviewResponse, summary="Test source and preview items")
async def test_source(
    source_id: int = Path(..., ge=1),
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        src = db.get_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source_not_found") from None

    source_type = str(getattr(src, "source_type", ""))
    _raise_if_forum_disabled(source_type)
    settings: dict[str, Any] = {}
    try:
        settings = json.loads(src.settings_json or "{}") if getattr(src, "settings_json", None) else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        settings = {}

    items: list[dict[str, Any]] = []
    test_mode = _is_test_mode()

    if source_type.lower() == "rss":
        try:
            res = await fetch_rss_feed(
                str(src.url),
                etag=getattr(src, "etag", None),
                last_modified=getattr(src, "last_modified", None),
                tenant_id="default",
            )
            items = res.get("items", []) if isinstance(res, dict) else []
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"watchlists.test_source: rss fetch failed: {exc}")
            items = []
    elif source_type.lower() in {"site", "forum"}:
        scrape_rules = settings.get("scrape_rules") if isinstance(settings.get("scrape_rules"), dict) else None
        if scrape_rules:
            try:
                items = await fetch_site_items_with_rules(
                    base_url=str(scrape_rules.get("list_url") or src.url),
                    rules=scrape_rules,
                    tenant_id="default",
                )
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"watchlists.test_source: scrape rules fetch failed: {exc}")
                items = []
        elif test_mode:
            items = [
                {
                    "title": "Test scraped item 1",
                    "url": f"{str(src.url).rstrip('/')}/test-item-1",
                    "summary": "Test summary from source preview.",
                }
            ]
        else:
            try:
                from tldw_Server_API.app.core.Watchlists.fetchers import fetch_site_top_links

                default_top_n = _forum_default_top_n() if source_type.lower() == "forum" else 1
                top_n = int(settings.get("top_n", default_top_n) or default_top_n)
                discover_method = str(settings.get("discover_method", "auto")).lower()
                urls = await fetch_site_top_links(str(src.url), top_n=top_n, method=discover_method)
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                urls = [str(src.url)]
            items = [{"url": url} for url in (urls or [])]

    if limit and limit > 0:
        items = items[:limit]

    preview_items: list[PreviewItem] = []
    for entry in items:
        preview_items.append(
            PreviewItem(
                source_id=int(source_id),
                source_type=source_type,  # type: ignore[arg-type]
                url=entry.get("url"),
                title=entry.get("title"),
                summary=entry.get("summary"),
                published_at=entry.get("published") or entry.get("published_at"),
                decision="ingest",
                matched_action=None,
                matched_filter_key=None,
                matched_filter_id=None,
                matched_filter_type=None,
                flagged=False,
            )
        )

    total = len(preview_items)
    return PreviewResponse(items=preview_items, total=total, ingestable=total, filtered=0)


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
        raise HTTPException(status_code=404, detail="source_not_found") from None
    target_type = str(payload.source_type) if (getattr(payload, "source_type", None) is not None) else str(existing.source_type)
    target_url = str(payload.url) if (getattr(payload, "url", None) is not None) else str(existing.url)
    _raise_if_forum_disabled(target_type)
    # Normalize/validate when target_type is rss and URL is YouTube
    if target_type.lower() == "rss" and _is_youtube_url(target_url) and not _is_youtube_feed_url(target_url):
        orig_url_for_log = target_url
        normalized = _normalize_youtube_feed_url(target_url)
        if normalized:
            target_url = normalized
            if payload.url is not None:
                try:
                    payload.url = type(payload.url)(target_url)  # type: ignore[call-arg]
                except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                    pass
            try:
                if response is not None:
                    response.headers["X-YouTube-Normalized"] = "1"
                    response.headers["X-YouTube-Canonical-URL"] = target_url
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                pass
            with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
                logger.debug(f"watchlists.update_source: normalized YouTube URL {orig_url_for_log} -> {target_url}")
        else:
            _validate_youtube_feed_or_raise(target_url, target_type)
    patch = payload.model_dump(exclude_unset=True)
    group_ids = patch.pop("group_ids", None)
    if group_ids is not None:
        group_ids = _validate_group_ids(db, group_ids)
    if "settings" in patch:
        patch["settings_json"] = json.dumps(patch.pop("settings")) if patch.get("settings") is not None else None
    # Coerce pydantic types to primitives for DB layer
    if "url" in patch and patch["url"] is not None:
        with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
            patch["url"] = str(patch["url"])
    row = db.update_source(source_id, patch)
    # tags replacement
    if payload.tags is not None:
        try:
            tags = db.set_source_tags(source_id, payload.tags)
            row.tags = tags  # type: ignore[attr-defined]
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            pass
    if group_ids is not None:
        try:
            db.set_source_groups(source_id, group_ids)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            logger.exception(
                "watchlists.update_source: failed to set source groups "
                f"(source_id={source_id}, group_ids={group_ids})"
            )
    return Source(
        id=row.id,
        name=row.name,
        url=row.url,
        source_type=row.source_type,  # type: ignore[assignment]
        active=bool(row.active),
        tags=getattr(row, "tags", []),
        group_ids=_get_group_ids(db, row.id),
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
    items: list[SourcesBulkCreateItem] = []
    created_count = 0
    errors_count = 0
    for s in payload.sources:
        try:
            _raise_if_forum_disabled(str(s.source_type))
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
        # Normalize/Validate YouTube-as-RSS for each entry; collect per-entry error instead of silent skip
        try:
            url_str = str(s.url)
            if str(s.source_type).lower() == "rss" and _is_youtube_url(url_str) and not _is_youtube_feed_url(url_str):
                normalized = _normalize_youtube_feed_url(url_str)
                if normalized:
                    url_str = normalized
                    with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
                        logger.debug(f"watchlists.bulk_create_sources: normalized YouTube URL {s.url} -> {url_str}")
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"bulk_create_sources: tag validation error for {s.name}: {exc}")
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
            if s.group_ids is not None:
                _validate_group_ids(db, s.group_ids)
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"bulk_create_sources: group validation error for {s.name}: {exc}")
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
                url=url_str,
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as e:
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
    q: str | None = Query(None),
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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        raise HTTPException(status_code=400, detail="group_create_failed") from None
    return Group(id=row.id, name=row.name, description=row.description, parent_group_id=row.parent_group_id)


@router.get("/groups", response_model=GroupsListResponse, summary="List groups")
async def list_groups(
    q: str | None = Query(None),
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
        raise HTTPException(status_code=404, detail="group_not_found") from None
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
    db = Depends(get_watchlists_db_for_user),
):
    backend_label = "sqlite"
    backend_type = getattr(getattr(db, "backend", None), "backend_type", None)
    backend_name = str(getattr(backend_type, "name", "") or "").lower()
    if "postgres" in backend_name:
        backend_label = "postgres"
    return {
        "default_output_ttl_seconds": DEFAULT_OUTPUT_TTL_SECONDS,
        "temporary_output_ttl_seconds": TEMP_OUTPUT_TTL_SECONDS,
        "forums_enabled": _forums_enabled(),
        "forum_default_top_n": _forum_default_top_n(),
        "sharing_mode": _watchlists_sharing_mode(),
        "watchlists_backend": backend_label,
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            jf_json = None
        ingest_prefs = payload.ingest_prefs.model_dump(exclude_none=True) if payload.ingest_prefs else None
        output_prefs = _merge_output_prefs(payload.output_prefs or {}, ingest_prefs)
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
            output_prefs_json=json.dumps(output_prefs),
            job_filters_json=jf_json,
        )
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"create_job failed: {e}")
        raise HTTPException(status_code=400, detail="job_create_failed") from e
    # Compute and persist next_run_at; register with workflows scheduler
    try:
        next_run = _compute_next_run(row.schedule_expr, row.schedule_timezone)
        if next_run:
            db.set_job_history(row.id, next_run_at=next_run)
            row = db.get_job(row.id)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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

    output_prefs = _normalize_output_prefs(getattr(row, "output_prefs_json", None))
    ingest_prefs = output_prefs.get("ingest") if isinstance(output_prefs, dict) else None
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
        output_prefs=output_prefs,
        ingest_prefs=ingest_prefs,
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
        raise HTTPException(status_code=404, detail="job_not_found") from None

    # Resolve sources for job scope (IDs, tags, groups)
    scope = {}
    try:
        scope = json.loads(job.scope_json or "{}") if job.scope_json else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        scope = {}

    selected: dict[int, Any] = {}
    for sid in map(int, scope.get("sources", []) or []):
        try:
            r = db.get_source(sid)
            if int(r.active or 0) == 1:
                selected[int(r.id)] = r
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            pass
    sources = list(selected.values())

    # Load job filters and include-only gating default
    raw_filters = {}
    try:
        raw_filters = json.loads(job.job_filters_json or "{}") if getattr(job, "job_filters_json", None) else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            pass
        try:
            return _is_truthy(os.getenv("WATCHLISTS_REQUIRE_INCLUDE_DEFAULT", ""))
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            return False

    include_rules_exist = any((str(f.get("action")) == "include") for f in job_filters)
    job_require_include = None
    if isinstance(raw_filters, dict) and "require_include" in raw_filters:
        try:
            job_require_include = bool(raw_filters.get("require_include"))
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            job_require_include = None
    org_default = await _org_require_include_default()
    effective_require_include = job_require_include if (job_require_include is not None) else org_default
    include_gating_active = bool(effective_require_include and include_rules_exist)

    # Collect candidates
    items: list[PreviewItem] = []
    total_ingestable = 0
    total_filtered = 0
    test_mode = _is_test_mode()

    for src in sources:
        if len(items) >= limit:
            break
        per_items: list[dict[str, Any]] = []
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
                    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                        cfg = {}
                    per_items = await fetch_site_items_with_rules(str(src.url), rules=cfg.get("scrape_rules") or {})
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.debug(f"preview_job: fetch failed for source {src.id}: {exc}")
            per_items = []

        if per_items and len(per_items) > per_source:
            per_items = per_items[:per_source]

        for taken, it in enumerate(per_items):
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
            decision = "filtered" if action == "exclude" or include_gating_active and action != "include" else "ingest"
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
                    matched_filter_id=(
                        int(meta["id"])
                        if isinstance(meta, dict) and meta.get("id") is not None
                        else None
                    ),
                    matched_filter_type=(
                        meta.get("type")
                        if isinstance(meta, dict) and isinstance(meta.get("type"), str)
                        else None
                    ),  # type: ignore[arg-type]
                    flagged=flagged,
                )
            )

    return PreviewResponse(items=items, total=len(items), ingestable=total_ingestable, filtered=total_filtered)


@router.get("/jobs", response_model=JobsListResponse, summary="List jobs")
async def list_jobs(
    q: str | None = Query(None),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: list jobs for another user ID.",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    limit = size
    offset = (page - 1) * limit
    rows, total = target_db.list_jobs(q=q, limit=limit, offset=offset)
    items: list[Job] = []
    for r in rows:
        output_prefs = _normalize_output_prefs(getattr(r, "output_prefs_json", None))
        ingest_prefs = output_prefs.get("ingest") if isinstance(output_prefs, dict) else None
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
                output_prefs=output_prefs,
                ingest_prefs=ingest_prefs,
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
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: fetch a job from another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    try:
        r = target_db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found") from None
    is_admin = _is_runs_admin_user(current_user)
    output_prefs = _normalize_output_prefs(getattr(r, "output_prefs_json", None))
    ingest_prefs = output_prefs.get("ingest") if isinstance(output_prefs, dict) else None
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
        output_prefs=output_prefs,
        ingest_prefs=ingest_prefs,
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
    ingest_prefs = patch.pop("ingest_prefs", None)
    output_prefs = patch.pop("output_prefs", None) if "output_prefs" in patch else None
    if "scope" in patch:
        patch["scope_json"] = json.dumps(patch.pop("scope") or {})
    if "retry_policy" in patch:
        patch["retry_policy_json"] = json.dumps(patch.pop("retry_policy") or {})
    if "job_filters" in patch:
        patch["job_filters_json"] = json.dumps(patch.pop("job_filters") or {})
    if ingest_prefs is not None:
        if output_prefs is None:
            try:
                current = db.get_job(job_id)
                output_prefs = _normalize_output_prefs(getattr(current, "output_prefs_json", None))
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                output_prefs = {}
        output_prefs = _merge_output_prefs(output_prefs, ingest_prefs)
        patch["output_prefs_json"] = json.dumps(output_prefs)
    elif output_prefs is not None:
        patch["output_prefs_json"] = json.dumps(output_prefs or {})
    try:
        r = db.update_job(job_id, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found") from None
    # Update next_run_at if schedule changed
    try:
        if any(k in patch for k in ("schedule_expr", "schedule_timezone")):
            next_run = _compute_next_run(r.schedule_expr, r.schedule_timezone)
            db.set_job_history(job_id, next_run_at=next_run)
            r = db.get_job(job_id)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        pass
    # Sync with workflows scheduler (create/update/enable/disable)
    try:
        from tldw_Server_API.app.services.workflows_scheduler import get_workflows_scheduler
        svc = get_workflows_scheduler()
        if r.wf_schedule_id:
            upd: dict[str, Any] = {}
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
    output_prefs = _normalize_output_prefs(getattr(r, "output_prefs_json", None))
    ingest_prefs = output_prefs.get("ingest") if isinstance(output_prefs, dict) else None
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
        output_prefs=output_prefs,
        ingest_prefs=ingest_prefs,
        job_filters=_normalize_filters_payload(getattr(r, "job_filters_json", None)),
        created_at=r.created_at,
        updated_at=r.updated_at,
        last_run_at=r.last_run_at,
        next_run_at=r.next_run_at,
    )


@router.get("/{watchlist_id}/clusters", summary="List claim clusters for a watchlist")
async def list_watchlist_clusters(
    watchlist_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        db.get_job(watchlist_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="watchlist_not_found") from None
    rows = db.list_watchlist_clusters(watchlist_id)
    return {"watchlist_id": int(watchlist_id), "clusters": rows}


@router.post("/{watchlist_id}/clusters", summary="Subscribe watchlist to a claim cluster")
async def add_watchlist_cluster(
    watchlist_id: int = Path(..., ge=1),
    cluster_id: int = Body(..., embed=True, ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        db.get_job(watchlist_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="watchlist_not_found") from None
    db.add_watchlist_cluster(watchlist_id, cluster_id)
    return {"status": "added", "watchlist_id": int(watchlist_id), "cluster_id": int(cluster_id)}


@router.delete("/{watchlist_id}/clusters/{cluster_id}", summary="Unsubscribe watchlist from a claim cluster")
async def remove_watchlist_cluster(
    watchlist_id: int = Path(..., ge=1),
    cluster_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        db.get_job(watchlist_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="watchlist_not_found") from None
    removed = db.remove_watchlist_cluster(watchlist_id, cluster_id)
    if not removed:
        raise HTTPException(status_code=404, detail="cluster_subscription_not_found")
    return {"status": "removed", "watchlist_id": int(watchlist_id), "cluster_id": int(cluster_id)}


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
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        pass
    ok = db.delete_job(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="job_not_found")
    return {"success": True}


@router.patch("/jobs/{job_id}/filters", response_model=WatchlistFiltersPayload, summary="Replace job filters")
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
        raise HTTPException(status_code=404, detail="job_not_found") from None
    updated = db.set_job_filters(job_id, payload.model_dump())
    # Normalize and return
    try:
        parsed = json.loads(updated.job_filters_json or "{}") if getattr(updated, "job_filters_json", None) else {"filters": []}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        parsed = {"filters": []}
    return WatchlistFiltersPayload(**parsed) if isinstance(parsed, dict) else WatchlistFiltersPayload(filters=[])


@router.post("/jobs/{job_id}/filters:add", response_model=WatchlistFiltersPayload, summary="Append job filters")
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
        raise HTTPException(status_code=404, detail="job_not_found") from None
    existing = list(current.get("filters") or [])
    to_add = payload.filters or []
    new_filters = existing + [f.model_dump() if hasattr(f, "model_dump") else f for f in to_add]
    db.set_job_filters(job_id, {"filters": new_filters})
    return WatchlistFiltersPayload(filters=[WatchlistFilter(**f) if isinstance(f, dict) else f for f in new_filters])


@router.post(
    "/jobs/{job_id}/run",
    response_model=Run,
    summary="Trigger a run (executes pipeline)",
    dependencies=[Depends(rbac_rate_limit("watchlists.run"))],
)
async def trigger_run(
    job_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    try:
        # Ensure job exists before execution
        db.get_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found") from None

    try:
        result = await run_watchlist_job(int(current_user.id), job_id)
        run_id = int(result.get("run_id"))
        run = db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=500, detail="run_lookup_failed") from None
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as e:
        logger.error(f"trigger_run failed: {e}")
        raise HTTPException(status_code=500, detail="run_trigger_failed") from e
    stats_dict: dict[str, Any] | None = None
    try:
        stats_dict = json.loads(run.stats_json or "{}") if run.stats_json else None
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: list runs for another user ID.",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _enforce_runs_admin_if_configured(current_user)
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    limit = size
    offset = (page - 1) * limit
    rows, total = target_db.list_runs_for_job(job_id, limit=limit, offset=offset)
    items = [Run(id=r.id, job_id=r.job_id, status=r.status, started_at=r.started_at, finished_at=r.finished_at, stats=(json.loads(r.stats_json or "{}") if r.stats_json else None), error_msg=r.error_msg) for r in rows]
    has_more = (offset + len(items)) < int(total or 0)
    return RunsListResponse(items=items, total=total, has_more=has_more)


@router.get("/runs", response_model=RunsListResponse, summary="List runs across all jobs")
async def list_runs_global(
    q: str | None = Query(None, description="Filter by job name/description, run status, or run id (text)"),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: list runs for another user ID.",
    ),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _enforce_runs_admin_if_configured(current_user)
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    limit = size
    offset = (page - 1) * limit
    rows, total = target_db.list_runs(q=q, limit=limit, offset=offset)
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
    job_id: int | None = Query(None, ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: export runs for another user ID.",
    ),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(200, ge=1, le=1000),
    include_tallies: bool = Query(False, description="When true, include a filter_tallies_json column per row"),
    tallies_mode: Literal["per_run", "aggregate"] = Query(
        "per_run",
        description="Tallies export mode when include_tallies=true. Use 'aggregate' to export global filter-key totals.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _enforce_runs_admin_if_configured(current_user)
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    """Return a CSV export of runs with basic counters.

    Columns: id,job_id,status,started_at,finished_at,items_found,items_ingested,filters_include,filters_exclude,filters_flag
    """
    limit = size
    offset = (page - 1) * limit

    def _safe_parse_stats(raw_stats_json: str | None) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_stats_json or "{}") if raw_stats_json else {}
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            parsed = {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _safe_parse_filter_tallies(stats: dict[str, Any]) -> dict[str, int]:
        raw_tallies = stats.get("filter_tallies")
        if not isinstance(raw_tallies, dict):
            return {}
        tallies_out: dict[str, int] = {}
        for key, value in raw_tallies.items():
            key_text = str(key).strip()
            if not key_text:
                continue
            if isinstance(value, (int, float)):
                tallies_out[key_text] = int(value)
        return tallies_out

    if include_tallies and tallies_mode == "aggregate":
        if scope != "global":
            raise HTTPException(status_code=400, detail="tallies_aggregation_global_only")

        aggregate: dict[str, int] = {}
        scan_offset = 0
        scan_limit = 1000
        while True:
            scan_rows, _scan_total = target_db.list_runs(q=q, limit=scan_limit, offset=scan_offset)
            if not scan_rows:
                break
            for row in scan_rows:
                stats = _safe_parse_stats(row.stats_json)
                tallies = _safe_parse_filter_tallies(stats)
                for tally_key, tally_count in tallies.items():
                    aggregate[tally_key] = aggregate.get(tally_key, 0) + tally_count
            if len(scan_rows) < scan_limit:
                break
            scan_offset += len(scan_rows)

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["filter_key", "count"])
        for key, count in sorted(aggregate.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow([key, int(count)])
        filename = f"watchlists_runs_global_tallies_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
        return PlainTextResponse(
            output.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Has-More": "false",
            },
        )

    if scope == "job":
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id_required")
        rows, total = target_db.list_runs_for_job(job_id, limit=limit, offset=offset)
    else:
        rows, total = target_db.list_runs(q=q, limit=limit, offset=offset)
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
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(headers)
    for r in rows:
        stats = _safe_parse_stats(r.stats_json)
        vals = [
            int(r.id),
            int(r.job_id),
            r.status or "",
            r.started_at or "",
            r.finished_at or "",
            int((stats or {}).get("items_found", 0) or 0),
            int((stats or {}).get("items_ingested", 0) or 0),
            int(((stats.get("filters_actions") or {}).get("include", 0)) if isinstance(stats, dict) else 0),
            int(((stats.get("filters_actions") or {}).get("exclude", 0)) if isinstance(stats, dict) else 0),
            int(((stats.get("filters_actions") or {}).get("flag", 0)) if isinstance(stats, dict) else 0),
        ]
        if include_tallies:
            try:
                vals.append(json.dumps(_safe_parse_filter_tallies(stats)))
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                vals.append("{}")
        writer.writerow(vals)
    filename = f"watchlists_runs_{scope}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    # Include lightweight pagination metadata parity via header
    try:
        has_more = (offset + len(rows)) < int(total or 0)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        has_more = False
    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Has-More": "true" if has_more else "false",
        },
    )

@router.get("/runs/{run_id}", response_model=Run, summary="Get a run")
async def get_run(
    run_id: int = Path(..., ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: fetch a run from another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _enforce_runs_admin_if_configured(current_user)
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    try:
        r = target_db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found") from None
    return Run(id=r.id, job_id=r.job_id, status=r.status, started_at=r.started_at, finished_at=r.finished_at, stats=(json.loads(r.stats_json or "{}") if r.stats_json else None), error_msg=r.error_msg)


@router.get("/runs/{run_id}/details", response_model=RunDetail, summary="Get run details with stats and logs")
async def get_run_details(
    run_id: int = Path(..., ge=1),
    include_tallies: bool = Query(False, description="When true, include filter_tallies in the response"),
    filtered_sample_max: int = Query(5, ge=0, le=50, description="Optional number of filtered items to include as a sample"),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: fetch run details for another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    response: Response = None,  # type: ignore[assignment]
):
    _enforce_runs_admin_if_configured(current_user)
    resolved_user_id, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    """Return a summarized view of run stats and logs.

    Note: Per-filter tallies are retained in the raw run stats (GET /watchlists/runs/{run_id})
    under the key `filter_tallies` for detailed analysis. This detail view returns
    flattened totals (filters_include/exclude/flag) for quick inspection.
    """
    try:
        r = target_db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found") from None
    # Stats defaulting
    stats = {}
    try:
        stats = json.loads(r.stats_json or "{}") if r.stats_json else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
            p = _resolve_watchlist_log_path(user_id=int(resolved_user_id), log_path=r.log_path)
            if p and p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
                max_len = 65536
                if len(content) > max_len:
                    log_text = content[-max_len:]
                    truncated = True
                else:
                    log_text = content
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            log_text = None
            truncated = False
    # Build stats for detail view, including filter totals when present
    detail_stats: dict[str, int] = {
        "items_found": items_found,
        "items_ingested": items_ingested,
        "filters_include": 0,
        "filters_exclude": 0,
        "filters_flag": 0,
    }
    try:
        if isinstance(stats.get("filters_matched"), int):
            detail_stats["filters_matched"] = int(stats.get("filters_matched") or 0)
        fa = stats.get("filters_actions")
        if isinstance(fa, dict):
            for k in ("include", "exclude", "flag"):
                v = fa.get(k)
                if isinstance(v, int):
                    detail_stats[f"filters_{k}"] = int(v)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        pass
    # Optional tallies
    tallies_out = None
    if include_tallies:
        try:
            tallies = stats.get("filter_tallies")
            if isinstance(tallies, dict):
                # Coerce values to int
                tallies_out = {str(k): int(v) for k, v in tallies.items() if isinstance(k, (str, int)) and isinstance(v, (int, float))}
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            tallies_out = None

    # Optional filtered items sample for triage
    filtered_sample = None
    if filtered_sample_max and filtered_sample_max > 0:
        try:
            rows, _ = target_db.list_items(run_id=run_id, status="filtered", limit=int(filtered_sample_max), offset=0)
            filtered_sample = [
                {
                    "id": it.id,
                    "title": it.title,
                    "url": it.url,
                    "status": it.status,
                }
                for it in rows
            ]
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            filtered_sample = None

    # Expose filter debug max knob via header for visibility
    try:
        debug_max_env = int(os.getenv("WATCHLISTS_FILTER_DEBUG_MAX", "100") or 100)
        if response is not None:
            response.headers["X-Watchlists-Filter-Debug-Max"] = str(debug_max_env)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
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
# WebSocket run stream
# --------------------


@router.websocket("/runs/{run_id}/stream")
async def stream_run(
    websocket: WebSocket,
    run_id: int,
    token: str | None = Query(None),
    api_key: str | None = Query(None),
):
    try:
        user_id = await _resolve_watchlists_ws_user_id(websocket, token=token, api_key=api_key)
    except HTTPException:
        try:
            await websocket.close(code=4401)
        finally:
            return  # noqa: B012
    db = WatchlistsDatabase.for_user(user_id)
    try:
        run = db.get_run(int(run_id))
    except KeyError:
        try:
            await websocket.close(code=4404)
        finally:
            return  # noqa: B012

    await websocket.accept()
    stream = WebSocketStream(
        websocket,
        heartbeat_interval_s=0.0,
        idle_timeout_s=None,
        close_on_done=False,
        labels={"component": "watchlists", "endpoint": "watchlists_run_ws"},
    )
    await stream.start()

    log_tail_max = int(os.getenv("WATCHLISTS_WS_LOG_TAIL_MAX", "65536") or 65536)
    log_chunk_max = int(os.getenv("WATCHLISTS_WS_LOG_CHUNK_MAX", "8192") or 8192)
    poll_interval = float(os.getenv("WATCHLISTS_WS_POLL_INTERVAL", "1.0") or 1.0)
    if poll_interval < 0.2:
        poll_interval = 0.2

    def _parse_stats(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
            return {}

    last_status = run.status
    last_stats_raw = run.stats_json
    last_error = run.error_msg
    log_text, log_offset, log_inode, log_truncated = _read_log_tail(
        log_path=run.log_path,
        user_id=user_id,
        max_bytes=log_tail_max,
    )
    await stream.send_json(
        {
            "type": "snapshot",
            "run": {
                "id": run.id,
                "job_id": run.job_id,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
            },
            "stats": _parse_stats(run.stats_json),
            "error_msg": run.error_msg,
            "log_tail": log_text,
            "log_truncated": log_truncated,
        }
    )

    try:
        while True:
            run = db.get_run(int(run_id))
            stats_raw = run.stats_json
            if run.status != last_status or stats_raw != last_stats_raw or run.error_msg != last_error:
                await stream.send_json(
                    {
                        "type": "run_update",
                        "run": {
                            "id": run.id,
                            "job_id": run.job_id,
                            "status": run.status,
                            "started_at": run.started_at,
                            "finished_at": run.finished_at,
                        },
                        "stats": _parse_stats(stats_raw),
                        "error_msg": run.error_msg,
                    }
                )
                last_status = run.status
                last_stats_raw = stats_raw
                last_error = run.error_msg

            chunk, log_offset, log_inode = _read_log_chunk(
                log_path=run.log_path,
                user_id=user_id,
                offset=log_offset,
                max_bytes=log_chunk_max,
                inode=log_inode,
            )
            if chunk:
                await stream.send_json({"type": "log", "text": chunk})
            elif run.status not in {"running", "queued"}:
                await stream.send_json({"type": "complete", "status": run.status})
                break
            else:
                await stream.send_json({"type": "heartbeat", "ts": datetime.utcnow().isoformat()})

            await asyncio.sleep(poll_interval)
    except WebSocketDisconnect:
        logger.info("Watchlists WS disconnected")
        raise
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"Watchlists WS error: {exc}")
        with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
            await stream.ws.close(code=status.WS_1011_INTERNAL_ERROR)


# --------------------
# Audio Briefing
# --------------------


@router.get(
    "/runs/{run_id}/audio",
    summary="Get audio briefing artifact for a run",
    response_model=None,
)
async def get_run_audio(
    run_id: int = Path(..., ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: fetch run audio info for another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db=Depends(get_watchlists_db_for_user),
):
    """Return audio briefing artifact metadata for a watchlist run.

    Looks up the workflow run that was triggered by this watchlist run
    (via metadata) and returns the audio artifact info including download URL.
    """
    _enforce_runs_admin_if_configured(current_user)
    resolved_user_id, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    try:
        r = target_db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found") from None

    # Check the run stats for audio_briefing_task_id
    stats: dict[str, Any] = {}
    try:
        stats = json.loads(r.stats_json or "{}") if r.stats_json else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        stats = {}

    task_id = stats.get("audio_briefing_task_id")
    if not task_id:
        raise HTTPException(status_code=404, detail="no_audio_briefing_for_run")

    # Try to find the workflow run and its artifacts
    try:
        from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase

        user_dir = DatabasePaths.get_user_base_directory(int(resolved_user_id))
        wf_db_path = os.path.join(str(user_dir), "workflows", "workflows.db")
        if not os.path.exists(wf_db_path):
            raise HTTPException(status_code=404, detail="no_workflow_db")

        wf_db = WorkflowsDatabase(db_path=wf_db_path)
        # List runs and find one whose metadata matches
        runs = wf_db.list_runs(limit=50)
        matching_run = None
        for wf_run in runs:
            try:
                meta = json.loads(wf_run.metadata_json or "{}") if hasattr(wf_run, "metadata_json") else {}
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                meta = {}
            if meta.get("watchlist_run_id") == run_id:
                matching_run = wf_run
                break

        if not matching_run:
            return {
                "run_id": run_id,
                "task_id": task_id,
                "status": "pending",
                "audio_uri": None,
                "download_url": None,
            }

        # Check for artifacts
        artifacts = wf_db.list_artifacts(run_id=matching_run.id)
        audio_artifact = None
        for art in artifacts:
            art_meta = {}
            try:
                art_meta = json.loads(art.metadata_json or "{}") if hasattr(art, "metadata_json") else {}
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                art_meta = {}
            if art.type == "tts_audio" or art_meta.get("multi_voice"):
                audio_artifact = art
                break

        if audio_artifact:
            return {
                "run_id": run_id,
                "task_id": task_id,
                "status": matching_run.status,
                "audio_uri": audio_artifact.uri,
                "artifact_id": audio_artifact.id,
                "download_url": f"/api/v1/workflows/artifacts/{audio_artifact.id}/download",
                "size_bytes": audio_artifact.size_bytes,
                "mime_type": getattr(audio_artifact, "mime_type", "audio/mpeg"),
            }

        return {
            "run_id": run_id,
            "task_id": task_id,
            "status": matching_run.status,
            "audio_uri": None,
            "download_url": None,
        }

    except HTTPException:
        raise
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        logger.warning(f"Failed to look up audio artifact for run {run_id}: {exc}")
        return {
            "run_id": run_id,
            "task_id": task_id,
            "status": "unknown",
            "audio_uri": None,
            "download_url": None,
            "error": str(exc),
        }


# --------------------
# CSV Exports (Admin convenience)
# --------------------


@router.get("/runs/{run_id}/tallies.csv", response_class=PlainTextResponse, summary="Export filter tallies for a run as CSV")
async def export_run_tallies_csv(
    run_id: int = Path(..., ge=1),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: export run tallies for another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _enforce_runs_admin_if_configured(current_user)
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    try:
        r = target_db.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found") from None
    try:
        stats = json.loads(r.stats_json or "{}") if r.stats_json else {}
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        stats = {}
    tallies = stats.get("filter_tallies") if isinstance(stats, dict) else None
    headers = ["run_id", "filter_key", "count"]
    out_lines = [",".join(headers)]
    if isinstance(tallies, dict):
        for k, v in tallies.items():
            try:
                out_lines.append(",".join([str(run_id), json.dumps(str(k)), str(int(v))]))
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                continue
    filename = f"watchlists_run_{run_id}_tallies_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
    return PlainTextResponse("\n".join(out_lines), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})


# --------------------
# Scraped items
# --------------------
@router.get("/items", response_model=ScrapedItemsListResponse, summary="List scraped items across runs")
async def list_scraped_items(
    run_id: int | None = Query(None),
    job_id: int | None = Query(None),
    source_id: int | None = Query(None),
    status: str | None = Query(None),
    reviewed: bool | None = Query(None),
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: list items for another user ID.",
    ),
    q: str | None = Query(None, description="Search by title/summary substring"),
    since: str | None = Query(None, description="ISO date filter (created_at >= since)"),
    until: str | None = Query(None, description="ISO date filter (created_at <= until)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    limit = size
    offset = (page - 1) * limit
    rows, total = target_db.list_items(
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
    target_user_id: int | None = Query(
        None,
        ge=1,
        description="Admin-only: fetch an item from another user ID.",
    ),
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
):
    _, target_db = await _resolve_target_watchlists_context(
        current_user=current_user,
        current_db=db,
        target_user_id=target_user_id,
    )
    try:
        row = target_db.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="item_not_found") from None
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
        raise HTTPException(status_code=404, detail="item_not_found") from None
    return _row_to_scraped_item(row)


# --------------------
# Outputs
# --------------------
@router.post("/outputs", response_model=WatchlistOutput, summary="Generate an output from scraped items")
async def create_output(
    payload: WatchlistOutputCreateRequest,
    current_user: User = Depends(get_request_user),
    db = Depends(get_watchlists_db_for_user),
    collections_db = Depends(get_collections_db_for_user),
    media_db = Depends(get_media_db_for_user),
):
    collections_db.purge_expired_outputs()
    try:
        run = db.get_run(payload.run_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="run_not_found") from None
    try:
        job = db.get_job(run.job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job_not_found") from None

    job_prefs: dict[str, Any] = {}
    try:
        job_prefs = (
            json.loads(job.output_prefs_json or "{}") if getattr(job, "output_prefs_json", None) else {}
        )
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
        job_prefs = {}
    retention_spec = job_prefs.get("retention") or {}
    job_default_retention = _safe_int(retention_spec.get("default_seconds"), DEFAULT_OUTPUT_TTL_SECONDS)
    job_temp_retention = _safe_int(retention_spec.get("temporary_seconds"), TEMP_OUTPUT_TTL_SECONDS)
    template_defaults = job_prefs.get("template") or {}
    delivery_defaults = job_prefs.get("deliveries") or {}
    tts_brief_defaults = {}
    if isinstance(job_prefs.get("tts_brief"), dict):
        tts_brief_defaults = job_prefs.get("tts_brief") or {}
    elif isinstance(job_prefs.get("audio_brief"), dict):
        tts_brief_defaults = job_prefs.get("audio_brief") or {}

    job_id = run.job_id
    items: list[Any]
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
    tts_generate_explicit = "generate_tts" in payload.model_fields_set
    tts_brief_enabled = bool(tts_brief_defaults.get("enabled", False))
    tts_brief_max_items = _safe_int(tts_brief_defaults.get("max_items"), DEFAULT_TTS_BRIEF_MAX_ITEMS)
    if tts_brief_max_items < 0:
        tts_brief_max_items = 0
    effective_generate_tts = bool(payload.generate_tts)
    tts_brief_auto = False
    if (
        not tts_generate_explicit
        and tts_brief_enabled
        and tts_brief_max_items > 0
        and len(item_models) <= tts_brief_max_items
    ):
        effective_generate_tts = True
        tts_brief_auto = True

    configured_tts_template_name = tts_brief_defaults.get("template_name")
    configured_tts_model = tts_brief_defaults.get("model")
    configured_tts_voice = tts_brief_defaults.get("voice")
    configured_tts_speed = tts_brief_defaults.get("speed")

    effective_tts_template_name = payload.tts_template_name
    if not effective_tts_template_name and isinstance(configured_tts_template_name, str):
        effective_tts_template_name = configured_tts_template_name.strip() or None

    effective_tts_model = payload.tts_model
    if not effective_tts_model and isinstance(configured_tts_model, str):
        effective_tts_model = configured_tts_model.strip() or None

    effective_tts_voice = payload.tts_voice
    if not effective_tts_voice and isinstance(configured_tts_voice, str):
        effective_tts_voice = configured_tts_voice.strip() or None

    effective_tts_speed = payload.tts_speed
    if effective_tts_speed is None:
        effective_tts_speed = _safe_float(configured_tts_speed, None, minimum=0.25, maximum=4.0)

    version = _next_output_version_for_run(collections_db, payload.run_id)
    job_name = getattr(job, "name", None) or f"Job-{job.id}"
    default_title = f"{job_name}-Output-{version}"
    title = payload.title or default_title

    template_name = payload.template_name or template_defaults.get("default_name")
    template_version = payload.template_version
    if template_version is None:
        configured_default_version = template_defaults.get("default_version")
        if configured_default_version is not None:
            try:
                parsed_default_version = int(configured_default_version)
                if parsed_default_version > 0:
                    template_version = parsed_default_version
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS:
                template_version = None
    if template_version is not None and not template_name:
        raise HTTPException(status_code=400, detail="template_version_requires_template_name")
    template_record = None
    output_template = None
    if template_name:
        name_is_safe = bool(_TEMPLATE_NAME_RE.fullmatch(template_name))
        try:
            output_template = collections_db.get_output_template_by_name(template_name)
        except KeyError:
            output_template = None
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:  # noqa: BLE001
            logger.error(f"Watchlists template lookup failed: {exc}")
            raise HTTPException(status_code=500, detail="template_lookup_failed") from exc
        if output_template:
            if template_version is not None:
                raise HTTPException(status_code=400, detail="template_version_not_supported_for_outputs_template")
            if output_template.format not in {"md", "html"}:
                raise HTTPException(status_code=400, detail="template_format_not_supported")
        elif name_is_safe:
            try:
                template_record = template_store.load_template(template_name, version=template_version)
            except template_store.TemplateNotFoundError:
                template_record = None
            except template_store.TemplateVersionNotFoundError:
                raise HTTPException(status_code=404, detail="template_version_not_found") from None
            except TemplateValidationError as exc:
                raise HTTPException(status_code=400, detail="invalid_template_name") from exc
        if template_record is None and output_template is None:
            if not name_is_safe:
                raise HTTPException(status_code=400, detail="invalid_template_name")
            raise HTTPException(status_code=404, detail="template_not_found")
    template_format = None
    if output_template:
        template_format = output_template.format
    elif template_record:
        template_format = template_record.format

    output_format = payload.format or template_defaults.get("default_format") or (template_format or "md")
    if output_format not in {"md", "html"}:
        raise HTTPException(status_code=400, detail="invalid_format")

    # LLM summarization (opt-in via payload.summarize)
    llm_summaries: dict[int, str] = {}
    if payload.summarize:
        llm_provider = payload.llm_provider
        if not llm_provider:
            llm_cfg = job_prefs.get("llm") or job_prefs.get("summarize") or {}
            llm_provider = llm_cfg.get("provider") or llm_cfg.get("api_name")
        if not llm_provider:
            raise HTTPException(
                status_code=400,
                detail="llm_provider_required: set llm_provider in request or job output_prefs.llm.provider",
            )
        items_for_summary = [
            {
                "id": getattr(it, "id", None),
                "title": getattr(it, "title", None),
                "summary": getattr(it, "summary", None),
                "content": getattr(it, "summary", None) or getattr(it, "title", ""),
                "metadata_json": getattr(it, "metadata_json", None),
            }
            for it in items
        ]
        try:
            items_for_summary = await summarize_items_for_output(
                items_for_summary,
                api_name=llm_provider,
                model_override=payload.llm_model,
                custom_prompt=payload.summarize_prompt,
                db=db,
            )
            for entry in items_for_summary:
                item_id = entry.get("id")
                if item_id is not None and entry.get("llm_summary"):
                    llm_summaries[int(item_id)] = entry["llm_summary"]
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.warning(f"Watchlists output summarization failed (non-critical): {exc}")

    context = _build_output_context(title, job, run, item_models)

    # Inject LLM summaries into context
    if llm_summaries:
        for item_ctx in context.get("items", []):
            item_id = item_ctx.get("id")
            if item_id is not None and int(item_id) in llm_summaries:
                item_ctx["llm_summary"] = llm_summaries[int(item_id)]
        context["has_llm_summaries"] = True
    if output_template:
        context["template_name"] = output_template.name
        if output_template.description:
            context["template_description"] = output_template.description
        try:
            content = _render_template_with_context(output_template.body, context)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.error(f"Watchlists template render failed: {exc}")
            raise HTTPException(status_code=400, detail=f"template_render_failed: {exc}") from exc
    elif template_record:
        context["template_name"] = template_record.name
        if template_record.description:
            context["template_description"] = template_record.description
        try:
            content = _render_template_with_context(template_record.content, context)
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.error(f"Watchlists template render failed: {exc}")
            raise HTTPException(status_code=400, detail=f"template_render_failed: {exc}") from exc
    else:
        if output_format == "html":
            content = _render_default_html(title, item_models)
        else:
            content = _render_default_markdown(title, item_models)

    metadata: dict[str, Any] = {}
    if payload.metadata:
        with contextlib.suppress(_WATCHLISTS_NONCRITICAL_EXCEPTIONS):
            metadata.update(payload.metadata)
    metadata.update(
        {
            "item_count": len(item_models),
            "item_ids": [itm.id for itm in item_models],
            "format": output_format,
            "type": payload.type,
        }
    )
    if output_template:
        metadata["template_id"] = output_template.id
        metadata["template_name"] = output_template.name
        metadata["template_source"] = "outputs_templates"
        if output_template.description:
            metadata["template_description"] = output_template.description
    elif template_record:
        metadata["template_name"] = template_record.name
        metadata["template_version"] = template_record.version
        metadata["template_source"] = "watchlists_templates"
        if template_record.description:
            metadata["template_description"] = template_record.description
    metadata["version"] = version
    metadata["origin"] = "watchlists"
    if tts_brief_auto:
        metadata["tts_brief_auto"] = True
        metadata["tts_brief_max_items"] = tts_brief_max_items

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

    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    try:
        out_dir = _outputs_dir_for_user(user_id)
        out_dir.mkdir(parents=True, exist_ok=True)
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"watchlists outputs: failed to create outputs dir: {exc}")
        raise HTTPException(status_code=500, detail="storage_unavailable") from exc

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_metadata = dict(metadata)
    tags = sorted({t for itm in item_models for t in (itm.tags or []) if isinstance(t, str)})
    created_outputs: list[tuple[int, Any]] = []
    template_id = output_template.id if output_template else None

    def _variant_metadata(
        *,
        output_type: str,
        output_format: str,
        variant_kind: str,
        variant_of: int,
    ) -> dict[str, Any]:
        meta = dict(base_metadata)
        meta["type"] = output_type
        meta["format"] = output_format
        meta["variant_of"] = variant_of
        meta["variant_kind"] = variant_kind
        return meta

    def _apply_template_meta(meta: dict[str, Any], tpl) -> None:
        if tpl is None:
            return
        meta["template_id"] = tpl.id
        meta["template_name"] = tpl.name
        meta["template_source"] = "outputs_templates"
        if getattr(tpl, "description", None):
            meta["template_description"] = tpl.description

    async def _persist_output_artifact(
        *,
        output_type: str,
        output_format: str,
        output_title: str,
        output_content: str | None,
        filename_suffix: str | None,
        meta: dict[str, Any],
        tpl,
        variant_of: int | None,
        template_id_override: int | None = None,
    ) -> Any:
        meta = dict(meta)
        if tpl is not None:
            _apply_template_meta(meta, tpl)
        filename = _build_output_filename(output_title, filename_suffix, ts, output_format)
        path = _resolve_output_path_for_user(user_id, filename)
        if output_format == "mp3":
            await _write_tts_audio_file(
                rendered=output_content or "",
                path=path,
                tts_model=effective_tts_model,
                tts_voice=effective_tts_voice,
                tts_speed=effective_tts_speed,
                template_row=tpl,
            )
        else:
            try:
                path.write_text(output_content or "", encoding="utf-8")
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
                logger.error(f"watchlists outputs: failed to write output file: {exc}")
                raise HTTPException(status_code=500, detail="write_failed") from exc
        try:
            row = collections_db.create_output_artifact(
                type_=output_type,
                title=output_title,
                format_=output_format,
                storage_path=filename,
                metadata_json=json.dumps(meta),
                job_id=job_id,
                run_id=payload.run_id,
                media_item_id=None,
                retention_until=expires_at,
            )
        except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
            logger.error(f"watchlists outputs: failed to insert output row: {exc}")
            try:
                if path.exists():
                    path.unlink()
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as cleanup_exc:
                logger.debug(f"watchlists outputs: cleanup failed for {path}: {cleanup_exc}")
            raise HTTPException(status_code=500, detail="db_insert_failed") from exc
        created_outputs.append((row.id, path))

        if payload.ingest_to_media_db:
            media_id = await _ingest_output_to_media_db(
                media_db=media_db,
                output_id=row.id,
                title=output_title,
                content=output_content or "",
                output_type=output_type,
                output_format=output_format,
                storage_path=filename,
                template_id=(tpl.id if tpl is not None else template_id_override),
                run_id=payload.run_id,
                item_ids=meta.get("item_ids", []),
                tags=tags,
                variant_of=variant_of,
            )
            row = collections_db.update_output_media_item_id(row.id, media_id)
        return row

    def _cleanup_outputs() -> None:
        for oid, path in created_outputs:
            try:
                if path and hasattr(path, "exists") and path.exists():
                    path.unlink()
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"watchlists: cleanup failed to remove file {path}: {exc}")
            try:
                collections_db.delete_output_artifact(oid, hard=True)
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
                logger.debug(f"watchlists: cleanup failed to delete artifact {oid}: {exc}")

    try:
        row = await _persist_output_artifact(
            output_type=payload.type,
            output_format=output_format,
            output_title=title,
            output_content=content,
            filename_suffix=None,
            meta=base_metadata,
            tpl=output_template,
            variant_of=None,
            template_id_override=template_id,
        )

        if payload.generate_mece and payload.type != "mece_markdown":
            mece_tpl = None
            if payload.mece_template_name:
                try:
                    mece_tpl = collections_db.get_output_template_by_name(payload.mece_template_name)
                except KeyError:
                    raise HTTPException(status_code=404, detail="mece_template_not_found") from None
                if mece_tpl.type != "mece_markdown":
                    raise HTTPException(status_code=422, detail="invalid_mece_template")
            else:
                mece_tpl = collections_db.get_default_output_template_by_type("mece_markdown")
                if not mece_tpl:
                    raise HTTPException(status_code=404, detail="mece_template_not_found")
            try:
                mece_rendered = _render_template_with_context(mece_tpl.body, context)
            except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
                raise HTTPException(status_code=422, detail="mece_render_failed") from exc
            mece_meta = _variant_metadata(
                output_type=mece_tpl.type,
                output_format=mece_tpl.format,
                variant_kind="mece",
                variant_of=row.id,
            )
            await _persist_output_artifact(
                output_type=mece_tpl.type,
                output_format=mece_tpl.format,
                output_title=f"{title} (MECE)",
                output_content=mece_rendered,
                filename_suffix="mece",
                meta=mece_meta,
                tpl=mece_tpl,
                variant_of=row.id,
                template_id_override=None,
            )

        if effective_generate_tts:
            tts_tpl = None
            tts_rendered = None
            if effective_tts_template_name:
                try:
                    tts_tpl = collections_db.get_output_template_by_name(effective_tts_template_name)
                except KeyError:
                    raise HTTPException(status_code=404, detail="tts_template_not_found") from None
                if tts_tpl.type != "tts_audio":
                    raise HTTPException(status_code=422, detail="invalid_tts_template")
            else:
                tts_tpl = collections_db.get_default_output_template_by_type("tts_audio")
            if tts_tpl:
                try:
                    tts_rendered = _render_template_with_context(tts_tpl.body, context)
                except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
                    raise HTTPException(status_code=422, detail="tts_render_failed") from exc
            else:
                tts_rendered = _strip_html_for_tts(content) if output_format == "html" else content
            tts_rendered = tts_rendered or ""

            tts_meta = _variant_metadata(
                output_type="tts_audio",
                output_format="mp3",
                variant_kind="tts",
                variant_of=row.id,
            )
            await _persist_output_artifact(
                output_type="tts_audio",
                output_format="mp3",
                output_title=f"{title} (Audio)",
                output_content=tts_rendered,
                filename_suffix="audio",
                meta=tts_meta,
                tpl=tts_tpl,
                variant_of=row.id,
                template_id_override=None,
            )
    except HTTPException:
        _cleanup_outputs()
        raise
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        logger.error(f"watchlists outputs create failed: {exc}")
        _cleanup_outputs()
        raise HTTPException(status_code=500, detail="output_create_failed") from exc

    output = _row_to_output(row, user_id=user_id, content_override=content)

    notifications = NotificationsService(
        user_id=resolve_user_id_for_request(
            current_user,
            as_int=True,
            error_status=500,
            invalid_detail="invalid user_id",
        ),
        user_email=getattr(current_user, "email", None),
    )
    delivery_results: list[dict[str, Any]] = []
    chatbook_path_update: str | None = None
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

    metadata_for_update: dict[str, Any] | None = None
    if metadata_update_needed:
        metadata_for_update = {k: v for k, v in metadata.items() if v is not None}

    if metadata_for_update is not None or chatbook_path_update:
        updated_row = collections_db.update_output_artifact_metadata(
            output.id,
            metadata_json=json.dumps(metadata_for_update) if metadata_for_update is not None else None,
            chatbook_path=chatbook_path_update,
        )
        output = _row_to_output(updated_row, user_id=user_id)

    return output


@router.get("/outputs", response_model=WatchlistOutputsListResponse, summary="List generated outputs")
async def list_outputs(
    run_id: int | None = Query(None),
    job_id: int | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_request_user),
    collections_db = Depends(get_collections_db_for_user),
):
    limit = size
    offset = (page - 1) * limit
    collections_db.purge_expired_outputs()
    rows, _total = collections_db.list_output_artifacts(run_id=run_id, job_id=job_id, limit=limit, offset=offset)
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    items: list[WatchlistOutput] = []
    for row in rows:
        metadata = _parse_output_metadata(row)
        if metadata.get("origin") != "watchlists":
            continue
        items.append(_row_to_output(row, user_id=user_id))
    return WatchlistOutputsListResponse(items=items, total=len(items))


@router.get("/outputs/{output_id}", response_model=WatchlistOutput, summary="Get output metadata")
async def get_output(
    output_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    collections_db = Depends(get_collections_db_for_user),
):
    collections_db.purge_expired_outputs()
    try:
        row = collections_db.get_output_artifact(output_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="output_not_found") from exc
    metadata = _parse_output_metadata(row)
    if metadata.get("origin") != "watchlists":
        raise HTTPException(status_code=404, detail="output_not_found")
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    output = _row_to_output(row, user_id=user_id)
    if output.expired:
        collections_db.purge_expired_outputs()
        raise HTTPException(status_code=404, detail="output_not_found")
    return output


@router.get("/outputs/{output_id}/download", summary="Download rendered output")
async def download_output(
    output_id: int = Path(..., ge=1),
    current_user: User = Depends(get_request_user),
    collections_db = Depends(get_collections_db_for_user),
):
    collections_db.purge_expired_outputs()
    try:
        row = collections_db.get_output_artifact(output_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="output_not_found") from exc
    metadata = _parse_output_metadata(row)
    if metadata.get("origin") != "watchlists":
        raise HTTPException(status_code=404, detail="output_not_found")
    user_id = resolve_user_id_for_request(
        current_user,
        as_int=True,
        error_status=500,
        invalid_detail="invalid user_id",
    )
    output = _row_to_output(row, user_id=user_id)
    if output.expired:
        collections_db.purge_expired_outputs()
        raise HTTPException(status_code=404, detail="output_not_found")
    fmt = output.format or "md"
    filename = (output.title or f"watchlist-output-{output_id}").replace("/", "_")
    storage_name = output.storage_path
    if not storage_name:
        raise HTTPException(status_code=404, detail="output_file_missing")
    try:
        output_path = _resolve_output_path_for_user(user_id, storage_name)
    except HTTPException as exc:
        raise HTTPException(status_code=400, detail=exc.detail) from exc
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="output_file_missing")
    if fmt == "mp3":
        headers = {"Content-Disposition": f'attachment; filename="{filename}.mp3"'}
        return FileResponse(path=output_path, media_type="audio/mpeg", headers=headers)
    try:
        content = output_path.read_text(encoding="utf-8")
    except _WATCHLISTS_NONCRITICAL_EXCEPTIONS as exc:
        raise HTTPException(status_code=404, detail="output_file_missing") from exc
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
            version=rec.version,
            history_count=rec.history_count,
        )
        for rec in records
    ]
    return WatchlistTemplateListResponse(items=items)


@router.get(
    "/templates/{template_name}/versions",
    response_model=WatchlistTemplateVersionsResponse,
    summary="List a template's versions",
)
async def list_template_versions(
    template_name: str,
    current_user: User = Depends(get_request_user),
):
    if not _TEMPLATE_NAME_RE.fullmatch(template_name):
        raise HTTPException(status_code=400, detail="invalid_template_name")
    try:
        versions = template_store.list_template_versions(template_name)
    except template_store.TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="template_not_found") from None
    return WatchlistTemplateVersionsResponse(
        items=[
            WatchlistTemplateVersionSummary(
                version=item.version,
                format=item.format,  # type: ignore[arg-type]
                description=item.description,
                updated_at=item.updated_at,
                is_current=item.is_current,
            )
            for item in versions
        ]
    )


@router.get("/templates/{template_name}", response_model=WatchlistTemplateDetail, summary="Fetch a template")
async def get_template(
    template_name: str,
    version: int | None = Query(None, ge=1, description="Optional historical version to load"),
    current_user: User = Depends(get_request_user),
):
    if not _TEMPLATE_NAME_RE.fullmatch(template_name):
        raise HTTPException(status_code=400, detail="invalid_template_name")
    try:
        record = template_store.load_template(template_name, version=version)
    except template_store.TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="template_not_found") from None
    except template_store.TemplateVersionNotFoundError:
        raise HTTPException(status_code=404, detail="template_version_not_found") from None
    return WatchlistTemplateDetail(
        name=record.name,
        format=record.format,
        description=record.description,
        updated_at=record.updated_at,
        content=record.content,
        version=record.version,
        history_count=record.history_count,
        available_versions=record.available_versions or [record.version],
    )


@router.post(
    "/templates",
    response_model=WatchlistTemplateDetail,
    summary="Create or update a template",
    responses={400: {"model": WatchlistTemplateValidationErrorResponse}},
)
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
    except TemplateValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "template_validation_error", "message": str(exc)},
        ) from exc
    except template_store.TemplateExistsError:
        raise HTTPException(status_code=409, detail="template_exists") from None
    return WatchlistTemplateDetail(
        name=record.name,
        format=record.format,
        description=record.description,
        updated_at=record.updated_at,
        content=record.content,
        version=record.version,
        history_count=record.history_count,
        available_versions=record.available_versions or [record.version],
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
        raise HTTPException(status_code=404, detail="template_not_found") from None
    return {"deleted": True}
