"""Package-owned claims monitoring config helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def delete_claims_monitoring_configs_by_user(self, user_id: str) -> None:
    self.execute_query(
        "DELETE FROM claims_monitoring_config WHERE user_id = ?",
        (str(user_id),),
        commit=True,
    )


def list_claims_monitoring_configs(
    self,
    user_id: str,
) -> list[dict[str, Any]]:
    """List monitoring configs (alert thresholds + channels) for a user."""
    rows = self.execute_query(
        "SELECT id, user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
        "email_recipients, enabled, created_at, updated_at "
        "FROM claims_monitoring_config WHERE user_id = ? ORDER BY id DESC",
        (str(user_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def create_claims_monitoring_config(
    self,
    *,
    user_id: str,
    threshold_ratio: float | None = None,
    baseline_ratio: float | None = None,
    slack_webhook_url: str | None = None,
    webhook_url: str | None = None,
    email_recipients: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    """Create a monitoring config row and return it."""
    now = self._get_current_utc_timestamp_str()
    insert_sql = (
        "INSERT INTO claims_monitoring_config "
        "(user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
        "email_recipients, enabled, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    if self.backend_type == BackendType.POSTGRESQL:
        insert_sql += " RETURNING id"
    cursor = self.execute_query(
        insert_sql,
        (
            str(user_id),
            threshold_ratio,
            baseline_ratio,
            slack_webhook_url,
            webhook_url,
            email_recipients,
            1 if enabled else 0,
            now,
            now,
        ),
        commit=True,
    )
    if self.backend_type == BackendType.POSTGRESQL:
        row = cursor.fetchone()
        config_id = int(row["id"]) if row else None
    else:
        config_id = cursor.lastrowid
    return get_claims_monitoring_config(self, config_id) if config_id else {}


def get_claims_monitoring_config(self, config_id: int) -> dict[str, Any]:
    row = self.execute_query(
        "SELECT id, user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
        "email_recipients, enabled, created_at, updated_at "
        "FROM claims_monitoring_config WHERE id = ?",
        (int(config_id),),
    ).fetchone()
    return dict(row) if row else {}


def update_claims_monitoring_config(
    self,
    config_id: int,
    *,
    threshold_ratio: float | None = None,
    baseline_ratio: float | None = None,
    slack_webhook_url: str | None = None,
    webhook_url: str | None = None,
    email_recipients: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    update_parts: list[str] = []
    params: list[Any] = []
    now = self._get_current_utc_timestamp_str()

    if threshold_ratio is not None:
        update_parts.append("threshold_ratio = ?")
        params.append(float(threshold_ratio))
    if baseline_ratio is not None:
        update_parts.append("baseline_ratio = ?")
        params.append(float(baseline_ratio))
    if slack_webhook_url is not None:
        update_parts.append("slack_webhook_url = ?")
        params.append(str(slack_webhook_url))
    if webhook_url is not None:
        update_parts.append("webhook_url = ?")
        params.append(str(webhook_url))
    if email_recipients is not None:
        update_parts.append("email_recipients = ?")
        params.append(str(email_recipients))
    if enabled is not None:
        update_parts.append("enabled = ?")
        params.append(1 if enabled else 0)

    if not update_parts:
        return get_claims_monitoring_config(self, int(config_id))

    update_parts.append("updated_at = ?")
    params.append(now)
    params.append(int(config_id))
    sql = "UPDATE claims_monitoring_config SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
    self.execute_query(sql, tuple(params), commit=True)
    return get_claims_monitoring_config(self, int(config_id))


def delete_claims_monitoring_config(self, config_id: int) -> None:
    self.execute_query(
        "DELETE FROM claims_monitoring_config WHERE id = ?",
        (int(config_id),),
        commit=True,
    )


def list_claims_monitoring_user_ids(self) -> list[str]:
    rows = self.execute_query(
        (
            "SELECT DISTINCT user_id FROM claims_monitoring_alerts "
            "UNION SELECT DISTINCT user_id FROM claims_monitoring_settings"
        ),
        (),
    ).fetchall()
    user_ids: list[str] = []
    for row in rows:
        try:
            user_id = row["user_id"]
        except _MEDIA_NONCRITICAL_EXCEPTIONS:
            try:
                user_id = row[0]
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                continue
        if user_id is None:
            continue
        user_ids.append(str(user_id))
    return [uid for uid in user_ids if uid]
