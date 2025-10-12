import os
import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory

try:
    import psycopg as _psycopg_v3
    _PG_DRIVER = "psycopg"
except Exception:  # pragma: no cover - optional dependency for local runs
    try:
        import psycopg2 as _psycopg2
        _PG_DRIVER = "psycopg2"
    except Exception:
        _PG_DRIVER = None


_REQUIRED_ENV = [
    "POSTGRES_TEST_HOST",
    "POSTGRES_TEST_PORT",
    "POSTGRES_TEST_DB",
    "POSTGRES_TEST_USER",
    "POSTGRES_TEST_PASSWORD",
]

pytestmark = pytest.mark.skipif(_PG_DRIVER is None, reason="Postgres driver not installed")


@pytest.fixture()
def postgres_config() -> DatabaseConfig:
    """Provide a DatabaseConfig pointing at the Postgres test service."""

    return DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=os.getenv("POSTGRES_TEST_HOST", "127.0.0.1"),
        pg_port=int(os.getenv("POSTGRES_TEST_PORT", "5432")),
        pg_database=os.getenv("POSTGRES_TEST_DB", "tldw_users"),
        pg_user=os.getenv("POSTGRES_TEST_USER", "tldw_user"),
        pg_password=os.getenv("POSTGRES_TEST_PASSWORD", "TestPassword123!"),
    )


def _reset_postgres_database(config: DatabaseConfig) -> None:
    """Drop and recreate the public schema for a clean slate."""

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


def _column_exists(backend, conn, table: str, column: str) -> bool:
    """Return True if the supplied column is present on the table."""

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


def _serial_sequence_name(backend, conn, table: str, column: str) -> str:
    """Fetch the fully-qualified sequence backing a serial column."""

    result = backend.execute(
        "SELECT pg_get_serial_sequence(%s, %s) AS seq",
        (table, column),
        connection=conn,
    )
    sequence = result.scalar
    if not sequence:
        raise AssertionError(f"Sequence not found for {table}.{column}")
    return str(sequence)


@pytest.mark.integration
def test_media_postgres_migration_adds_safe_metadata(postgres_config: DatabaseConfig) -> None:
    """Downgrade schema to v4 and ensure migration restores the v5 metadata column."""

    _reset_postgres_database(postgres_config)
    backend = DatabaseBackendFactory.create_backend(postgres_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-migration", backend=backend)

    try:
        with backend.transaction() as conn:
            backend.execute(
                "ALTER TABLE DocumentVersions DROP COLUMN IF EXISTS safe_metadata",
                connection=conn,
            )
            backend.execute(
                "UPDATE schema_version SET version = %s",
                (4,),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            assert _column_exists(backend, conn, "documentversions", "safe_metadata")
            version = backend.execute(
                "SELECT version FROM schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == db._CURRENT_SCHEMA_VERSION
    finally:
        db.close_connection()


@pytest.mark.integration
def test_media_postgres_sequence_sync(postgres_config: DatabaseConfig) -> None:
    """Sequences are advanced to match table maxima after initialization."""

    _reset_postgres_database(postgres_config)
    backend = DatabaseBackendFactory.create_backend(postgres_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-seq", backend=backend)

    try:
        with backend.transaction() as conn:
            now = db._get_current_utc_timestamp_str()
            backend.execute(
                """
                INSERT INTO Media (title, type, content_hash, uuid, last_modified, version, client_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    "Sequence sync",
                    "text",
                    "hash-123",
                    str(uuid.uuid4()),
                    now,
                    1,
                    db.client_id,
                ),
                connection=conn,
            )

        with backend.transaction() as conn:
            sequence = _serial_sequence_name(backend, conn, "media", "id")
            backend.execute(
                "SELECT setval(%s, %s, false)",
                (sequence, 1),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            sequence = _serial_sequence_name(backend, conn, "media", "id")
            next_value = backend.execute(
                "SELECT nextval(%s)",
                (sequence,),
                connection=conn,
            ).scalar
        assert int(next_value) > 1
    finally:
        db.close_connection()
