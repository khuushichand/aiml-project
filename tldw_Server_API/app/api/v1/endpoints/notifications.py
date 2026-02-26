from __future__ import annotations

import asyncio
import contextlib
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from loguru import logger

from tldw_Server_API.app.api.v1.API_Deps.Collections_DB_Deps import get_collections_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import rbac_rate_limit, require_permissions
from tldw_Server_API.app.api.v1.schemas.reminders_schemas import (
    NotificationDismissResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
    NotificationResponse,
    NotificationsListResponse,
    NotificationsMarkReadRequest,
    NotificationsMarkReadResponse,
    NotificationsUnreadCountResponse,
    NotificationSnoozeRequest,
    NotificationSnoozeResponse,
)
from tldw_Server_API.app.core.AuthNZ.permissions import NOTIFICATIONS_CONTROL, NOTIFICATIONS_READ
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase, UserNotificationRow
from tldw_Server_API.app.core.Streaming.streams import SSEStream

router = APIRouter(prefix="/notifications", tags=["notifications"])

_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    ImportError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
)


def _notification_to_response(row: UserNotificationRow) -> NotificationResponse:
    return NotificationResponse(
        id=row.id,
        user_id=row.user_id,
        kind=row.kind,  # type: ignore[arg-type]
        title=row.title,
        message=row.message,
        severity=row.severity,
        source_task_id=row.source_task_id,
        source_task_run_id=row.source_task_run_id,
        source_job_id=row.source_job_id,
        source_domain=row.source_domain,
        source_job_type=row.source_job_type,
        link_type=row.link_type,
        link_id=row.link_id,
        link_url=row.link_url,
        dedupe_key=row.dedupe_key,
        retention_until=row.retention_until,
        archived_at=row.archived_at,
        created_at=row.created_at,
        read_at=row.read_at,
        dismissed_at=row.dismissed_at,
    )


def _stream_int_env(key: str, default: int, *, min_value: int, max_value: int) -> int:
    raw = os.getenv(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, value))


def _stream_float_env(key: str, default: float, *, min_value: float) -> float:
    raw = os.getenv(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return max(min_value, value)


def _resolve_stream_cursor(*, after: int, last_event_id: str | None) -> int:
    raw = (last_event_id or "").strip()
    if raw:
        try:
            return max(0, int(raw))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid_last_event_id",
            ) from exc
    return max(0, int(after))


def _notification_stream_payload(row: UserNotificationRow) -> dict:
    return {
        "event_id": row.id,
        "notification_id": row.id,
        "kind": row.kind,
        "created_at": row.created_at,
        "title": row.title,
        "message": row.message,
        "severity": row.severity,
    }


@router.get(
    "",
    response_model=NotificationsListResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.read"))],
)
async def list_notifications(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_archived: bool = Query(False),
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_READ)),  # noqa: B008
) -> NotificationsListResponse:
    rows = db.list_user_notifications(include_archived=include_archived, limit=limit, offset=offset)
    return NotificationsListResponse(items=[_notification_to_response(row) for row in rows], total=len(rows))


@router.get(
    "/unread-count",
    response_model=NotificationsUnreadCountResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.read"))],
)
async def unread_count(
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_READ)),  # noqa: B008
) -> NotificationsUnreadCountResponse:
    return NotificationsUnreadCountResponse(unread_count=db.count_unread_user_notifications())


@router.post(
    "/mark-read",
    response_model=NotificationsMarkReadResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.control"))],
)
async def mark_read(
    payload: NotificationsMarkReadRequest,
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_CONTROL)),  # noqa: B008
) -> NotificationsMarkReadResponse:
    updated = db.mark_user_notifications_read(payload.ids)
    return NotificationsMarkReadResponse(updated=updated)


@router.post(
    "/{notification_id}/dismiss",
    response_model=NotificationDismissResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.control"))],
)
async def dismiss_notification(
    notification_id: int = Path(..., ge=1),
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_CONTROL)),  # noqa: B008
) -> NotificationDismissResponse:
    return NotificationDismissResponse(dismissed=db.dismiss_user_notification(notification_id))


@router.post(
    "/{notification_id}/snooze",
    response_model=NotificationSnoozeResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.control"))],
)
async def snooze_notification(
    payload: NotificationSnoozeRequest,
    notification_id: int = Path(..., ge=1),
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_CONTROL)),  # noqa: B008
) -> NotificationSnoozeResponse:
    try:
        source = db.get_user_notification(notification_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="notification_not_found") from exc

    run_at = (datetime.now(timezone.utc) + timedelta(minutes=payload.minutes)).isoformat()
    task_id = db.create_reminder_task(
        title=f"Snoozed: {source.title}",
        body=source.message,
        schedule_kind="one_time",
        run_at=run_at,
        cron=None,
        timezone="UTC",
        enabled=True,
        link_type=source.link_type,
        link_id=source.link_id,
        link_url=source.link_url,
    )
    return NotificationSnoozeResponse(task_id=task_id, run_at=run_at)


@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.read"))],
)
async def get_preferences(
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_READ)),  # noqa: B008
) -> NotificationPreferencesResponse:
    row = db.get_notification_preferences()
    return NotificationPreferencesResponse(
        user_id=row.user_id,
        reminder_enabled=row.reminder_enabled,
        job_completed_enabled=row.job_completed_enabled,
        job_failed_enabled=row.job_failed_enabled,
        updated_at=row.updated_at,
    )


@router.patch(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    dependencies=[Depends(rbac_rate_limit("notifications.control"))],
)
async def patch_preferences(
    payload: NotificationPreferencesUpdateRequest,
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_CONTROL)),  # noqa: B008
) -> NotificationPreferencesResponse:
    updated = db.update_notification_preferences(
        reminder_enabled=payload.reminder_enabled,
        job_completed_enabled=payload.job_completed_enabled,
        job_failed_enabled=payload.job_failed_enabled,
    )
    return NotificationPreferencesResponse(
        user_id=updated.user_id,
        reminder_enabled=updated.reminder_enabled,
        job_completed_enabled=updated.job_completed_enabled,
        job_failed_enabled=updated.job_failed_enabled,
        updated_at=updated.updated_at,
    )


@router.get(
    "/stream",
    dependencies=[Depends(rbac_rate_limit("notifications.read"))],
)
async def stream_notifications(
    after: int = Query(0, ge=0),
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
    db: CollectionsDatabase = Depends(get_collections_db_for_user),
    _principal=Depends(require_permissions(NOTIFICATIONS_READ)),  # noqa: B008
) -> StreamingResponse:
    cursor = _resolve_stream_cursor(after=after, last_event_id=last_event_id)
    user_id = int(db.user_id)
    replay_window = _stream_int_env("NOTIFICATIONS_STREAM_REPLAY_WINDOW", 500, min_value=1, max_value=5000)
    batch_size = _stream_int_env("NOTIFICATIONS_STREAM_BATCH_SIZE", 200, min_value=1, max_value=1000)
    burst_threshold = _stream_int_env("NOTIFICATIONS_STREAM_BURST_THRESHOLD", 50, min_value=1, max_value=1000)
    floor_check_every = _stream_int_env("NOTIFICATIONS_STREAM_FLOOR_CHECK_EVERY_POLLS", 15, min_value=1, max_value=3600)
    poll_interval_s = _stream_float_env("NOTIFICATIONS_STREAM_POLL_SEC", 1.0, min_value=0.01)
    send_timeout_s = _stream_float_env("NOTIFICATIONS_STREAM_SEND_TIMEOUT_SEC", 1.0, min_value=0.05)
    heartbeat_interval_s = _stream_float_env("NOTIFICATIONS_STREAM_HEARTBEAT_SEC", 10.0, min_value=0.05)
    max_duration_s = _stream_float_env("NOTIFICATIONS_STREAM_MAX_DURATION_SEC", 0.0, min_value=0.0)
    if max_duration_s <= 0:
        max_duration_s = None
    stream = SSEStream(
        heartbeat_interval_s=heartbeat_interval_s,
        heartbeat_mode="data",
        max_duration_s=max_duration_s,
        labels={"component": "notifications", "endpoint": "notifications_stream"},
    )

    async def _send_with_timeout(event: str, payload: dict, *, event_id: str | None = None) -> bool:
        try:
            await asyncio.wait_for(stream.send_event(event, payload, event_id=event_id), timeout=send_timeout_s)
            return True
        except asyncio.TimeoutError:
            logger.warning("notifications stream send timeout for event={}", event)
            with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                await stream.done(force=True)
            return False

    async def _producer() -> None:
        nonlocal cursor
        if not await _send_with_timeout("heartbeat", {}):
            return
        poll_count = 0
        while True:
            try:
                if getattr(stream, "_closed", False):
                    break
            except _NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS:
                pass
            try:
                with CollectionsDatabase.for_user(user_id=user_id) as user_db:
                    while True:
                        try:
                            if getattr(stream, "_closed", False):
                                return
                        except _NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS:
                            pass

                        if cursor > 0 and (poll_count % floor_check_every == 0):
                            floor_id = user_db.get_user_notifications_window_floor_id(window_size=replay_window)
                            if floor_id is not None and cursor < (floor_id - 1):
                                latest_id = user_db.get_user_notifications_latest_id()
                                if not await _send_with_timeout(
                                    "reset_required",
                                    {
                                        "reason": "cursor_too_old",
                                        "min_event_id": floor_id - 1,
                                        "latest_event_id": latest_id,
                                    },
                                    event_id=str(latest_id or floor_id - 1),
                                ):
                                    return
                                cursor = floor_id - 1

                        rows = user_db.list_user_notifications_after_id(after_id=cursor, limit=batch_size)
                        if rows:
                            if len(rows) > burst_threshold:
                                first_id = rows[0].id
                                last_id = rows[-1].id
                                if not await _send_with_timeout(
                                    "notifications_coalesced",
                                    {
                                        "count": len(rows),
                                        "from_event_id": first_id,
                                        "to_event_id": last_id,
                                    },
                                    event_id=str(last_id),
                                ):
                                    return
                                cursor = last_id
                            else:
                                for row in rows:
                                    if not await _send_with_timeout(
                                        "notification",
                                        _notification_stream_payload(row),
                                        event_id=str(row.id),
                                    ):
                                        return
                                    cursor = row.id
                        poll_count += 1
                        await asyncio.sleep(poll_interval_s)
            except (asyncio.CancelledError, GeneratorExit):
                break
            except _NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS as exc:
                logger.warning("notifications stream loop error: {}", exc)
                await asyncio.sleep(poll_interval_s)

    async def _gen():
        producer_task = asyncio.create_task(_producer(), name="notifications_stream_producer")
        try:
            async for line in stream.iter_sse():
                yield line
        except asyncio.CancelledError:
            if not producer_task.done():
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    await stream.done(force=True)
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    producer_task.cancel()
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    await producer_task
            raise
        else:
            if not producer_task.done():
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    await stream.done(force=True)
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    producer_task.cancel()
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    await producer_task
        finally:
            if not producer_task.done():
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    await stream.done(force=True)
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    producer_task.cancel()
                with contextlib.suppress(_NOTIFICATIONS_STREAM_NONCRITICAL_EXCEPTIONS):
                    await producer_task

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
