from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_monitoring_settings_ops import (
    get_claims_monitoring_settings as helper_get_claims_monitoring_settings,
    upsert_claims_monitoring_settings as helper_upsert_claims_monitoring_settings,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-monitoring-settings-helper")
    db.initialize_db()
    return db


def test_get_claims_monitoring_settings_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-monitoring-settings-missing.db")
    try:
        assert db.get_claims_monitoring_settings.__func__ is helper_get_claims_monitoring_settings
        assert db.get_claims_monitoring_settings("1") == {}
    finally:
        db.close_connection()


def test_upsert_claims_monitoring_settings_insert_defaults_enabled_and_rebinds_method(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-settings-insert.db")
    try:
        assert db.upsert_claims_monitoring_settings.__func__ is helper_upsert_claims_monitoring_settings

        row = db.upsert_claims_monitoring_settings(
            user_id="1",
            threshold_ratio=0.4,
            baseline_ratio=0.1,
            slack_webhook_url=None,
            webhook_url="https://example.com/webhook",
            email_recipients='["alerts@example.com"]',
            enabled=None,
        )

        assert int(row["id"]) > 0
        assert row["user_id"] == "1"
        assert float(row["threshold_ratio"]) == 0.4
        assert float(row["baseline_ratio"]) == 0.1
        assert row["slack_webhook_url"] is None
        assert row["webhook_url"] == "https://example.com/webhook"
        assert row["email_recipients"] == '["alerts@example.com"]'
        assert bool(row["enabled"]) is True
        assert row["created_at"]
        assert row["updated_at"]
    finally:
        db.close_connection()


def test_upsert_claims_monitoring_settings_preserves_noop_and_partial_update_behavior(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-settings-update.db")
    try:
        created = db.upsert_claims_monitoring_settings(
            user_id="1",
            threshold_ratio=0.5,
            baseline_ratio=0.2,
            slack_webhook_url="https://hooks.slack.test/old",
            webhook_url="https://example.com/old",
            email_recipients='["old@example.com"]',
            enabled=False,
        )

        unchanged = db.upsert_claims_monitoring_settings(user_id="1")
        updated = db.upsert_claims_monitoring_settings(
            user_id="1",
            threshold_ratio=0.6,
            webhook_url="https://example.com/new",
            enabled=True,
        )

        assert int(unchanged["id"]) == int(created["id"])
        assert float(unchanged["threshold_ratio"]) == 0.5
        assert float(unchanged["baseline_ratio"]) == 0.2
        assert unchanged["webhook_url"] == "https://example.com/old"
        assert bool(unchanged["enabled"]) is False

        assert int(updated["id"]) == int(created["id"])
        assert float(updated["threshold_ratio"]) == 0.6
        assert float(updated["baseline_ratio"]) == 0.2
        assert updated["slack_webhook_url"] == "https://hooks.slack.test/old"
        assert updated["webhook_url"] == "https://example.com/new"
        assert updated["email_recipients"] == '["old@example.com"]'
        assert bool(updated["enabled"]) is True
    finally:
        db.close_connection()
