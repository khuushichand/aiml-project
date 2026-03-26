from __future__ import annotations

import importlib
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.media_database_impl import (
    MediaDatabase,
)


pytestmark = pytest.mark.unit


_RUNTIME_MODULE_NAME = (
    "tldw_Server_API.app.core.DB_Management.media_db.runtime.claims_fts_ops"
)


def _load_runtime_module():
    try:
        return importlib.import_module(_RUNTIME_MODULE_NAME)
    except ModuleNotFoundError:
        return None


def _load_helper(name: str):
    module = _load_runtime_module()
    if module is None:
        return None
    return getattr(module, name, None)


def _make_db(tmp_path: Path, name: str) -> MediaDatabase:
    db = MediaDatabase(db_path=str(tmp_path / name), client_id="claims-fts-helper")
    db.initialize_db()
    return db


def _insert_claim_record(db: MediaDatabase) -> None:
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


def test_rebuild_claims_fts_rebinds_and_recovers_missing_sqlite_table(
    tmp_path: Path,
) -> None:
    db = _make_db(tmp_path, "claims-fts-helper.sqlite")
    try:
        assert db.rebuild_claims_fts.__func__ is _load_helper("rebuild_claims_fts")

        _insert_claim_record(db)
        db.execute_query("DROP TABLE claims_fts", commit=True)

        indexed = db.rebuild_claims_fts()
        assert indexed == 1

        rows = db.execute_query("SELECT claim_text FROM claims_fts").fetchall()
        assert rows
        first = rows[0]
        if isinstance(first, tuple):
            claim_text = first[0]
        else:
            mapping = first if isinstance(first, dict) else dict(first)
            claim_text = mapping.get("claim_text")
        assert claim_text == "Confidence in backend migrations"
    finally:
        db.close_connection()


def test_rebuild_claims_fts_helper_preserves_postgres_backend_path() -> None:
    helper_rebuild_claims_fts = _load_helper("rebuild_claims_fts")
    assert helper_rebuild_claims_fts is not None

    fake_db = MediaDatabase.__new__(MediaDatabase)
    fake_db.backend_type = BackendType.POSTGRESQL
    fake_db.backend = MagicMock()
    executed: list[tuple[str, Any]] = []

    class _Conn:
        pass

    conn = _Conn()

    def fake_transaction():
        @contextmanager
        def _ctx():
            yield conn

        return _ctx()

    fake_db.transaction = fake_transaction  # type: ignore[assignment]

    def record(conn_arg: Any, query: str, params: Any = None):
        assert conn_arg is conn
        executed.append((query, params))
        return MagicMock()

    fake_db._execute_with_connection = MagicMock(side_effect=record)  # type: ignore[attr-defined]
    fake_db._fetchone_with_connection = MagicMock(return_value={"total": 4})  # type: ignore[attr-defined]

    result = helper_rebuild_claims_fts(fake_db)

    assert result == 4
    fake_db.backend.create_fts_table.assert_called_once_with(
        table_name="claims_fts",
        source_table="claims",
        columns=["claim_text"],
        connection=conn,
    )
    assert executed[0][0].startswith("UPDATE claims ")
    fake_db._fetchone_with_connection.assert_called_once_with(
        conn,
        "SELECT COUNT(*) AS total FROM claims WHERE deleted = 0",
    )
