from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock

import pytest

from tldw_Server_API.app.core.DB_Management.media_db.errors import DatabaseError
from tldw_Server_API.app.core.DB_Management.media_db.native_class import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.media_db.runtime import execution_ops as media_db_execution_ops


class _FailingCursor:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.rowcount = -1
        self.lastrowid = None
        self.description = None
        self.closed = False

    def execute(self, *args, **kwargs):
        raise self._exc

    def executemany(self, *args, **kwargs):
        raise self._exc

    def close(self) -> None:
        self.closed = True


class _FailingConnection:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.closed = False
        self.row_factory = None
        self._cursor = None

    def execute(self, *args, **kwargs):
        return None

    def cursor(self) -> _FailingCursor:
        self._cursor = _FailingCursor(self._exc)
        return self._cursor

    def commit(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


def test_postgres_get_connection_reapplies_scope() -> None:
    db = MediaDatabase.__new__(MediaDatabase)
    db.backend_type = BackendType.POSTGRESQL
    backend = MagicMock()
    pool = MagicMock()
    conn = object()
    pool.get_connection.return_value = conn
    backend.get_pool.return_value = pool
    backend.apply_scope = MagicMock()
    db.backend = backend
    db._txn_conn_var = ContextVar("test_txn_conn", default=None)
    db._persistent_conn_var = ContextVar("test_persistent_conn", default=None)

    first = MediaDatabase.get_connection(db)
    second = MediaDatabase.get_connection(db)

    assert first is conn
    assert second is conn
    pool.get_connection.assert_called_once()
    assert backend.apply_scope.call_count == 2
    backend.apply_scope.assert_called_with(conn)


def test_execute_query_closes_ephemeral_connection_on_error(tmp_path: Path, monkeypatch) -> None:
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="cleanup-test")
    failing_conn = _FailingConnection(sqlite3.OperationalError("boom"))
    monkeypatch.setattr(media_db_execution_ops.sqlite3, "connect", lambda *args, **kwargs: failing_conn)

    with pytest.raises(DatabaseError):
        db.execute_query("SELECT 1")

    assert failing_conn.closed is True


def test_execute_query_passthroughs_sync_integrity_error(tmp_path: Path, monkeypatch) -> None:
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="cleanup-test")
    failing_conn = _FailingConnection(sqlite3.IntegrityError("sync error: boom"))
    monkeypatch.setattr(media_db_execution_ops.sqlite3, "connect", lambda *args, **kwargs: failing_conn)

    with pytest.raises(sqlite3.IntegrityError, match="sync error"):
        db.execute_query("SELECT 1")

    assert failing_conn.closed is True


def test_execute_many_closes_ephemeral_connection_on_error(tmp_path: Path, monkeypatch) -> None:
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="cleanup-test")
    failing_conn = _FailingConnection(sqlite3.OperationalError("boom"))
    monkeypatch.setattr(media_db_execution_ops.sqlite3, "connect", lambda *args, **kwargs: failing_conn)

    with pytest.raises(DatabaseError):
        db.execute_many(
            "INSERT INTO Media (uuid, title, type, content_hash, last_modified, version, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [("uuid", "title", "text", "hash", "now", 1, "client")],
        )

    assert failing_conn.closed is True


def test_execute_many_returns_none_for_empty_params_list(tmp_path: Path) -> None:
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="cleanup-test")

    result = db.execute_many(
        "INSERT INTO Media (uuid, title, type, content_hash, last_modified, version, client_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [],
    )

    assert result is None


def test_execute_many_rejects_non_list_params_list(tmp_path: Path) -> None:
    db = MediaDatabase(db_path=str(tmp_path / "media.db"), client_id="cleanup-test")

    with pytest.raises(TypeError, match="params_list must be a list"):
        db.execute_many(
            "INSERT INTO Media (uuid, title, type, content_hash, last_modified, version, client_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("uuid", "title"),
        )
