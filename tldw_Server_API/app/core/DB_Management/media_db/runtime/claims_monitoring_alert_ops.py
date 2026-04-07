"""Package-owned claims monitoring alert helpers."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def list_claims_monitoring_alerts(self, user_id: str) -> list[dict[str, Any]]:
    rows = self.execute_query(
        "SELECT id, user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
        "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at "
        "FROM claims_monitoring_alerts WHERE user_id = ? ORDER BY id DESC",
        (str(user_id),),
    ).fetchall()
    return [dict(row) for row in rows]


def get_claims_monitoring_alert(self, alert_id: int) -> dict[str, Any]:
    row = self.execute_query(
        "SELECT id, user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
        "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at "
        "FROM claims_monitoring_alerts WHERE id = ?",
        (int(alert_id),),
    ).fetchone()
    return dict(row) if row else {}


def create_claims_monitoring_alert(
    self,
    *,
    user_id: str,
    name: str,
    alert_type: str,
    channels_json: str,
    threshold_ratio: float | None = None,
    baseline_ratio: float | None = None,
    slack_webhook_url: str | None = None,
    webhook_url: str | None = None,
    email_recipients: str | None = None,
    enabled: bool = True,
    alert_id: int | None = None,
    created_at: str | None = None,
    updated_at: str | None = None,
) -> dict[str, Any]:
    now = self._get_current_utc_timestamp_str()
    created = created_at or now
    updated = updated_at or now
    if alert_id is not None:
        insert_sql = (
            "INSERT INTO claims_monitoring_alerts "
            "(id, user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
            "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        self.execute_query(
            insert_sql,
            (
                int(alert_id),
                str(user_id),
                str(name),
                str(alert_type),
                threshold_ratio,
                baseline_ratio,
                str(channels_json),
                slack_webhook_url,
                webhook_url,
                email_recipients,
                1 if enabled else 0,
                created,
                updated,
            ),
            commit=True,
        )
        if self.backend_type == BackendType.POSTGRESQL:
            with suppress(_MEDIA_NONCRITICAL_EXCEPTIONS):
                self.execute_query(
                    "SELECT setval(pg_get_serial_sequence('claims_monitoring_alerts','id'), "
                    "GREATEST((SELECT MAX(id) FROM claims_monitoring_alerts), 1))",
                    commit=True,
                )
        return get_claims_monitoring_alert(self, int(alert_id))

    insert_sql = (
        "INSERT INTO claims_monitoring_alerts "
        "(user_id, name, alert_type, threshold_ratio, baseline_ratio, channels_json, "
        "slack_webhook_url, webhook_url, email_recipients, enabled, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    if self.backend_type == BackendType.POSTGRESQL:
        insert_sql += " RETURNING id"
    cursor = self.execute_query(
        insert_sql,
        (
            str(user_id),
            str(name),
            str(alert_type),
            threshold_ratio,
            baseline_ratio,
            str(channels_json),
            slack_webhook_url,
            webhook_url,
            email_recipients,
            1 if enabled else 0,
            created,
            updated,
        ),
        commit=True,
    )
    if self.backend_type == BackendType.POSTGRESQL:
        row = cursor.fetchone()
        new_id = int(row["id"]) if row else None
    else:
        new_id = cursor.lastrowid
    return get_claims_monitoring_alert(self, int(new_id)) if new_id else {}


def update_claims_monitoring_alert(
    self,
    alert_id: int,
    *,
    name: str | None = None,
    alert_type: str | None = None,
    threshold_ratio: float | None = None,
    baseline_ratio: float | None = None,
    channels_json: str | None = None,
    slack_webhook_url: str | None = None,
    webhook_url: str | None = None,
    email_recipients: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    update_parts: list[str] = []
    params: list[Any] = []
    now = self._get_current_utc_timestamp_str()
    if name is not None:
        update_parts.append("name = ?")
        params.append(str(name))
    if alert_type is not None:
        update_parts.append("alert_type = ?")
        params.append(str(alert_type))
    if threshold_ratio is not None:
        update_parts.append("threshold_ratio = ?")
        params.append(float(threshold_ratio))
    if baseline_ratio is not None:
        update_parts.append("baseline_ratio = ?")
        params.append(float(baseline_ratio))
    if channels_json is not None:
        update_parts.append("channels_json = ?")
        params.append(str(channels_json))
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
        return get_claims_monitoring_alert(self, int(alert_id))
    update_parts.append("updated_at = ?")
    params.append(now)
    params.append(int(alert_id))
    sql = "UPDATE claims_monitoring_alerts SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
    self.execute_query(sql, tuple(params), commit=True)
    return get_claims_monitoring_alert(self, int(alert_id))


def delete_claims_monitoring_alert(self, alert_id: int) -> None:
    self.execute_query(
        "DELETE FROM claims_monitoring_alerts WHERE id = ?",
        (int(alert_id),),
        commit=True,
    )
