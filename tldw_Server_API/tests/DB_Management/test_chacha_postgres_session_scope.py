from __future__ import annotations

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


class _StubCursor:
    def __init__(self, conn: "_StubConn") -> None:
        self._conn = conn

    def execute(self, *_args, **_kwargs) -> None:
        if self._conn.fail_execute:
            raise RuntimeError("execute failed")


class _StubConn:
    def __init__(self, *, fail_execute: bool = False, fail_commit: bool = False, fail_rollback: bool = False) -> None:
        self.fail_execute = fail_execute
        self.fail_commit = fail_commit
        self.fail_rollback = fail_rollback
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self) -> _StubCursor:
        return _StubCursor(self)

    def commit(self) -> None:
        self.commits += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        self.rollbacks += 1
        if self.fail_rollback:
            raise RuntimeError("rollback failed")

    def close(self) -> None:
        self.closed = True


class _StubPool:
    def __init__(self, connections: list[_StubConn]) -> None:
        self._connections = list(connections)
        self.get_calls = 0
        self.returned: list[_StubConn] = []

    def get_connection(self) -> _StubConn:
        self.get_calls += 1
        return self._connections.pop(0)

    def return_connection(self, conn: _StubConn) -> None:
        self.returned.append(conn)


class _StubBackend:
    backend_type = BackendType.POSTGRESQL

    def __init__(self, pool: _StubPool) -> None:
        self._pool = pool

    def get_pool(self) -> _StubPool:
        return self._pool


def test_open_new_connection_rolls_back_on_commit_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(CharactersRAGDB, "_initialize_schema", lambda self: None)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB.psycopg_sql",
        None,
    )

    conn = _StubConn(fail_commit=True)
    pool = _StubPool([conn])
    backend = _StubBackend(pool)

    db = CharactersRAGDB(tmp_path / "ChaChaNotes.db", client_id="123", backend=backend)
    opened = db._open_new_connection()

    assert opened is conn
    assert conn.rollbacks == 1
    assert pool.get_calls == 1


def test_open_new_connection_replaces_connection_when_rollback_fails(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(CharactersRAGDB, "_initialize_schema", lambda self: None)
    monkeypatch.setattr(
        "tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB.psycopg_sql",
        None,
    )

    bad_conn = _StubConn(fail_commit=True, fail_rollback=True)
    good_conn = _StubConn()
    pool = _StubPool([bad_conn, good_conn])
    backend = _StubBackend(pool)

    db = CharactersRAGDB(tmp_path / "ChaChaNotes.db", client_id="123", backend=backend)
    opened = db._open_new_connection()

    assert opened is good_conn
    assert bad_conn in pool.returned
    assert pool.get_calls >= 2
