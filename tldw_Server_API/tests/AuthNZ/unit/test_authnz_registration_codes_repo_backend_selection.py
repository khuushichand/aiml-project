from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.registration_codes_repo import (
    AuthnzRegistrationCodesRepo,
)


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


class _SqliteConnWithFetchrowTrap:
    def __init__(self, rowcount: int = 2) -> None:
        self.rowcount = rowcount
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _SqliteCursor:
        self.execute_calls.append((str(query), params))
        return _SqliteCursor(self.rowcount)


class _PostgresConnWithSqliteTrap:
    def __init__(self, result: str = "UPDATE 4") -> None:
        self.result = result
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "expires_at < ?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        return self.result


@pytest.mark.asyncio
async def test_deactivate_expired_codes_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithFetchrowTrap(rowcount=3)
    repo = AuthnzRegistrationCodesRepo(db_pool=_PoolStub(conn, postgres=False))
    cutoff = datetime.now(timezone.utc)

    updated = await repo.deactivate_expired_codes(cutoff)

    assert updated == 3
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "expires_at < ?" in query
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_deactivate_expired_codes_postgres_backend_selection_uses_dollar_params():
    conn = _PostgresConnWithSqliteTrap(result="UPDATE 5")
    repo = AuthnzRegistrationCodesRepo(db_pool=_PoolStub(conn, postgres=True))
    cutoff = datetime.now(timezone.utc)

    updated = await repo.deactivate_expired_codes(cutoff)

    assert updated == 5
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "expires_at < $1" in query
    assert params and params[0] == cutoff
