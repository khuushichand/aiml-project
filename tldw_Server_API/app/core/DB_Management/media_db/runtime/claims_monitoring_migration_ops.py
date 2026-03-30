"""Package-owned claims monitoring legacy migration coordinator."""

from __future__ import annotations

import json

from tldw_Server_API.app.core.DB_Management.media_db.runtime.noncritical import (
    MEDIA_NONCRITICAL_EXCEPTIONS,
)


_MEDIA_NONCRITICAL_EXCEPTIONS: tuple[type[BaseException], ...] = MEDIA_NONCRITICAL_EXCEPTIONS


def migrate_legacy_claims_monitoring_alerts(self, user_id: str) -> int:
    """Migrate legacy claims_monitoring_config rows into claims_monitoring_alerts."""
    existing = self.list_claims_monitoring_alerts(user_id)
    if existing:
        return 0
    legacy_rows = self.list_claims_monitoring_configs(user_id)
    if not legacy_rows:
        return 0
    migrated = 0
    for row in legacy_rows:
        slack_url = row.get("slack_webhook_url")
        webhook_url = row.get("webhook_url")
        email_recipients = row.get("email_recipients")
        email_enabled = False
        if email_recipients:
            try:
                parsed = json.loads(str(email_recipients))
                email_enabled = (
                    bool(parsed)
                    if isinstance(parsed, list)
                    else bool(str(email_recipients).strip())
                )
            except _MEDIA_NONCRITICAL_EXCEPTIONS:
                email_enabled = bool(str(email_recipients).strip())
        channels = {
            "slack": bool(slack_url),
            "webhook": bool(webhook_url),
            "email": email_enabled,
        }
        self.create_claims_monitoring_alert(
            alert_id=int(row.get("id")),
            user_id=str(user_id),
            name=f"Legacy alert {row.get('id')}",
            alert_type="threshold_breach",
            threshold_ratio=row.get("threshold_ratio"),
            baseline_ratio=row.get("baseline_ratio"),
            channels_json=json.dumps(channels),
            slack_webhook_url=slack_url,
            webhook_url=webhook_url,
            email_recipients=email_recipients,
            enabled=bool(row.get("enabled", True)),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
        migrated += 1
    self.delete_claims_monitoring_configs_by_user(str(user_id))
    return migrated
