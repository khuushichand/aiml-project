from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.token_blacklist_repo import (
    AuthnzTokenBlacklistRepo,
)


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


class _SqliteCursor:
    def __init__(self, *, row: Any = None, rowcount: int = 0) -> None:
        self._row = row
        self.rowcount = rowcount

    async def fetchone(self) -> Any:
        return self._row


class _SqliteConnWithPostgresTrap:
    def __init__(self, *, rowcount: int = 2) -> None:
        self.rowcount = rowcount
        self.execute_calls: list[tuple[str, Any]] = []
        self.commit_calls = 0

    async def fetch(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetch")

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _SqliteCursor:
        self.execute_calls.append((str(query), params))
        lower_q = str(query).lower()
        if "select expires_at" in lower_q:
            return _SqliteCursor(row=("2026-02-08T00:00:00",), rowcount=1)
        return _SqliteCursor(rowcount=self.rowcount)

    async def commit(self) -> None:
        self.commit_calls += 1


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        return "INSERT 0 1"

    async def fetch(self, query: str, *params: Any) -> list[dict[str, Any]]:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.fetch_calls.append((str(query), tuple(params)))
        return [{"id": 1}, {"id": 2}]

    async def fetchrow(self, query: str, *params: Any) -> dict[str, Any]:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.fetchrow_calls.append((str(query), tuple(params)))
        if "select expires_at" in lower_q:
            return {"expires_at": datetime(2026, 2, 8, 0, 0, 0)}
        return {
            "total": 2,
            "access_tokens": 1,
            "refresh_tokens": 1,
            "earliest_revocation": None,
            "latest_revocation": None,
        }


@pytest.mark.asyncio
async def test_insert_blacklisted_token_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPostgresTrap(rowcount=1)
    repo = AuthnzTokenBlacklistRepo(db_pool=_PoolStub(conn, postgres=False))

    await repo.insert_blacklisted_token(
        jti="jti-sqlite",
        user_id=1,
        token_type="access",
        expires_at=datetime.now(timezone.utc),
        reason="test",
        revoked_by=9,
        ip_address="127.0.0.1",
    )

    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "insert or ignore into token_blacklist" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_insert_blacklisted_token_postgres_backend_selection_uses_dollar_params():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzTokenBlacklistRepo(db_pool=_PoolStub(conn, postgres=True))

    await repo.insert_blacklisted_token(
        jti="jti-pg",
        user_id=1,
        token_type="refresh",
        expires_at=datetime.now(timezone.utc),
        reason="test",
        revoked_by=9,
        ip_address="127.0.0.1",
    )

    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "values ($1, $2, $3, $4, $5, $6, $7)" in query.lower()
    assert "on conflict (jti) do nothing" in query.lower()
    assert len(params) == 7


@pytest.mark.asyncio
async def test_cleanup_expired_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPostgresTrap(rowcount=4)
    repo = AuthnzTokenBlacklistRepo(db_pool=_PoolStub(conn, postgres=False))

    deleted = await repo.cleanup_expired(datetime.now(timezone.utc))

    assert deleted == 4
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from token_blacklist where expires_at < ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_get_active_expiry_for_jti_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzTokenBlacklistRepo(db_pool=_PoolStub(conn, postgres=True))

    expiry = await repo.get_active_expiry_for_jti("jti-pg", now=datetime.now(timezone.utc))

    assert isinstance(expiry, datetime)
    assert conn.fetchrow_calls
    query, params = conn.fetchrow_calls[0]
    assert "where jti = $1 and expires_at > $2" in query.lower()
    assert params and params[0] == "jti-pg"


@pytest.mark.asyncio
async def test_get_blacklist_stats_user_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzTokenBlacklistRepo(db_pool=_PoolStub(conn, postgres=True))

    stats = await repo.get_blacklist_stats(now=datetime.now(timezone.utc), user_id=7)

    assert stats["total"] == 2
    assert stats["access_tokens"] == 1
    assert conn.fetchrow_calls
    query, params = conn.fetchrow_calls[0]
    assert "where user_id = $1 and expires_at > $2" in query.lower()
    assert params and params[0] == 7
