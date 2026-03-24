"""Package-owned claims notification helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def insert_claim_notification(
    self,
    *,
    user_id: str,
    kind: str,
    payload_json: str,
    target_user_id: str | None = None,
    target_review_group: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> dict[str, Any]:
    now = self._get_current_utc_timestamp_str()
    insert_sql = (
        "INSERT INTO claims_notifications "
        "(user_id, kind, target_user_id, target_review_group, resource_type, resource_id, "
        "payload_json, created_at, delivered_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    if self.backend_type == BackendType.POSTGRESQL:
        insert_sql += " RETURNING id"
    cursor = self.execute_query(
        insert_sql,
        (
            str(user_id),
            str(kind),
            str(target_user_id) if target_user_id is not None else None,
            str(target_review_group) if target_review_group is not None else None,
            str(resource_type) if resource_type is not None else None,
            str(resource_id) if resource_id is not None else None,
            str(payload_json),
            str(now),
            None,
        ),
        commit=True,
    )
    if self.backend_type == BackendType.POSTGRESQL:
        row = cursor.fetchone()
        notif_id = int(row["id"]) if row else None
    else:
        notif_id = cursor.lastrowid
    return get_claim_notification(self, int(notif_id)) if notif_id else {}


def get_claim_notification(self, notification_id: int) -> dict[str, Any]:
    row = self.execute_query(
        "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "
        "resource_id, payload_json, created_at, delivered_at "
        "FROM claims_notifications WHERE id = ?",
        (int(notification_id),),
    ).fetchone()
    return dict(row) if row else {}


def get_latest_claim_notification(
    self,
    *,
    user_id: str,
    kind: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> dict[str, Any] | None:
    conditions = ["user_id = ?", "kind = ?"]
    params: list[Any] = [str(user_id), str(kind)]
    if resource_type is not None:
        conditions.append("resource_type = ?")
        params.append(str(resource_type))
    if resource_id is not None:
        conditions.append("resource_id = ?")
        params.append(str(resource_id))
    sql = (
        "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "  # nosec B608
        "resource_id, payload_json, created_at, delivered_at "
        "FROM claims_notifications "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY created_at DESC LIMIT 1"
    )
    row = self.execute_query(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def list_claim_notifications(
    self,
    *,
    user_id: str,
    kind: str | None = None,
    target_user_id: str | None = None,
    target_review_group: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    delivered: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    try:
        limit = int(limit)
        offset = int(offset)
    except (TypeError, ValueError):
        limit, offset = 100, 0
    limit = max(1, min(1000, limit))
    offset = max(0, offset)
    conditions = ["user_id = ?"]
    params: list[Any] = [str(user_id)]
    if kind:
        conditions.append("kind = ?")
        params.append(str(kind))
    if target_user_id:
        conditions.append("target_user_id = ?")
        params.append(str(target_user_id))
    if target_review_group:
        conditions.append("target_review_group = ?")
        params.append(str(target_review_group))
    if resource_type:
        conditions.append("resource_type = ?")
        params.append(str(resource_type))
    if resource_id:
        conditions.append("resource_id = ?")
        params.append(str(resource_id))
    if delivered is True:
        conditions.append("delivered_at IS NOT NULL")
    elif delivered is False:
        conditions.append("delivered_at IS NULL")
    sql = (
        "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "  # nosec B608
        "resource_id, payload_json, created_at, delivered_at "
        "FROM claims_notifications "
        f"WHERE {' AND '.join(conditions)} "
        "ORDER BY created_at DESC LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    rows = self.execute_query(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_claim_notifications_by_ids(self, ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    sql = (
        "SELECT id, user_id, kind, target_user_id, target_review_group, resource_type, "  # nosec B608
        "resource_id, payload_json, created_at, delivered_at "
        f"FROM claims_notifications WHERE id IN ({placeholders})"
    )
    rows = self.execute_query(sql, tuple(int(i) for i in ids)).fetchall()
    return [dict(row) for row in rows]


def mark_claim_notifications_delivered(self, ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" * len(ids))
    now = self._get_current_utc_timestamp_str()
    sql = f"UPDATE claims_notifications SET delivered_at = ? WHERE id IN ({placeholders})"  # nosec B608
    params: list[Any] = [str(now)]
    params.extend(int(i) for i in ids)
    cursor = self.execute_query(sql, tuple(params), commit=True)
    try:
        return int(getattr(cursor, "rowcount", 0) or 0)
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        return 0
