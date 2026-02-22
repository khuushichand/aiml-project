import sqlite3

from tldw_Server_API.app.core.AuthNZ.migrations import (
    migration_001_create_users_table,
    migration_003_create_api_keys_table,
    migration_012_create_rbac_tables,
    migration_013_create_rbac_limits_and_usage,
    migration_015_create_llm_usage_tables,
)


def _prepare_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    migration_001_create_users_table(conn)
    migration_003_create_api_keys_table(conn)
    migration_012_create_rbac_tables(conn)
    return conn


def _fk_count(conn: sqlite3.Connection, table_name: str) -> int:
    rows = conn.execute(f"PRAGMA foreign_key_list({table_name})").fetchall()
    return len(rows)


def test_migration_013_relaxes_fks_when_tldw_test_mode_is_y(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "y")
    monkeypatch.delenv("DISABLE_USAGE_FOREIGN_KEYS", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    conn = _prepare_conn()
    migration_013_create_rbac_limits_and_usage(conn)

    assert _fk_count(conn, "usage_log") == 0
    assert _fk_count(conn, "usage_daily") == 0


def test_migration_015_relaxes_fks_when_tldw_test_mode_is_y(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "y")
    monkeypatch.delenv("DISABLE_USAGE_FOREIGN_KEYS", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    conn = _prepare_conn()
    migration_015_create_llm_usage_tables(conn)

    assert _fk_count(conn, "llm_usage_log") == 0
    assert _fk_count(conn, "llm_usage_daily") == 0


def test_migrations_013_and_015_keep_fks_when_test_flags_disabled(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")
    monkeypatch.delenv("DISABLE_USAGE_FOREIGN_KEYS", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    conn = _prepare_conn()
    migration_013_create_rbac_limits_and_usage(conn)
    migration_015_create_llm_usage_tables(conn)

    assert _fk_count(conn, "usage_log") >= 1
    assert _fk_count(conn, "usage_daily") >= 1
    assert _fk_count(conn, "llm_usage_log") >= 1
    assert _fk_count(conn, "llm_usage_daily") >= 1
