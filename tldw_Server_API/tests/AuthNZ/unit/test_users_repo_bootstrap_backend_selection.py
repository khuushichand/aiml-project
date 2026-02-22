from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.users_repo import AuthnzUsersRepo


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


class _CursorStub:
    def __init__(self, row: Any = None) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SQLiteConnWithFetchvalTrap:
    def __init__(self, *, role_row: Any = None) -> None:
        self.role_row = role_row
        self.execute_calls: list[tuple[str, Any]] = []
        self.committed = False

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        q = str(query).lower()
        if "select id from roles" in q:
            return _CursorStub(self.role_row)
        return _CursorStub()

    async def commit(self) -> None:
        self.committed = True

    async def fetchval(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchval")


class _PostgresConnWithSqliteTrap:
    def __init__(self, *, role_id: int | None = None) -> None:
        self.role_id = role_id
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchval_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> None:
        lower_q = str(query).lower()
        if "insert or ignore" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite INSERT OR IGNORE SQL")
        self.execute_calls.append((str(query), tuple(params)))

    async def fetchval(self, query: str, *params: Any) -> int | None:
        self.fetchval_calls.append((str(query), tuple(params)))
        return self.role_id


@pytest.mark.asyncio
async def test_ensure_single_user_admin_user_sqlite_backend_selection_uses_execute():
    conn = _SQLiteConnWithFetchvalTrap()
    repo = AuthnzUsersRepo(db_pool=_PoolStub(conn, postgres=False))

    await repo.ensure_single_user_admin_user(user_id=321)

    assert conn.committed is True
    assert conn.execute_calls
    first_q = conn.execute_calls[0][0].lower()
    second_q = conn.execute_calls[1][0].lower()
    assert "insert or ignore into users" in first_q
    assert "update users set role = 'admin'" in second_q


@pytest.mark.asyncio
async def test_ensure_single_user_admin_user_postgres_backend_selection_uses_pg_sql():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzUsersRepo(db_pool=_PoolStub(conn, postgres=True))

    await repo.ensure_single_user_admin_user(user_id=654)

    assert conn.execute_calls
    assert "on conflict (id) do nothing" in conn.execute_calls[0][0].lower()
    assert "where id = $1" in conn.execute_calls[1][0].lower()


@pytest.mark.asyncio
async def test_assign_role_if_missing_sqlite_backend_selection_uses_execute():
    conn = _SQLiteConnWithFetchvalTrap(role_row=(7,))
    repo = AuthnzUsersRepo(db_pool=_PoolStub(conn, postgres=False))

    await repo.assign_role_if_missing(user_id=11, role_name="admin")

    assert conn.committed is True
    all_queries = " ".join(q.lower() for q, _ in conn.execute_calls)
    assert "select id from roles where name = ?" in all_queries
    assert "insert or ignore into user_roles" in all_queries


@pytest.mark.asyncio
async def test_assign_role_if_missing_postgres_backend_selection_uses_fetchval():
    conn = _PostgresConnWithSqliteTrap(role_id=9)
    repo = AuthnzUsersRepo(db_pool=_PoolStub(conn, postgres=True))

    await repo.assign_role_if_missing(user_id=22, role_name="admin")

    assert conn.fetchval_calls, "expected Postgres fetchval path to be used"
    assert "select id from roles where name = $1" in conn.fetchval_calls[0][0].lower()
    assert conn.execute_calls
    assert "insert into user_roles" in conn.execute_calls[0][0].lower()
