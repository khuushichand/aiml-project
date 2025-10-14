"""PostgreSQL migration tests for the Workflows database."""

from __future__ import annotations

import os

import pytest

from tldw_Server_API.app.core.DB_Management.Workflows_DB import WorkflowsDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

try:
    import psycopg as _psycopg_v3  # type: ignore
    _PG_DRIVER = "psycopg"
except Exception:  # pragma: no cover - optional dependency
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None

_REQUIRED_ENV = (
    "POSTGRES_TEST_HOST",
    "POSTGRES_TEST_PORT",
    "POSTGRES_TEST_DB",
    "POSTGRES_TEST_USER",
    "POSTGRES_TEST_PASSWORD",
)

pytestmark = pytest.mark.skipif(_PG_DRIVER is None, reason="Postgres driver not installed")


def _postgres_config() -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
        pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
        pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
        pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
        pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
    )


def _reset_postgres_database(config: DatabaseConfig) -> None:
    assert _PG_DRIVER is not None
    if _PG_DRIVER == "psycopg":
        conn = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname=config.pg_database,
            user=config.pg_user,
            password=config.pg_password,
        )
    else:
        conn = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database=config.pg_database,
            user=config.pg_user,
            password=config.pg_password,
        )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    finally:
        conn.close()


_LEGACY_WORKFLOW_STATEMENTS = (
    """
CREATE TABLE workflows (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private',
    description TEXT,
    tags TEXT,
    definition_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (tenant_id, name, version)
)
""",
    """
CREATE TABLE workflow_runs (
    run_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    workflow_id INTEGER,
    status TEXT NOT NULL,
    status_reason TEXT,
    user_id TEXT NOT NULL,
    inputs_json TEXT NOT NULL,
    outputs_json TEXT,
    error TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    definition_version INTEGER,
    definition_snapshot_json TEXT,
    idempotency_key TEXT,
    session_id TEXT,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
)
""",
    """
CREATE TABLE workflow_step_runs (
    step_run_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    name TEXT,
    type TEXT,
    status TEXT,
    attempt INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    inputs_json TEXT,
    outputs_json TEXT,
    error TEXT,
    decision TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    review_comment TEXT,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ
)
""",
    """
CREATE TABLE workflow_events (
    event_id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_run_id TEXT,
    event_seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
)
""",
)


def _column_exists(backend, conn, table: str, column: str) -> bool:
    result = backend.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table, column),
        connection=conn,
    )
    return bool(result.rows)


@pytest.mark.integration
def test_workflows_postgres_schema_migration_adds_missing_columns() -> None:
    config = _postgres_config()
    _reset_postgres_database(config)
    backend = DatabaseBackendFactory.create_backend(config)

    try:
        with backend.transaction() as conn:
            for stmt in _LEGACY_WORKFLOW_STATEMENTS:
                backend.execute(stmt, connection=conn)

        # Instantiating the database should apply migrations and bump schema version.
        db = WorkflowsDatabase(db_path=":memory:", backend=backend)

        with backend.transaction() as conn:
            assert _column_exists(backend, conn, "workflow_runs", "cancel_requested")
            assert _column_exists(backend, conn, "workflow_runs", "tokens_input")
            assert _column_exists(backend, conn, "workflow_runs", "tokens_output")
            assert _column_exists(backend, conn, "workflow_runs", "cost_usd")

            for column in ("pid", "pgid", "workdir", "stdout_path", "stderr_path"):
                assert _column_exists(backend, conn, "workflow_step_runs", column)

            assert backend.table_exists("workflow_artifacts", connection=conn)
            # Per-run event counters table present
            assert backend.table_exists("workflow_event_counters", connection=conn)

            version = backend.execute(
                "SELECT version FROM workflow_schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == WorkflowsDatabase._CURRENT_SCHEMA_VERSION

    finally:
        pool = backend.get_pool()
        if pool:
            pool.close_all()
