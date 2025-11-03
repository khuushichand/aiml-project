from __future__ import annotations

import os
import uuid
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

try:
    import psycopg as _psycopg_v3  # type: ignore
    _PG = True
except Exception:
    try:
        import psycopg2 as _psycopg2  # type: ignore
        _PG = True
    except Exception:
        _PG = False


pytestmark = pytest.mark.skipif(not _PG, reason="Postgres driver not installed")


def _create_temp_postgres_database(base_config: DatabaseConfig) -> DatabaseConfig:
    """Create an isolated temporary Postgres database for this test.

    Mirrors the pattern used in other Postgres tests to avoid mutating shared
    schemas/databases (e.g., DROP SCHEMA on a common DB).
    """
    assert _PG, "Postgres driver is required for this test"

    temp_db = f"tldw_test_{uuid.uuid4().hex[:8]}"

    try:
        import psycopg as _psycopg_v3  # type: ignore
        _conn = _psycopg_v3.connect(
            host=base_config.pg_host,
            port=base_config.pg_port,
            dbname="postgres",
            user=base_config.pg_user,
            password=base_config.pg_password,
        )
    except Exception:
        import psycopg2 as _psycopg2  # type: ignore
        _conn = _psycopg2.connect(
            host=base_config.pg_host,
            port=base_config.pg_port,
            database="postgres",
            user=base_config.pg_user,
            password=base_config.pg_password,
        )
    _conn.autocommit = True
    try:
        with _conn.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{temp_db}" OWNER {base_config.pg_user}')
    finally:
        _conn.close()

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=base_config.pg_host,
        pg_port=base_config.pg_port,
        pg_database=temp_db,
        pg_user=base_config.pg_user,
        pg_password=base_config.pg_password,
    )


def _drop_temp_postgres_database(config: DatabaseConfig) -> None:
    """Drop the temporary Postgres database created for this test."""
    assert _PG, "Postgres driver is required for this test"

    try:
        import psycopg as _psycopg_v3  # type: ignore
        _conn = _psycopg_v3.connect(
            host=config.pg_host,
            port=config.pg_port,
            dbname="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    except Exception:
        import psycopg2 as _psycopg2  # type: ignore
        _conn = _psycopg2.connect(
            host=config.pg_host,
            port=config.pg_port,
            database="postgres",
            user=config.pg_user,
            password=config.pg_password,
        )
    _conn.autocommit = True
    try:
        with _conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s;",
                (config.pg_database,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{config.pg_database}"')
    finally:
        _conn.close()


def test_sync_log_entity_column_adapts_to_entity_uuid_on_postgres(tmp_path, pg_eval_params):
    base_config = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=pg_eval_params["host"],
        pg_port=int(pg_eval_params["port"]),
        pg_database=pg_eval_params["database"],
        pg_user=pg_eval_params["user"],
        pg_password=pg_eval_params.get("password"),
    )

    # Use an isolated temp database so we don't require a pre-created DB and
    # we don't clobber a shared schema in CI runs.
    try:
        temp_config = _create_temp_postgres_database(base_config)
    except Exception as e:
        require_pg = os.getenv("TLDW_TEST_POSTGRES_REQUIRED", "").lower() in ("1", "true", "yes")
        if not require_pg:
            pytest.skip(f"PostgreSQL not available for temp DB ({e}); skipping Postgres-specific test.")
        raise

    backend = DatabaseBackendFactory.create_backend(temp_config)

    # Quick connectivity probe to surface any env issues clearly
    require_pg = os.getenv("TLDW_TEST_POSTGRES_REQUIRED", "").lower() in ("1", "true", "yes")
    try:
        with backend.transaction() as _conn:
            pass
    except Exception as e:
        if not require_pg:
            pytest.skip(f"PostgreSQL not available ({e}); skipping Postgres-specific test.")
        # Ensure cleanup of temp DB even on failure
        try:
            _drop_temp_postgres_database(temp_config)
        finally:
            raise

    # Initialize ChaCha DB on the empty temp database
    db = CharactersRAGDB(db_path=":memory:", client_id="sync-test", backend=backend)
    try:
        # Replace sync_log with a version that uses entity_uuid to simulate shared schema from Media DB
        with backend.transaction() as conn:
            backend.execute("DROP TABLE IF EXISTS sync_log", connection=conn)
            backend.execute(
                """
                CREATE TABLE sync_log(
                  change_id   BIGSERIAL PRIMARY KEY,
                  entity      TEXT NOT NULL,
                  entity_uuid TEXT NOT NULL,
                  operation   TEXT NOT NULL,
                  timestamp   TIMESTAMPTZ NOT NULL,
                  client_id   TEXT NOT NULL,
                  version     INTEGER NOT NULL,
                  payload     TEXT NOT NULL
                )
                """,
                connection=conn,
            )

        # Create keyword + note and then link them to force a sync_log insert
        kid = db.add_keyword("x-sync")
        assert kid is not None
        note_id = db.add_note("T", "C")
        assert note_id is not None
        linked = db.link_note_to_keyword(note_id, int(kid))
        assert linked is True

        # Validate sync_log row exists and entity_uuid column was used
        with backend.transaction() as conn:
            rows = backend.execute(
                "SELECT entity, entity_uuid FROM sync_log ORDER BY change_id DESC LIMIT 1",
                connection=conn,
            ).rows
            assert rows, "Expected a sync_log row after linking"
            last = rows[0]
            assert last.get("entity") == "note_keywords"
            assert "_" in last.get("entity_uuid", "")
    finally:
        try:
            db.close_connection()
        finally:
            try:
                # Close any pooled connections before dropping the DB
                backend.get_pool().close_all()
            except Exception:
                pass
            try:
                _drop_temp_postgres_database(temp_config)
            except Exception:
                pass
