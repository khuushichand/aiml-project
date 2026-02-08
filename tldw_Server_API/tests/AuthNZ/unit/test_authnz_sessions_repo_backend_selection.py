from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.sessions_repo import AuthnzSessionsRepo


class _Tx:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ARG002
        return False


class _Acquire:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ARG002
        return False


class _PoolStub:
    def __init__(self, conn: Any, *, postgres: bool) -> None:
        self._conn = conn
        self.pool = object() if postgres else None

    def transaction(self) -> _Tx:
        return _Tx(self._conn)

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


class _Cursor:
    def __init__(self, row: Any = None) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SqliteConnWithFetchrowTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _Cursor:
        q = str(query).lower()
        self.execute_calls.append((str(query), params))
        if "from sessions" in q and "where id = ?" in q:
            return _Cursor((1, 2, "access-jti", "refresh-jti", "2026-01-01T00:00:00", "2026-01-08T00:00:00"))
        return _Cursor(None)


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *params: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((str(query), tuple(params)))
        if "from sessions s" in str(query).lower():
            return {
                "id": 10,
                "token_hash": "hash-access",
                "user_id": 3,
                "expires_at": "2026-01-01T00:00:00",
                "is_active": True,
                "revoked_at": None,
                "username": "tester",
                "role": "user",
                "user_active": True,
            }
        return {
            "id": 1,
            "user_id": 2,
            "access_jti": "access-jti",
            "refresh_jti": "refresh-jti",
            "expires_at": "2026-01-01T00:00:00",
            "refresh_expires_at": "2026-01-08T00:00:00",
        }

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "where id = ?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        return "UPDATE 1"


@pytest.mark.asyncio
async def test_revoke_session_record_sqlite_backend_selection_uses_execute_even_with_fetchrow():
    conn = _SqliteConnWithFetchrowTrap()
    repo = AuthnzSessionsRepo(db_pool=_PoolStub(conn, postgres=False))

    details = await repo.revoke_session_record(session_id=1, revoked_by=7, reason="unit-test")

    assert details is not None
    assert details["id"] == 1
    assert details["user_id"] == 2
    assert conn.execute_calls
    assert any("where id = ?" in q.lower() for q, _ in conn.execute_calls)


@pytest.mark.asyncio
async def test_revoke_session_record_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzSessionsRepo(db_pool=_PoolStub(conn, postgres=True))

    details = await repo.revoke_session_record(session_id=5, revoked_by=9, reason="admin")

    assert details is not None
    assert details["id"] == 1
    assert conn.fetchrow_calls
    assert "where id = $1" in conn.fetchrow_calls[0][0].lower()
    assert conn.execute_calls
    assert "update sessions" in conn.execute_calls[0][0].lower()


@pytest.mark.asyncio
async def test_fetch_session_for_validation_by_id_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzSessionsRepo(db_pool=_PoolStub(conn, postgres=True))

    row = await repo.fetch_session_for_validation_by_id(session_id=10)

    assert row is not None
    assert row["id"] == 10
    assert conn.fetchrow_calls
    assert "from sessions s" in conn.fetchrow_calls[0][0].lower()
    assert "where s.id = $1" in conn.fetchrow_calls[0][0].lower()
