from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.orgs_teams_repo import AuthnzOrgsTeamsRepo


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


class _Cursor:
    def __init__(self, row: Any = None) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SqliteConnWithPgTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []
        self._default_team_select_calls = 0

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _Cursor:
        self.execute_calls.append((str(query), params))
        lower_q = str(query).lower()
        if "select tm.team_id, tm.user_id, tm.role, t.org_id" in lower_q:
            return _Cursor((2, 7, "member", 11))
        if "select id from teams where org_id = ? and name = ?" in lower_q:
            self._default_team_select_calls += 1
            if self._default_team_select_calls == 1:
                return _Cursor(None)
            return _Cursor((55,))
        return _Cursor(None)


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> str:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.execute_calls.append((str(query), tuple(params)))
        return "INSERT 0 1"

    async def fetchrow(self, query: str, *params: Any) -> dict[str, Any]:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.fetchrow_calls.append((str(query), tuple(params)))
        return {"team_id": 2, "user_id": 7, "role": "member", "org_id": 11}


@pytest.mark.asyncio
async def test_add_team_member_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithPgTrap()
    repo = AuthnzOrgsTeamsRepo(db_pool=_PoolStub(conn, postgres=False))

    row = await repo.add_team_member(team_id=2, user_id=7, role="member")

    assert row["team_id"] == 2
    assert row["org_id"] == 11
    assert conn.execute_calls
    assert "insert or ignore into team_members" in conn.execute_calls[0][0].lower()
    assert "where tm.team_id = ? and tm.user_id = ?" in conn.execute_calls[1][0].lower()


@pytest.mark.asyncio
async def test_add_team_member_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzOrgsTeamsRepo(db_pool=_PoolStub(conn, postgres=True))

    row = await repo.add_team_member(team_id=2, user_id=7, role="member")

    assert row["team_id"] == 2
    assert row["org_id"] == 11
    assert conn.execute_calls
    assert "on conflict (team_id, user_id) do nothing" in conn.execute_calls[0][0].lower()
    assert conn.fetchrow_calls
    assert "where tm.team_id = $1 and tm.user_id = $2" in conn.fetchrow_calls[0][0].lower()


@pytest.mark.asyncio
async def test_ensure_user_in_default_team_sqlite_backend_selection_uses_sqlite_upsert():
    conn = _SqliteConnWithPgTrap()
    repo = AuthnzOrgsTeamsRepo(db_pool=_PoolStub(conn, postgres=False))

    await repo._ensure_user_in_default_team(conn, org_id=11, user_id=7)

    assert conn.execute_calls
    insert_calls = [
        q for q, _ in conn.execute_calls if "insert or ignore into team_members" in q.lower()
    ]
    assert insert_calls
