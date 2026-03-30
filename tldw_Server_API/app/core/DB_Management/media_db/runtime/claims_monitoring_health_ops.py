"""Package-owned claims monitoring health helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def get_claims_monitoring_health(self, user_id: str) -> dict[str, Any]:
    row = self.execute_query(
        "SELECT id, user_id, queue_size, worker_count, last_worker_heartbeat, last_processed_at, "
        "last_failure_at, last_failure_reason, updated_at "
        "FROM claims_monitoring_health WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
        (str(user_id),),
    ).fetchone()
    return dict(row) if row else {}


def upsert_claims_monitoring_health(
    self,
    *,
    user_id: str,
    queue_size: int,
    worker_count: int | None = None,
    last_worker_heartbeat: str | None = None,
    last_processed_at: str | None = None,
    last_failure_at: str | None = None,
    last_failure_reason: str | None = None,
) -> dict[str, Any]:
    now = self._get_current_utc_timestamp_str()
    existing = self.execute_query(
        "SELECT id FROM claims_monitoring_health WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
        (str(user_id),),
    ).fetchone()
    existing_id: int | None = None
    if existing is not None:
        try:
            existing_id = int(existing["id"])
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            try:
                existing_id = int(existing[0])
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                existing_id = None
    if existing_id is None:
        self.execute_query(
            (
                "INSERT INTO claims_monitoring_health "
                "(user_id, queue_size, worker_count, last_worker_heartbeat, last_processed_at, "
                "last_failure_at, last_failure_reason, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                str(user_id),
                int(queue_size),
                worker_count,
                last_worker_heartbeat,
                last_processed_at,
                last_failure_at,
                last_failure_reason,
                now,
            ),
            commit=True,
        )
        return get_claims_monitoring_health(self, str(user_id))

    self.execute_query(
        (
            "UPDATE claims_monitoring_health SET "
            "queue_size = ?, worker_count = ?, last_worker_heartbeat = ?, last_processed_at = ?, "
            "last_failure_at = ?, last_failure_reason = ?, updated_at = ? "
            "WHERE id = ?"
        ),
        (
            int(queue_size),
            worker_count,
            last_worker_heartbeat,
            last_processed_at,
            last_failure_at,
            last_failure_reason,
            now,
            int(existing_id),
        ),
        commit=True,
    )
    return get_claims_monitoring_health(self, str(user_id))
