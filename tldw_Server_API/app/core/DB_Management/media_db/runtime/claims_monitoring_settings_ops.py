"""Package-owned claims monitoring settings helpers."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def get_claims_monitoring_settings(self, user_id: str) -> dict[str, Any]:
    row = self.execute_query(
        "SELECT id, user_id, threshold_ratio, baseline_ratio, slack_webhook_url, webhook_url, "
        "email_recipients, enabled, created_at, updated_at "
        "FROM claims_monitoring_settings WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1",
        (str(user_id),),
    ).fetchone()
    return dict(row) if row else {}


def upsert_claims_monitoring_settings(
    self,
    *,
    user_id: str,
    threshold_ratio: float | None = None,
    baseline_ratio: float | None = None,
    slack_webhook_url: str | None = None,
    webhook_url: str | None = None,
    email_recipients: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    existing = get_claims_monitoring_settings(self, str(user_id))
    now = self._get_current_utc_timestamp_str()
    if not existing:
        insert_sql = (
            "INSERT INTO claims_monitoring_settings "
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
                1 if enabled is None else (1 if enabled else 0),
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
        return get_claims_monitoring_settings(self, str(user_id)) if config_id else {}

    update_parts: list[str] = []
    params: list[Any] = []
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
        return get_claims_monitoring_settings(self, str(user_id))

    update_parts.append("updated_at = ?")
    params.append(now)
    params.append(int(existing.get("id")))
    sql = "UPDATE claims_monitoring_settings SET " + ", ".join(update_parts) + " WHERE id = ?"  # nosec B608
    self.execute_query(sql, tuple(params), commit=True)
    return get_claims_monitoring_settings(self, str(user_id))
