from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_monitoring_migration_ops import (
    migrate_legacy_claims_monitoring_alerts,
)


pytestmark = pytest.mark.unit


def test_migrate_legacy_claims_monitoring_alerts_short_circuits_when_alerts_exist() -> None:
    calls: list[tuple[str, object]] = []

    fake_db = SimpleNamespace(
        list_claims_monitoring_alerts=lambda user_id: calls.append(("alerts", user_id)) or [{"id": 1}],
        list_claims_monitoring_configs=lambda user_id: calls.append(("configs", user_id)) or [{"id": 1}],
    )

    migrated = migrate_legacy_claims_monitoring_alerts(fake_db, "1")

    assert migrated == 0
    assert calls == [("alerts", "1")]


def test_migrate_legacy_claims_monitoring_alerts_short_circuits_when_no_legacy_rows() -> None:
    calls: list[tuple[str, object]] = []

    fake_db = SimpleNamespace(
        list_claims_monitoring_alerts=lambda user_id: calls.append(("alerts", user_id)) or [],
        list_claims_monitoring_configs=lambda user_id: calls.append(("configs", user_id)) or [],
    )

    migrated = migrate_legacy_claims_monitoring_alerts(fake_db, "1")

    assert migrated == 0
    assert calls == [("alerts", "1"), ("configs", "1")]


def test_migrate_legacy_claims_monitoring_alerts_preserves_explicit_ids_and_deletes_configs_after_migration() -> None:
    created_alerts: list[dict[str, object]] = []
    deleted_users: list[str] = []
    legacy_rows = [
        {
            "id": 7,
            "threshold_ratio": 0.4,
            "baseline_ratio": 0.1,
            "slack_webhook_url": "https://example.com/slack",
            "webhook_url": "",
            "email_recipients": json.dumps(["alerts@example.com"]),
            "enabled": True,
            "created_at": "2026-03-22T01:00:00Z",
            "updated_at": "2026-03-22T02:00:00Z",
        }
    ]

    fake_db = SimpleNamespace(
        list_claims_monitoring_alerts=lambda user_id: [],
        list_claims_monitoring_configs=lambda user_id: legacy_rows,
        create_claims_monitoring_alert=lambda **kwargs: created_alerts.append(kwargs),
        delete_claims_monitoring_configs_by_user=lambda user_id: deleted_users.append(user_id),
    )

    migrated = migrate_legacy_claims_monitoring_alerts(fake_db, "1")

    assert migrated == 1
    assert created_alerts == [
        {
            "alert_id": 7,
            "user_id": "1",
            "name": "Legacy alert 7",
            "alert_type": "threshold_breach",
            "threshold_ratio": 0.4,
            "baseline_ratio": 0.1,
            "channels_json": json.dumps({"slack": True, "webhook": False, "email": True}),
            "slack_webhook_url": "https://example.com/slack",
            "webhook_url": "",
            "email_recipients": json.dumps(["alerts@example.com"]),
            "enabled": True,
            "created_at": "2026-03-22T01:00:00Z",
            "updated_at": "2026-03-22T02:00:00Z",
        }
    ]
    assert deleted_users == ["1"]


def test_migrate_legacy_claims_monitoring_alerts_treats_malformed_truthy_email_as_enabled() -> None:
    created_alerts: list[dict[str, object]] = []

    fake_db = SimpleNamespace(
        list_claims_monitoring_alerts=lambda user_id: [],
        list_claims_monitoring_configs=lambda user_id: [
            {
                "id": 11,
                "threshold_ratio": None,
                "baseline_ratio": None,
                "slack_webhook_url": None,
                "webhook_url": None,
                "email_recipients": "not-json-but-present",
                "enabled": False,
                "created_at": None,
                "updated_at": None,
            }
        ],
        create_claims_monitoring_alert=lambda **kwargs: created_alerts.append(kwargs),
        delete_claims_monitoring_configs_by_user=lambda user_id: None,
    )

    migrated = migrate_legacy_claims_monitoring_alerts(fake_db, "9")

    assert migrated == 1
    assert json.loads(str(created_alerts[0]["channels_json"])) == {
        "slack": False,
        "webhook": False,
        "email": True,
    }
