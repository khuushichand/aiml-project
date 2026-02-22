from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.monitoring_repo import AuthnzMonitoringRepo


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


class _SqliteConnWithPgTrap:
    def __init__(self, *, rowcount: int = 3) -> None:
        self.rowcount = rowcount
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _SqliteCursor:
        self.execute_calls.append((str(query), params))
        return _SqliteCursor(self.rowcount)


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        if "delete from audit_logs" in lower_q:
            return "DELETE 5"
        return "INSERT 0 1"


@pytest.mark.asyncio
async def test_insert_metric_audit_log_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPgTrap()
    repo = AuthnzMonitoringRepo(db_pool=_PoolStub(conn, postgres=False))

    await repo.insert_metric_audit_log(
        action="metric_auth_success",
        details_json="{}",
        created_at=datetime.now(timezone.utc),
    )

    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "values (?, ?, ?)" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_insert_metric_audit_log_postgres_backend_selection_uses_dollar_params():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzMonitoringRepo(db_pool=_PoolStub(conn, postgres=True))

    await repo.insert_metric_audit_log(
        action="metric_auth_success",
        details_json="{}",
        created_at=datetime.now(timezone.utc),
    )

    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "values ($1, $2, $3)" in query.lower()
    assert len(params) == 3
    assert isinstance(params[2], datetime)
    assert params[2].tzinfo is None


@pytest.mark.asyncio
async def test_delete_audit_logs_before_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPgTrap(rowcount=4)
    repo = AuthnzMonitoringRepo(db_pool=_PoolStub(conn, postgres=False))

    deleted = await repo.delete_audit_logs_before(datetime.now(timezone.utc))

    assert deleted == 4
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from audit_logs where created_at < ?" in query.lower()
    assert isinstance(params, tuple)


@pytest.mark.asyncio
async def test_delete_audit_logs_before_postgres_backend_selection_uses_dollar_params():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzMonitoringRepo(db_pool=_PoolStub(conn, postgres=True))

    deleted = await repo.delete_audit_logs_before(datetime.now(timezone.utc))

    assert deleted == 5
    assert conn.execute_calls
    query, params = conn.execute_calls[0]
    assert "delete from audit_logs where created_at < $1" in query.lower()
    assert params and isinstance(params[0], datetime)
    assert params[0].tzinfo is None
