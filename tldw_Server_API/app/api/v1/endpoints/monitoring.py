from __future__ import annotations

"""
Topic Monitoring API (Phase 1)

Admin endpoints to manage watchlists and view alerts.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
import os
import json

from tldw_Server_API.app.api.v1.API_Deps.auth_deps import require_admin
from tldw_Server_API.app.api.v1.schemas.monitoring_schemas import (
    Watchlist,
    WatchlistListResponse,
    WatchlistUpsertResponse,
    WatchlistDeleteResponse,
    AlertsListResponse,
    AlertItem,
    MarkReadResponse,
    NotificationSettings,
    NotificationSettingsUpdate,
    NotificationTestRequest,
)
from tldw_Server_API.app.core.Monitoring.topic_monitoring_service import get_topic_monitoring_service
from tldw_Server_API.app.core.DB_Management.TopicMonitoring_DB import TopicMonitoringDB, TopicAlert
from tldw_Server_API.app.core.Monitoring.notification_service import get_notification_service


router = APIRouter()


@router.get("/monitoring/watchlists", response_model=WatchlistListResponse, tags=["monitoring"], summary="List all watchlists")
async def list_watchlists(_: Any = Depends(require_admin)):
    svc = get_topic_monitoring_service()
    return WatchlistListResponse(watchlists=svc.list_watchlists())


@router.post("/monitoring/watchlists", response_model=WatchlistUpsertResponse, tags=["monitoring"], summary="Create or update a watchlist")
async def upsert_watchlist(payload: Watchlist, _: Any = Depends(require_admin)):
    try:
        svc = get_topic_monitoring_service()
        wl = svc.upsert_watchlist(payload)
        return WatchlistUpsertResponse(watchlist=wl, status="ok")
    except Exception as e:
        logger.error(f"Failed to upsert watchlist: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/monitoring/watchlists/{watchlist_id}", response_model=WatchlistDeleteResponse, tags=["monitoring"], summary="Delete a watchlist")
async def delete_watchlist(watchlist_id: str, _: Any = Depends(require_admin)):
    svc = get_topic_monitoring_service()
    ok = svc.delete_watchlist(watchlist_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Watchlist not found or failed to delete")
    return WatchlistDeleteResponse(status="deleted", id=watchlist_id)


@router.post("/monitoring/reload", tags=["monitoring"], summary="Reload watchlists from file")
async def reload_watchlists(_: Any = Depends(require_admin)):
    svc = get_topic_monitoring_service()
    svc.reload()
    return {"status": "ok"}


@router.get("/monitoring/alerts", response_model=AlertsListResponse, tags=["monitoring"], summary="List monitoring alerts")
async def list_alerts(
    user_id: Optional[str] = Query(None, description="Filter by user id"),
    since: Optional[str] = Query(None, description="ISO 8601 timestamp inclusive lower bound"),
    unread_only: Optional[bool] = Query(False, description="Only unread alerts"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: Any = Depends(require_admin),
):
    db = TopicMonitoringDB()  # default path from env handled in service; keep simple here
    rows = db.list_alerts(user_id=user_id, since_iso=since, unread_only=bool(unread_only), limit=limit, offset=offset)
    items: list[AlertItem] = []
    for r in rows:
        # metadata column may be JSON string
        meta = r.get("metadata")
        if isinstance(meta, str) and meta:
            try:
                import json
                r["metadata"] = json.loads(meta)
            except Exception as e:
                logger.debug(f"monitoring: failed to parse alert metadata JSON: {e}")
        items.append(AlertItem(**r))
    return AlertsListResponse(items=items)


@router.post("/monitoring/alerts/{alert_id}/read", response_model=MarkReadResponse, tags=["monitoring"], summary="Mark an alert as read")
async def mark_alert_read(alert_id: int, _: Any = Depends(require_admin)):
    db = TopicMonitoringDB()
    ok = db.mark_read(alert_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return MarkReadResponse(status="ok", id=alert_id)


@router.get("/monitoring/notifications/settings", response_model=NotificationSettings, tags=["monitoring"], summary="Get notification settings")
async def get_notifications_settings(_: Any = Depends(require_admin)):
    svc = get_notification_service()
    return NotificationSettings(**svc.get_settings())


@router.put("/monitoring/notifications/settings", response_model=NotificationSettings, tags=["monitoring"], summary="Update notification settings (runtime only)")
async def update_notifications_settings(payload: NotificationSettingsUpdate, _: Any = Depends(require_admin)):
    svc = get_notification_service()
    data = payload.model_dump(exclude_unset=True)
    updated = svc.update_settings(**data)
    return NotificationSettings(**updated)


@router.post("/monitoring/notifications/test", tags=["monitoring"], summary="Send a test notification (critical by default)")
async def send_test_notification(payload: NotificationTestRequest, _: Any = Depends(require_admin)):
    notifier = get_notification_service()
    alert = TopicAlert(
        user_id=payload.user_id or "admin",
        scope_type="user",
        scope_id=payload.user_id or "admin",
        source="monitoring.test",
        watchlist_id="test",
        rule_category="test",
        rule_severity=payload.severity or "critical",
        pattern="test",
        text_snippet=payload.message or "Test notification",
        metadata={"source": "admin_panel"},
    )
    try:
        notifier.notify(alert)
    except Exception as e:
        logger.error(f"monitoring: failed to send test notification: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return {"status": "ok"}


@router.get("/monitoring/notifications/recent", tags=["monitoring"], summary="Tail recent notifications from file (JSONL)")
async def get_recent_notifications(limit: int = Query(50, ge=1, le=500), _: Any = Depends(require_admin)):
    svc = get_notification_service()
    path = getattr(svc, 'file_path', None)
    items: list[dict] = []
    if not path or not os.path.exists(path):
        return {"items": []}
    try:
        # Simple bounded tail: read last N lines
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-limit:]
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                items.append(json.loads(ln))
            except Exception as e:
                logger.debug(f"monitoring: failed to parse recent notification JSONL line: {e}")
                items.append({"raw": ln})
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
