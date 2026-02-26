from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse

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

router = APIRouter(prefix="/notifications", tags=["notifications"])


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
    _principal=Depends(require_permissions(NOTIFICATIONS_READ)),  # noqa: B008
) -> StreamingResponse:
    async def _event_stream():
        yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
