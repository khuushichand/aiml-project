import sqlite3

import pytest


pytestmark = pytest.mark.unit


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def test_migration_017_extend_api_keys_virtual_adds_columns() -> None:


    from tldw_Server_API.app.core.AuthNZ.migrations import (
        migration_001_create_users_table,
        migration_003_create_api_keys_table,
        migration_004_create_api_key_audit_log,
        migration_016_create_orgs_teams,
        migration_017_extend_api_keys_virtual,
    )

    conn = sqlite3.connect(":memory:")
    try:
        migration_001_create_users_table(conn)
        migration_003_create_api_keys_table(conn)
        migration_004_create_api_key_audit_log(conn)
        migration_016_create_orgs_teams(conn)
        migration_017_extend_api_keys_virtual(conn)

        cols = _sqlite_columns(conn, "api_keys")
        for expected in (
            "is_virtual",
            "parent_key_id",
            "org_id",
            "team_id",
            "llm_budget_day_tokens",
            "llm_budget_month_tokens",
            "llm_budget_day_usd",
            "llm_budget_month_usd",
            "llm_allowed_endpoints",
            "llm_allowed_providers",
            "llm_allowed_models",
        ):
            assert expected in cols
    finally:
        conn.close()


def test_migration_085_removes_api_keys_scope_default() -> None:
    from tldw_Server_API.app.core.AuthNZ.migrations import (
        migration_001_create_users_table,
        migration_003_create_api_keys_table,
        migration_004_create_api_key_audit_log,
        migration_085_remove_api_keys_scope_default,
    )

    conn = sqlite3.connect(":memory:")
    try:
        migration_001_create_users_table(conn)
        migration_003_create_api_keys_table(conn)
        migration_004_create_api_key_audit_log(conn)

        migration_085_remove_api_keys_scope_default(conn)

        columns = conn.execute("PRAGMA table_info(api_keys)").fetchall()
        scope_row = next(row for row in columns if row[1] == "scope")
        assert scope_row[4] is None
    finally:
        conn.close()
