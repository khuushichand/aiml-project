from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.usage_repo import AuthnzUsageRepo


class _Tx:
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


class _SqliteCursor:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _SqliteConnWithFetchTrap:
    def __init__(self, *, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetch(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetch")

    async def execute(self, query: str, params: Any) -> _SqliteCursor:
        self.execute_calls.append((str(query), params))
        return _SqliteCursor(self.rowcount)


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *params: Any) -> list[dict[str, int]]:
        self.fetch_calls.append((str(query), tuple(params)))
        return [{"_": 1}, {"_": 1}]

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if " day < ?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        return "DELETE 4"


@pytest.mark.asyncio
async def test_prune_usage_log_before_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithFetchTrap(rowcount=3)
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=False))
    cutoff = datetime.now(timezone.utc)

    deleted = await repo.prune_usage_log_before(cutoff)

    assert deleted == 3
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from usage_log where ts < ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_prune_usage_log_before_postgres_backend_selection_uses_fetch():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=True))
    cutoff = datetime.now(timezone.utc)

    deleted = await repo.prune_usage_log_before(cutoff)

    assert deleted == 2
    assert conn.fetch_calls
    assert "delete from usage_log where ts < $1 returning 1" in conn.fetch_calls[0][0].lower()


@pytest.mark.asyncio
async def test_prune_llm_usage_log_before_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithFetchTrap(rowcount=5)
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=False))
    cutoff = datetime.now(timezone.utc)

    deleted = await repo.prune_llm_usage_log_before(cutoff)

    assert deleted == 5
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from llm_usage_log where ts < ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_prune_llm_usage_log_before_postgres_backend_selection_uses_fetch():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=True))
    cutoff = datetime.now(timezone.utc)

    deleted = await repo.prune_llm_usage_log_before(cutoff)

    assert deleted == 2
    assert conn.fetch_calls
    assert "delete from llm_usage_log where ts < $1 returning 1" in conn.fetch_calls[0][0].lower()


@pytest.mark.asyncio
async def test_prune_usage_daily_before_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithFetchTrap(rowcount=7)
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=False))

    deleted = await repo.prune_usage_daily_before(date(2026, 2, 8))

    assert deleted == 7
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from usage_daily where day < ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_prune_usage_daily_before_postgres_backend_selection_uses_fetch():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=True))

    deleted = await repo.prune_usage_daily_before(date(2026, 2, 8))

    assert deleted == 2
    assert conn.fetch_calls
    assert "delete from usage_daily where day < $1::date returning 1" in conn.fetch_calls[0][0].lower()


@pytest.mark.asyncio
async def test_prune_llm_usage_daily_before_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithFetchTrap(rowcount=6)
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=False))

    deleted = await repo.prune_llm_usage_daily_before(date(2026, 2, 8))

    assert deleted == 6
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from llm_usage_daily where day < ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_prune_llm_usage_daily_before_postgres_backend_selection_uses_execute():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzUsageRepo(db_pool=_PoolStub(conn, postgres=True))

    deleted = await repo.prune_llm_usage_daily_before(date(2026, 2, 8))

    assert deleted == 4
    assert conn.execute_calls
    assert "delete from llm_usage_daily where day < $1::date" in conn.execute_calls[0][0].lower()
