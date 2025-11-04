from __future__ import annotations

import uuid
import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


def test_sync_log_entity_column_adapts_to_entity_uuid_on_postgres(tmp_path, pg_database_config: DatabaseConfig):
    backend = DatabaseBackendFactory.create_backend(pg_database_config)
    # Initialize ChaCha DB on the empty temp database provided by fixture
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
                backend.get_pool().close_all()
            except Exception:
                pass
