
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, List, Tuple
from unittest.mock import MagicMock
import uuid

from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


def _insert_claim_record(db: MediaDatabase) -> None:
    """Helper to seed a minimal media + claim pair."""
    timestamp = db._get_current_utc_timestamp_str()
    media_uuid = str(uuid.uuid4())
    claim_uuid = str(uuid.uuid4())

    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO Media (uuid, title, type, content_hash, last_modified, version, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                media_uuid,
                "Test media",
                "text",
                f"media-hash-{media_uuid}",
                timestamp,
                1,
                db.client_id,
            ),
        )
        media_id = conn.execute(
            "SELECT id FROM Media WHERE uuid = ?",
            (media_uuid,),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO Claims (media_id, chunk_index, claim_text, chunk_hash, extractor, extractor_version, created_at, uuid, last_modified, version, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                media_id,
                0,
                "Confidence in backend migrations",
                f"chunk-hash-{claim_uuid}",
                "pytest",
                "v1",
                timestamp,
                claim_uuid,
                timestamp,
                1,
                db.client_id,
            ),
        )


def test_rebuild_claims_fts_sqlite_populates_index(tmp_path: Path) -> None:
    db_path = tmp_path / "media.sqlite"
    db = MediaDatabase(str(db_path), client_id="test-client")
    try:
        _insert_claim_record(db)

        indexed = db.rebuild_claims_fts()
        assert indexed == 1

        cursor = db.execute_query("SELECT claim_text FROM claims_fts")
        rows = cursor.fetchall()
        assert rows
        first = rows[0]
        claim_text = first[0] if isinstance(first, tuple) else first.get("claim_text")
        assert claim_text == "Confidence in backend migrations"
    finally:
        db.close_connection()


def test_rebuild_claims_fts_postgres_uses_backend() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db.backend = MagicMock()
    executed: List[Tuple[str, Any]] = []

    class _Conn:
        pass

    conn = _Conn()

    def fake_transaction():
        @contextmanager
        def _ctx():
            yield conn
        return _ctx()

    db.transaction = fake_transaction  # type: ignore[assignment]

    def record(conn_arg: Any, query: str, params: Any = None):
        assert conn_arg is conn
        executed.append((query, params))
        return MagicMock()

    db._execute_with_connection = MagicMock(side_effect=record)  # type: ignore[attr-defined]
    db._fetchone_with_connection = MagicMock(return_value({"total": 4}))  # type: ignore[attr-defined]

    result = db.rebuild_claims_fts()

    assert result == 4
    db.backend.create_fts_table.assert_called_once_with(
        table_name="claims_fts",
        source_table="claims",
        columns=["claim_text"],
        connection=conn,
    )
    assert executed[0][0].startswith("UPDATE claims ")
    assert executed[1][0] == "SELECT COUNT(*) AS total FROM claims WHERE deleted = 0"
