from __future__ import annotations

from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_monitoring_health_ops import (
    get_claims_monitoring_health as helper_get_claims_monitoring_health,
    upsert_claims_monitoring_health as helper_upsert_claims_monitoring_health,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-monitoring-health-helper")
    db.initialize_db()
    return db


def test_get_claims_monitoring_health_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-monitoring-health-missing.db")
    try:
        assert db.get_claims_monitoring_health.__func__ is helper_get_claims_monitoring_health
        assert db.get_claims_monitoring_health("1") == {}
    finally:
        db.close_connection()


def test_upsert_claims_monitoring_health_inserts_initial_row_and_rebinds_method(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-health-insert.db")
    try:
        assert db.upsert_claims_monitoring_health.__func__ is helper_upsert_claims_monitoring_health

        row = db.upsert_claims_monitoring_health(
            user_id="1",
            queue_size=7,
            worker_count=2,
            last_worker_heartbeat="2024-01-01T00:00:00.000Z",
            last_processed_at="2024-01-01T00:00:05.000Z",
            last_failure_at="2024-01-01T00:00:10.000Z",
            last_failure_reason="boom",
        )

        assert int(row["id"]) > 0
        assert row["user_id"] == "1"
        assert int(row["queue_size"]) == 7
        assert int(row["worker_count"]) == 2
        assert row["last_worker_heartbeat"] == "2024-01-01T00:00:00.000Z"
        assert row["last_processed_at"] == "2024-01-01T00:00:05.000Z"
        assert row["last_failure_at"] == "2024-01-01T00:00:10.000Z"
        assert row["last_failure_reason"] == "boom"
        assert row["updated_at"]
    finally:
        db.close_connection()


def test_upsert_claims_monitoring_health_updates_existing_row_and_returns_refreshed_state(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-health-update.db")
    try:
        created = db.upsert_claims_monitoring_health(
            user_id="1",
            queue_size=7,
            worker_count=2,
            last_worker_heartbeat="2024-01-01T00:00:00.000Z",
            last_processed_at="2024-01-01T00:00:05.000Z",
            last_failure_at="2024-01-01T00:00:10.000Z",
            last_failure_reason="boom",
        )

        updated = db.upsert_claims_monitoring_health(
            user_id="1",
            queue_size=3,
            worker_count=1,
            last_worker_heartbeat="2024-01-02T00:00:00.000Z",
            last_processed_at="2024-01-02T00:00:05.000Z",
            last_failure_at=None,
            last_failure_reason=None,
        )

        assert int(updated["id"]) == int(created["id"])
        assert int(updated["queue_size"]) == 3
        assert int(updated["worker_count"]) == 1
        assert updated["last_worker_heartbeat"] == "2024-01-02T00:00:00.000Z"
        assert updated["last_processed_at"] == "2024-01-02T00:00:05.000Z"
        assert updated["last_failure_at"] is None
        assert updated["last_failure_reason"] is None
    finally:
        db.close_connection()
