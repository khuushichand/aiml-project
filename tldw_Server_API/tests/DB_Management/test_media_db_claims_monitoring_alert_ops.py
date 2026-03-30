from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_monitoring_alert_ops import (
    create_claims_monitoring_alert as helper_create_claims_monitoring_alert,
    delete_claims_monitoring_alert as helper_delete_claims_monitoring_alert,
    get_claims_monitoring_alert as helper_get_claims_monitoring_alert,
    list_claims_monitoring_alerts as helper_list_claims_monitoring_alerts,
    update_claims_monitoring_alert as helper_update_claims_monitoring_alert,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-monitoring-alert-helper")
    db.initialize_db()
    return db


def test_list_and_get_claims_monitoring_alerts_preserve_order_and_missing_behavior(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-alert-list.db")
    try:
        assert db.list_claims_monitoring_alerts.__func__ is helper_list_claims_monitoring_alerts
        assert db.get_claims_monitoring_alert.__func__ is helper_get_claims_monitoring_alert

        first = db.create_claims_monitoring_alert(
            user_id="1",
            name="First alert",
            alert_type="threshold_breach",
            channels_json='{"webhook": true}',
            threshold_ratio=0.4,
        )
        second = db.create_claims_monitoring_alert(
            user_id="1",
            name="Second alert",
            alert_type="threshold_breach",
            channels_json='{"email": true}',
            threshold_ratio=0.5,
        )

        rows = db.list_claims_monitoring_alerts("1")

        assert [int(row["id"]) for row in rows] == [int(second["id"]), int(first["id"])]
        assert db.get_claims_monitoring_alert(-1) == {}
    finally:
        db.close_connection()


def test_create_claims_monitoring_alert_preserves_explicit_alert_id(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-alert-create.db")
    try:
        assert db.create_claims_monitoring_alert.__func__ is helper_create_claims_monitoring_alert

        row = db.create_claims_monitoring_alert(
            user_id="1",
            name="Legacy alert",
            alert_type="threshold_breach",
            channels_json='{"slack": true, "email": true}',
            threshold_ratio=0.6,
            baseline_ratio=0.2,
            slack_webhook_url="https://example.com/slack",
            webhook_url=None,
            email_recipients='["alerts@example.com"]',
            enabled=True,
            alert_id=17,
            created_at="2026-03-22T00:00:00Z",
            updated_at="2026-03-22T00:00:01Z",
        )

        assert int(row["id"]) == 17
        assert row["name"] == "Legacy alert"
        assert row["channels_json"] == '{"slack": true, "email": true}'
        assert row["created_at"] == "2026-03-22T00:00:00Z"
        assert row["updated_at"] == "2026-03-22T00:00:01Z"
    finally:
        db.close_connection()


def test_update_and_delete_claims_monitoring_alert_preserve_noop_partial_and_delete_behavior(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-alert-update.db")
    try:
        assert db.update_claims_monitoring_alert.__func__ is helper_update_claims_monitoring_alert
        assert db.delete_claims_monitoring_alert.__func__ is helper_delete_claims_monitoring_alert

        created = db.create_claims_monitoring_alert(
            user_id="1",
            name="Original alert",
            alert_type="threshold_breach",
            channels_json='{"webhook": true}',
            threshold_ratio=0.5,
            baseline_ratio=0.1,
            webhook_url="https://example.com/original",
            email_recipients='["old@example.com"]',
            enabled=True,
        )

        unchanged = db.update_claims_monitoring_alert(int(created["id"]))
        updated = db.update_claims_monitoring_alert(
            int(created["id"]),
            name="Updated alert",
            threshold_ratio=0.7,
            enabled=False,
        )

        assert int(unchanged["id"]) == int(created["id"])
        assert unchanged["name"] == "Original alert"
        assert float(unchanged["threshold_ratio"]) == 0.5
        assert unchanged["webhook_url"] == "https://example.com/original"
        assert bool(unchanged["enabled"]) is True

        assert int(updated["id"]) == int(created["id"])
        assert updated["name"] == "Updated alert"
        assert float(updated["threshold_ratio"]) == 0.7
        assert float(updated["baseline_ratio"]) == 0.1
        assert updated["webhook_url"] == "https://example.com/original"
        assert updated["email_recipients"] == '["old@example.com"]'
        assert bool(updated["enabled"]) is False

        db.delete_claims_monitoring_alert(int(created["id"]))

        assert db.get_claims_monitoring_alert(int(created["id"])) == {}
    finally:
        db.close_connection()
