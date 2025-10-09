
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


def test_postgres_migrations_include_v6() -> None:
    migrations = MediaDatabase._get_postgres_migrations(MediaDatabase.__new__(MediaDatabase))
    assert 6 in migrations


def test_postgres_migrate_to_v6_creates_identifier_table() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db.backend = MagicMock()

    conn = object()
    db._postgres_migrate_to_v6(conn)

    create_call = db.backend.execute.call_args_list[0]
    sql_text = create_call.args[0]
    assert "CREATE TABLE IF NOT EXISTS \"DocumentVersionIdentifiers\"" in sql_text
    assert "REFERENCES \"DocumentVersions\"" in sql_text

    index_calls = [call.args[0] for call in db.backend.execute.call_args_list[1:]]
    expected_indices = {
        'idx_dvi_doi',
        'idx_dvi_pmid',
        'idx_dvi_pmcid',
        'idx_dvi_arxiv',
        'idx_dvi_s2',
    }
    assert all(any(name in sql for sql in index_calls) for name in expected_indices)


def test_update_fts_media_postgres_updates_vector() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db._execute_with_connection = MagicMock()  # type: ignore[attr-defined]

    conn = object()
    db._update_fts_media(conn, 9, "Title", "Body")

    db._execute_with_connection.assert_called_once()
    sql, params = db._execute_with_connection.call_args.args[1:]
    assert "UPDATE media SET media_fts_tsv" in sql
    assert params == (9,)


def test_delete_fts_media_postgres_nulls_vector() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db._execute_with_connection = MagicMock()  # type: ignore[attr-defined]

    conn = object()
    db._delete_fts_media(conn, 11)

    db._execute_with_connection.assert_called_once()
    sql, params = db._execute_with_connection.call_args.args[1:]
    assert sql.strip().startswith("UPDATE media SET media_fts_tsv = NULL")
    assert params == (11,)


def test_update_fts_keyword_postgres_updates_vector() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db._execute_with_connection = MagicMock()  # type: ignore[attr-defined]

    conn = object()
    db._update_fts_keyword(conn, 5, "science")

    db._execute_with_connection.assert_called_once()
    sql, params = db._execute_with_connection.call_args.args[1:]
    assert "UPDATE keywords SET keyword_fts_tsv" in sql
    assert params == (5,)


def test_delete_fts_keyword_postgres_nulls_vector() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db._execute_with_connection = MagicMock()  # type: ignore[attr-defined]

    conn = object()
    db._delete_fts_keyword(conn, 7)

    db._execute_with_connection.assert_called_once()
    sql, params = db._execute_with_connection.call_args.args[1:]
    assert sql.strip().startswith("UPDATE keywords SET keyword_fts_tsv = NULL")
    assert params == (7,)


def test_search_media_db_postgres_uses_tsquery():
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    db.client_id = "pg-test"
    db.db_path_str = "pg-test-db"

    calls: List[Tuple[str, Tuple[Any, ...]]] = []

    class _CountCursor:
        def fetchone(self):
            return (1,)

    class _ResultCursor:
        def fetchall(self):
            return [{"id": 1, "title": "Deep Learning", "relevance_score": 0.5}]

    def fake_execute(sql: str, params: Tuple[Any, ...] | None = None):
        captured_params = tuple(params) if params is not None else tuple()
        calls.append((sql, captured_params))
        if "COUNT" in sql:
            return _CountCursor()
        return _ResultCursor()

    # Bind helpers expected by search_media_db
    db.execute_query = fake_execute  # type: ignore[assignment]
    db._append_case_insensitive_like = MediaDatabase._append_case_insensitive_like.__get__(db, MediaDatabase)

    results, total = db.search_media_db(
        "deep learning",
        search_fields=["title"],
        sort_by="relevance",
    )

    assert total == 1
    assert results and results[0]["title"] == "Deep Learning"

    count_sql, count_params = calls[0]
    assert "m.media_fts_tsv @@ to_tsquery('english', ?)" in count_sql
    assert count_params[0] == "deep & learning"

    result_sql, result_params = calls[1]
    assert "ts_rank(m.media_fts_tsv, to_tsquery('english', ?))" in result_sql
    assert result_params[0] == "deep & learning"
    assert result_params[1] == "deep & learning"
