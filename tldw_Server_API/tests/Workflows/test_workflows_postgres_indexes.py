"""PostgreSQL schema/index tests for Workflows DB (fresh and legacy).

Skips if Postgres driver is unavailable.
"""

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

pytestmark = pytest.mark.skipif(_PG_DRIVER is None, reason="Postgres driver not installed")


def _postgres_config_from_params(params: dict) -> DatabaseConfig:
    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=params["host"],
        pg_port=int(params["port"]),
        pg_database=params["database"],
        pg_user=params["user"],
        pg_password=params.get("password"),
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
        conn = _psycopg2.connect(  # type: ignore[name-defined]
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


def _index_def(backend, conn, table: str, name: str) -> str:
    res = backend.execute(
        "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=%s AND indexname=%s",
        (table, name),
        connection=conn,
    )
    return (res.rows[0]["indexdef"]) if res.rows else ""


@pytest.mark.integration
def test_workflows_postgres_fresh_schema_has_jsonb_and_indexes(pg_eval_params) -> None:
    config = _postgres_config_from_params(pg_eval_params)
    _reset_postgres_database(config)
    backend = DatabaseBackendFactory.create_backend(config)

    try:
        # Fresh initialization should create schema and migrations up to current version
        WorkflowsDatabase(db_path=":memory:", backend=backend)

        with backend.transaction() as conn:
            # payload_json is JSONB
            col_type = backend.execute(
                """
                SELECT data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s AND column_name=%s
                LIMIT 1
                """,
                ("workflow_events", "payload_json"),
                connection=conn,
            ).scalar
            assert str(col_type).lower() == "jsonb"

            # GIN index exists on payload_json
            gin_def = _index_def(backend, conn, "workflow_events", "idx_events_payload_json_gin")
            assert gin_def and "using gin" in gin_def.lower()

            # Unique index on (run_id, event_seq)
            uniq_def = _index_def(backend, conn, "workflow_events", "ux_events_run_seq")
            assert uniq_def and "unique" in uniq_def.lower() and "(run_id, event_seq)" in uniq_def

            # Partial indexes for hot/terminal statuses
            running_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_running")
            assert running_def and ("where" in running_def.lower() and "running" in running_def.lower())
            queued_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_queued")
            assert queued_def and ("where" in queued_def.lower() and "queued" in queued_def.lower())
            succ_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_succeeded")
            assert succ_def and ("where" in succ_def.lower() and "succeeded" in succ_def.lower())
            fail_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_failed")
            assert fail_def and ("where" in fail_def.lower() and "failed" in fail_def.lower())

            # Schema version table exists and equals current
            version = backend.execute(
                "SELECT version FROM workflow_schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == WorkflowsDatabase._CURRENT_SCHEMA_VERSION
    finally:
        pool = backend.get_pool()
        if pool:
            pool.close_all()


@pytest.mark.integration
def test_workflows_postgres_migration_preserves_indexes_from_legacy(pg_eval_params) -> None:
    # Start with a legacy schema then instantiate WorkflowsDatabase to migrate
    LEGACY_STMTS = (
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

    config = _postgres_config_from_params(pg_eval_params)
    _reset_postgres_database(config)
    backend = DatabaseBackendFactory.create_backend(config)

    try:
        with backend.transaction() as conn:
            for stmt in LEGACY_STMTS:
                backend.execute(stmt, connection=conn)

        # Trigger migrations
        WorkflowsDatabase(db_path=":memory:", backend=backend)

        with backend.transaction() as conn:
            # JSONB and GIN index present post-migration
            col_type = backend.execute(
                "SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s LIMIT 1",
                ("workflow_events", "payload_json"),
                connection=conn,
            ).scalar
            assert str(col_type).lower() == "jsonb"

            gin_def = _index_def(backend, conn, "workflow_events", "idx_events_payload_json_gin")
            assert gin_def and "using gin" in gin_def.lower()

            # Unique event sequence per run
            uniq_def = _index_def(backend, conn, "workflow_events", "ux_events_run_seq")
            assert uniq_def and "unique" in uniq_def.lower()

            # Partial indexes for hot/terminal statuses
            running_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_running")
            queued_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_queued")
            succ_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_succeeded")
            fail_def = _index_def(backend, conn, "workflow_runs", "idx_runs_status_failed")
            assert running_def and queued_def and succ_def and fail_def

            version = backend.execute(
                "SELECT version FROM workflow_schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == WorkflowsDatabase._CURRENT_SCHEMA_VERSION
    finally:
        pool = backend.get_pool()
        if pool:
            pool.close_all()
