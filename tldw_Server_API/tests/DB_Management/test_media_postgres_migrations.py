import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


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
def test_media_postgres_migration_adds_safe_metadata(pg_database_config: DatabaseConfig) -> None:
    """Downgrade schema to v4 and ensure migration restores the v5 metadata column."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
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
def test_media_postgres_migration_reaches_v20_and_restores_workspace_tag(
    pg_database_config: DatabaseConfig,
) -> None:
    """Downgrade schema to v9 and ensure v10–v20 migrations repair late additions."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-migration-v19", backend=backend)

    try:
        with backend.transaction() as conn:
            backend.execute(
                "DROP INDEX IF EXISTS idx_data_tables_workspace_tag",
                connection=conn,
            )
            backend.execute(
                "ALTER TABLE data_tables DROP COLUMN IF EXISTS workspace_tag",
                connection=conn,
            )
            backend.execute(
                "DROP TABLE IF EXISTS claims_monitoring_events",
                connection=conn,
            )
            backend.execute(
                "UPDATE schema_version SET version = %s",
                (9,),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            assert _column_exists(backend, conn, "data_tables", "workspace_tag")
            assert backend.table_exists("claims_monitoring_events", connection=conn)
            version = backend.execute(
                "SELECT version FROM schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == db._CURRENT_SCHEMA_VERSION
    finally:
        db.close_connection()


@pytest.mark.integration
def test_media_postgres_sequence_sync(pg_database_config: DatabaseConfig) -> None:
    """Sequences are advanced to match table maxima after initialization."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
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
