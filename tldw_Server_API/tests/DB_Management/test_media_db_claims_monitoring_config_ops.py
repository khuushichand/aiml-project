from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)
from tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_monitoring_config_ops import (
    create_claims_monitoring_config as helper_create_claims_monitoring_config,
    delete_claims_monitoring_config as helper_delete_claims_monitoring_config,
    delete_claims_monitoring_configs_by_user as helper_delete_claims_monitoring_configs_by_user,
    get_claims_monitoring_config as helper_get_claims_monitoring_config,
    list_claims_monitoring_configs as helper_list_claims_monitoring_configs,
    list_claims_monitoring_user_ids as helper_list_claims_monitoring_user_ids,
    update_claims_monitoring_config as helper_update_claims_monitoring_config,
)


pytestmark = pytest.mark.unit


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-monitoring-config-helper")
    db.initialize_db()
    return db


def test_create_and_list_claims_monitoring_configs_rebind_and_preserve_order(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-config-list.db")
    try:
        assert db.create_claims_monitoring_config.__func__ is helper_create_claims_monitoring_config
        assert db.list_claims_monitoring_configs.__func__ is helper_list_claims_monitoring_configs

        first = db.create_claims_monitoring_config(user_id="1", threshold_ratio=0.4, enabled=True)
        second = db.create_claims_monitoring_config(user_id="1", threshold_ratio=0.6, enabled=False)
        listed = db.list_claims_monitoring_configs("1")

        assert [int(row["id"]) for row in listed] == [int(second["id"]), int(first["id"])]
    finally:
        db.close_connection()


def test_get_claims_monitoring_config_returns_empty_dict_when_missing(tmp_path: Path) -> None:
    db = _make_db(tmp_path, "claims-monitoring-config-missing.db")
    try:
        assert db.get_claims_monitoring_config.__func__ is helper_get_claims_monitoring_config
        assert db.get_claims_monitoring_config(9999) == {}
    finally:
        db.close_connection()


def test_update_and_delete_claims_monitoring_config_rebind_and_preserve_behavior(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-monitoring-config-update.db")
    try:
        assert db.update_claims_monitoring_config.__func__ is helper_update_claims_monitoring_config
        assert (
            db.delete_claims_monitoring_configs_by_user.__func__
            is helper_delete_claims_monitoring_configs_by_user
        )
        assert db.delete_claims_monitoring_config.__func__ is helper_delete_claims_monitoring_config

        created = db.create_claims_monitoring_config(
            user_id="1",
            threshold_ratio=0.4,
            baseline_ratio=0.1,
            slack_webhook_url="https://hooks.slack.test",
            enabled=True,
        )
        unchanged = db.update_claims_monitoring_config(int(created["id"]))
        updated = db.update_claims_monitoring_config(
            int(created["id"]),
            threshold_ratio=0.75,
            enabled=False,
        )

        assert float(unchanged["threshold_ratio"]) == 0.4
        assert bool(unchanged["enabled"]) is True
        assert float(updated["threshold_ratio"]) == 0.75
        assert bool(updated["enabled"]) is False

        db.delete_claims_monitoring_config(int(created["id"]))
        assert db.get_claims_monitoring_config(int(created["id"])) == {}

        other = db.create_claims_monitoring_config(user_id="1", threshold_ratio=0.2, enabled=True)
        db.delete_claims_monitoring_configs_by_user("1")
        assert db.list_claims_monitoring_configs("1") == []
        assert db.get_claims_monitoring_config(int(other["id"])) == {}
    finally:
        db.close_connection()


def test_create_claims_monitoring_config_preserves_postgres_returning_id_path() -> None:
    class _Cursor:
        lastrowid = None

        def fetchone(self):
            return {"id": 13}

    execute_calls: list[tuple[str, tuple[object, ...], bool]] = []

    def _execute_query(sql, params=None, commit=False):
        execute_calls.append((sql, tuple(params or ()), commit))
        return _Cursor()

    fake_db = SimpleNamespace(
        backend_type=BackendType.POSTGRESQL,
        _get_current_utc_timestamp_str=lambda: "2026-03-22T00:00:00Z",
        execute_query=_execute_query,
    )
    fake_db.get_claims_monitoring_config = lambda config_id: {"id": int(config_id)}

    created = helper_create_claims_monitoring_config(
        fake_db,
        user_id="1",
        threshold_ratio=0.4,
        baseline_ratio=0.1,
        slack_webhook_url=None,
        webhook_url="https://example.com/webhook",
        email_recipients='["alerts@example.com"]',
        enabled=True,
    )

    assert created == {"id": 13}
    assert execute_calls[0][0].endswith(" RETURNING id")


def test_list_claims_monitoring_user_ids_preserves_mapping_and_tuple_fallback() -> None:
    class _Cursor:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    rows = [{"user_id": "1"}, ("2",), {"user_id": ""}, (None,), object()]
    fake_db = SimpleNamespace(execute_query=lambda sql, params=None: _Cursor(rows))

    user_ids = helper_list_claims_monitoring_user_ids(fake_db)

    assert user_ids == ["1", "2"]
