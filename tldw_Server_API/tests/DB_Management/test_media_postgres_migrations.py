import uuid

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
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


def _index_exists(backend, conn, index_name: str) -> bool:
    """Return True if the supplied PostgreSQL index exists in public schema."""

    result = backend.execute(
        """
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'public'
          AND indexname = %s
        LIMIT 1
        """,
        (index_name,),
        connection=conn,
    )
    return bool(result.rows)


def _constraint_exists(backend, conn, constraint_name: str) -> bool:
    """Return True if the supplied PostgreSQL constraint exists on public tables."""

    result = backend.execute(
        """
        SELECT 1
        FROM pg_constraint
        WHERE conname = %s
        LIMIT 1
        """,
        (constraint_name,),
        connection=conn,
    )
    return bool(result.rows)


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
def test_media_postgres_migration_reaches_v11_and_restores_mediafiles_table(
    pg_database_config: DatabaseConfig,
) -> None:
    """Downgrade schema to v10 and ensure v11 restores the MediaFiles table."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-migration-v11", backend=backend)

    try:
        with backend.transaction() as conn:
            backend.execute("DROP TABLE IF EXISTS MediaFiles", connection=conn)
            backend.execute(
                "UPDATE schema_version SET version = %s",
                (10,),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            assert backend.table_exists("MediaFiles", connection=conn)
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
def test_media_postgres_migration_reaches_v9_and_restores_visibility_owner_columns(
    pg_database_config: DatabaseConfig,
) -> None:
    """Downgrade schema to v8 and ensure v9 restores visibility-owner artifacts."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-migration-v9", backend=backend)
    media_uuid = str(uuid.uuid4())

    try:
        with backend.transaction() as conn:
            now = db._get_current_utc_timestamp_str()
            backend.execute(
                """
                INSERT INTO Media (uuid, title, type, content_hash, last_modified, version, client_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    media_uuid,
                    "Visibility migration",
                    "text",
                    f"hash-{media_uuid}",
                    now,
                    1,
                    "321",
                ),
                connection=conn,
            )
            backend.execute(
                "ALTER TABLE media DROP CONSTRAINT IF EXISTS chk_media_visibility",
                connection=conn,
            )
            backend.execute("DROP INDEX IF EXISTS idx_media_visibility", connection=conn)
            backend.execute(
                "DROP INDEX IF EXISTS idx_media_owner_user_id",
                connection=conn,
            )
            backend.execute(
                "ALTER TABLE media DROP COLUMN IF EXISTS owner_user_id",
                connection=conn,
            )
            backend.execute(
                "ALTER TABLE media DROP COLUMN IF EXISTS visibility",
                connection=conn,
            )
            backend.execute(
                "UPDATE schema_version SET version = %s",
                (8,),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            assert _column_exists(backend, conn, "media", "visibility")
            assert _column_exists(backend, conn, "media", "owner_user_id")
            assert _index_exists(backend, conn, "idx_media_visibility")
            assert _index_exists(backend, conn, "idx_media_owner_user_id")
            assert _constraint_exists(backend, conn, "chk_media_visibility")
            owner_user_id = backend.execute(
                "SELECT owner_user_id FROM media WHERE uuid = %s",
                (media_uuid,),
                connection=conn,
            ).scalar
            assert int(owner_user_id) == 321
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


@pytest.mark.integration
def test_media_postgres_migration_reaches_v21_and_restores_structure_visual_indexes(
    pg_database_config: DatabaseConfig,
) -> None:
    """Downgrade schema to v20 and ensure v21 restores structure and visual indexes."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-migration-v21", backend=backend)

    try:
        with backend.transaction() as conn:
            backend.execute("DROP INDEX IF EXISTS idx_dsi_media_path", connection=conn)
            backend.execute("DROP INDEX IF EXISTS idx_visualdocs_caption", connection=conn)
            backend.execute("DROP INDEX IF EXISTS idx_visualdocs_tags", connection=conn)
            backend.execute(
                "UPDATE schema_version SET version = %s",
                (20,),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            assert _index_exists(backend, conn, "idx_dsi_media_path")
            assert _index_exists(backend, conn, "idx_visualdocs_caption")
            assert _index_exists(backend, conn, "idx_visualdocs_tags")
            version = backend.execute(
                "SELECT version FROM schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == db._CURRENT_SCHEMA_VERSION
    finally:
        db.close_connection()


@pytest.mark.integration
def test_media_postgres_migration_reaches_v22_and_restores_email_schema(
    pg_database_config: DatabaseConfig,
) -> None:
    """Downgrade schema to v21 and ensure v22 restores stable email-native artifacts."""

    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    db = MediaDatabase(db_path=":memory:", client_id="pg-migration-v22", backend=backend)

    try:
        with backend.transaction() as conn:
            backend.execute("DROP TABLE IF EXISTS email_sources CASCADE", connection=conn)
            backend.execute(
                "DROP INDEX IF EXISTS idx_email_messages_tenant_date_id",
                connection=conn,
            )
            backend.execute(
                "UPDATE schema_version SET version = %s",
                (21,),
                connection=conn,
            )

        db._initialize_schema()

        with backend.transaction() as conn:
            assert backend.table_exists("email_sources", connection=conn)
            assert _index_exists(backend, conn, "idx_email_messages_tenant_date_id")
            version = backend.execute(
                "SELECT version FROM schema_version LIMIT 1",
                connection=conn,
            ).scalar
            assert int(version) == db._CURRENT_SCHEMA_VERSION
    finally:
        db.close_connection()
