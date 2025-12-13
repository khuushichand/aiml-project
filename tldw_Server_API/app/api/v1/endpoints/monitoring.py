from __future__ import annotations

"""
Topic Monitoring API (Phase 1)

Permission-gated endpoints requiring SYSTEM_LOGS to manage watchlists, alerts, and notifications.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
import os
import json
import asyncio

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_permissions
from tldw_Server_API.app.core.AuthNZ.permissions import SYSTEM_LOGS
from tldw_Server_API.app.api.v1.schemas.monitoring_schemas import (
    Watchlist,
    WatchlistListResponse,
    WatchlistUpsertResponse,
    WatchlistDeleteResponse,
    WatchlistsReloadResponse,
    AlertsListResponse,
    AlertItem,
    MarkReadResponse,
    NotificationSettings,
    NotificationSettingsUpdate,
    NotificationTestRequest,
    NotificationTestResponse,
    RecentNotificationsResponse,
)
from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicMonitoringDB, TopicAlert
from tldw_Server_API.app.core.Monitoring.notification_service import get_notification_service

# All monitoring routes require SYSTEM_LOGS permission via this dependency.
router = APIRouter(
    dependencies=[Depends(require_permissions(SYSTEM_LOGS))],
)

def get_topic_monitoring_db() -> TopicMonitoringDB:
    """Return a TopicMonitoringDB instance for alert reads/updates."""
    raw_db_path = os.getenv("MONITORING_ALERTS_DB", "Databases/monitoring_alerts.db")
    try:
        from pathlib import Path as _Path
        from tldw_Server_API.app.core.Utils.Utils import get_project_root as _gpr

        root = _Path(_gpr())
    except Exception:
        from pathlib import Path as _Path

        root = _Path(__file__).resolve().parents[5]

    try:
        db_path = _Path(str(raw_db_path))
    except Exception:
        db_path = _Path("Databases/monitoring_alerts.db")

    if not db_path.is_absolute():
        db_path = (root / db_path).resolve()

    return TopicMonitoringDB(db_path=str(db_path))


@router.get(
    "/monitoring/watchlists",
    response_model=WatchlistListResponse,
    tags=["monitoring"],
    summary="List all watchlists",
)
async def list_watchlists() -> WatchlistListResponse:
    """List all configured topic monitoring watchlists."""
    svc = get_topic_monitoring_service()
    return WatchlistListResponse(watchlists=svc.list_watchlists())


@router.post(
    "/monitoring/watchlists",
    response_model=WatchlistUpsertResponse,
    tags=["monitoring"],
    summary="Create or update a watchlist",
)
async def upsert_watchlist(payload: Watchlist) -> WatchlistUpsertResponse:
    """Create a new watchlist or update an existing one."""
    try:
        svc = get_topic_monitoring_service()
        wl = svc.upsert_watchlist(payload)
        return WatchlistUpsertResponse(watchlist=wl, status="ok")
    except HTTPException:
        # Propagate existing HTTP errors without masking them
        raise
    except Exception as e:  # Generic 500 handler
        logger.exception("Failed to upsert watchlist")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upsert watchlist",
        ) from e


@router.delete(
    "/monitoring/watchlists/{watchlist_id}",
    response_model=WatchlistDeleteResponse,
    tags=["monitoring"],
    summary="Delete a watchlist",
)
async def delete_watchlist(watchlist_id: str) -> WatchlistDeleteResponse:
    """Delete a watchlist by ID and return the deletion status."""
    svc = get_topic_monitoring_service()
    ok = svc.delete_watchlist(watchlist_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found or failed to delete")
    return WatchlistDeleteResponse(status="deleted", id=watchlist_id)


@router.post(
    "/monitoring/reload",
    response_model=WatchlistsReloadResponse,
    tags=["monitoring"],
    summary="Reload watchlists from file",
)
async def reload_watchlists() -> WatchlistsReloadResponse:
    """Reload watchlist definitions from the backing configuration source."""
    svc = get_topic_monitoring_service()
    svc.reload()
    return WatchlistsReloadResponse(status="ok")


@router.get(
    "/monitoring/alerts",
    response_model=AlertsListResponse,
    tags=["monitoring"],
    summary="List monitoring alerts",
)
async def list_alerts(
    user_id: str | None = Query(None, description="Filter by user id"),
    since: str | None = Query(None, description="ISO 8601 timestamp inclusive lower bound"),
    unread_only: bool = Query(False, description="Only unread alerts"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: TopicMonitoringDB = Depends(get_topic_monitoring_db),
) -> AlertsListResponse:
    """List monitoring alerts with optional filters and pagination."""

    rows = db.list_alerts(user_id=user_id, since_iso=since, unread_only=unread_only, limit=limit, offset=offset)
    items: list[AlertItem] = []
    for r in rows:
        # metadata column may be JSON string
        meta = r.get("metadata")
        if isinstance(meta, str) and meta:
            try:
                r["metadata"] = json.loads(meta)
            except (TypeError, json.JSONDecodeError) as e:
                logger.debug(f"monitoring: failed to parse alert metadata JSON: {e}")
        items.append(AlertItem(**r))
    return AlertsListResponse(items=items)


@router.post(
    "/monitoring/alerts/{alert_id}/read",
    response_model=MarkReadResponse,
    tags=["monitoring"],
    summary="Mark an alert as read",
)
async def mark_alert_read(
    alert_id: int,
    db: TopicMonitoringDB = Depends(get_topic_monitoring_db),
) -> MarkReadResponse:
    """Mark a single alert as read by ID."""

    ok = db.mark_read(alert_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return MarkReadResponse(status="ok", id=alert_id)


@router.get(
    "/monitoring/notifications/settings",
    response_model=NotificationSettings,
    tags=["monitoring"],
    summary="Get notification settings",
)
async def get_notifications_settings() -> NotificationSettings:
    """Return the current in-memory notification settings."""

    svc = get_notification_service()
    return NotificationSettings(**svc.get_settings())


@router.put(
    "/monitoring/notifications/settings",
    response_model=NotificationSettings,
    tags=["monitoring"],
    summary="Update notification settings (runtime only)",
)
async def update_notifications_settings(
    payload: NotificationSettingsUpdate,
) -> NotificationSettings:
    """Update notification settings for the running process."""

    svc = get_notification_service()
    data = payload.model_dump(exclude_unset=True)
    updated = svc.update_settings(**data)
    return NotificationSettings(**updated)


@router.post(
    "/monitoring/notifications/test",
    response_model=NotificationTestResponse,
    tags=["monitoring"],
    summary="Send a test notification (critical by default)",
)
async def send_test_notification(payload: NotificationTestRequest) -> NotificationTestResponse:
    """Send a synthetic test notification using the current settings."""

    notifier = get_notification_service()
    alert = TopicAlert(
        user_id=payload.user_id or "admin",
        scope_type="user",
        scope_id=payload.user_id or "admin",
        source="monitoring.test",
        watchlist_id="test",
        rule_category="test",
        rule_severity=payload.severity,
        pattern="test",
        text_snippet=payload.message or "Test notification",
        metadata={"source": "admin_panel"},
    )
    try:
        # notifier.notify performs file I/O; offload to a thread to keep the event loop responsive.
        await asyncio.to_thread(notifier.notify, alert)
    except Exception as e:  # Generic 500 handler
        logger.exception("monitoring: failed to send test notification")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test notification",
        ) from e
    return NotificationTestResponse(status="ok")


def _tail_jsonl_file(path: str, limit: int) -> list[str]:
    """
    Return the last ``limit`` lines from a JSONL file without scanning the entire file.

    Reads from the end of the file in fixed-size blocks until enough newline-delimited
    records have been collected.
    """
    if limit <= 0:
        return []

    block_size = 4096
    lines: list[bytes] = []
    buffer = b""

    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        remaining = file_size

        while remaining > 0 and len(lines) < limit:
            read_size = block_size if remaining >= block_size else remaining
            remaining -= read_size
            f.seek(remaining)
            chunk = f.read(read_size)
            if not chunk:
                break

            buffer = chunk + buffer

            while True:
                newline_pos = buffer.rfind(b"\n")
                if newline_pos == -1:
                    break
                line = buffer[newline_pos + 1 :]
                buffer = buffer[:newline_pos]
                if line:
                    lines.append(line)
                if len(lines) >= limit:
                    break

        if buffer and len(lines) < limit:
            lines.append(buffer)

    # lines are collected from the end; reverse to restore chronological order
    decoded: list[str] = []
    for raw in reversed(lines[:limit]):
        decoded.append(raw.decode("utf-8", errors="replace").rstrip("\n"))
    return decoded


@router.get(
    "/monitoring/notifications/recent",
    response_model=RecentNotificationsResponse,
    tags=["monitoring"],
    summary="Tail recent notifications from file (JSONL)",
)
async def get_recent_notifications(
    limit: int = Query(50, ge=1, le=500),
) -> RecentNotificationsResponse:
    """Return a bounded tail of recent notification events from the JSONL log file."""

    svc = get_notification_service()
    path = svc.get_notification_file_path()
    items: list[dict] = []
    if not path or not os.path.exists(path):
        return RecentNotificationsResponse(items=[])
    try:
        # Offload blocking file I/O to a worker thread to keep the event loop responsive.
        lines = await asyncio.to_thread(_tail_jsonl_file, path, limit)
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                items.append(json.loads(ln))
            except (TypeError, json.JSONDecodeError) as e:
                logger.debug(f"monitoring: failed to parse recent notification JSONL line: {e}")
                items.append({"raw": ln})
    except Exception as e:  # Generic 500 handler
        logger.error(f"monitoring: failed to read recent notifications from {path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read recent notifications",
        ) from e
    else:
        return RecentNotificationsResponse(items=items)
