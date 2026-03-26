"""Package-owned claims analytics export helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def create_claims_analytics_export(
    self,
    *,
    export_id: str,
    user_id: str,
    format: str,
    status: str,
    payload_json: str | None = None,
    payload_csv: str | None = None,
    filters_json: str | None = None,
    pagination_json: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    now = self._get_current_utc_timestamp_str()
    self.execute_query(
        (
            "INSERT INTO claims_analytics_exports "
            "(export_id, user_id, format, status, payload_json, payload_csv, filters_json, "
            "pagination_json, error_message, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        (
            str(export_id),
            str(user_id),
            str(format),
            str(status),
            payload_json,
            payload_csv,
            filters_json,
            pagination_json,
            error_message,
            now,
            now,
        ),
        commit=True,
    )
    return get_claims_analytics_export(self, export_id, user_id=str(user_id))


def get_claims_analytics_export(
    self,
    export_id: str,
    *,
    user_id: str | None = None,
) -> dict[str, Any]:
    params: list[Any] = [str(export_id)]
    conditions = ["export_id = ?"]
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(str(user_id))
    row = self.execute_query(
        (
            "SELECT export_id, user_id, format, status, payload_json, payload_csv, filters_json, "  # nosec B608
            "pagination_json, error_message, created_at, updated_at "
            "FROM claims_analytics_exports WHERE "
            + " AND ".join(conditions)
            + " LIMIT 1"
        ),
        tuple(params),
    ).fetchone()
    return dict(row) if row else {}


def list_claims_analytics_exports(
    self,
    user_id: str,
    *,
    status: str | None = None,
    format: str | None = None,
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
    if status:
        conditions.append("status = ?")
        params.append(str(status))
    if format:
        conditions.append("format = ?")
        params.append(str(format))
    query = (
        "SELECT export_id, user_id, format, status, filters_json, pagination_json, error_message, "  # nosec B608
        "created_at, updated_at "
        "FROM claims_analytics_exports WHERE "
        + " AND ".join(conditions)
        + " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    )
    params.extend([limit, offset])
    rows = self.execute_query(query, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def count_claims_analytics_exports(
    self,
    user_id: str,
    *,
    status: str | None = None,
    format: str | None = None,
) -> int:
    conditions = ["user_id = ?"]
    params: list[Any] = [str(user_id)]
    if status:
        conditions.append("status = ?")
        params.append(str(status))
    if format:
        conditions.append("format = ?")
        params.append(str(format))
    row = self.execute_query(
        "SELECT COUNT(*) AS count FROM claims_analytics_exports WHERE " + " AND ".join(conditions),  # nosec B608
        tuple(params),
    ).fetchone()
    if not row:
        return 0
    try:
        return int(row["count"] or 0)
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        try:
            return int(row[0] or 0)
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            return 0


def cleanup_claims_analytics_exports(
    self,
    *,
    user_id: str,
    retention_hours: float,
) -> int:
    try:
        retention_hours = float(retention_hours)
    except (TypeError, ValueError):
        return 0
    if retention_hours <= 0:
        return 0
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    ).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    cursor = self.execute_query(
        "DELETE FROM claims_analytics_exports WHERE user_id = ? AND created_at < ?",
        (str(user_id), cutoff),
        commit=True,
    )
    try:
        deleted = int(cursor.rowcount or 0)
    except _MEDIA_NONCRITICAL_EXCEPTIONS:
        deleted = 0
    return max(deleted, 0)
