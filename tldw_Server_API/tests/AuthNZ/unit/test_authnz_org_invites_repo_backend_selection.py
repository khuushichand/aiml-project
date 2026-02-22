from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.org_invites_repo import AuthnzOrgInvitesRepo


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
    def __init__(self, *, lastrowid: int | None = None, row: Any = None) -> None:
        self.lastrowid = lastrowid
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SqliteConnWithFetchrowTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("SQLite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _SqliteCursor:
        self.execute_calls.append((str(query), params))
        lower_q = str(query).lower()
        if "insert into org_invites" in lower_q:
            return _SqliteCursor(lastrowid=33)
        if "from org_invites where id = ?" in lower_q:
            row = (
                33,
                "INV-TESTCODE1234567890",
                5,
                None,
                "member",
                9,
                "2026-02-08T00:00:00",
                "2026-02-15T00:00:00",
                1,
                0,
                1,
                "notes",
                None,
            )
            return _SqliteCursor(row=row)
        return _SqliteCursor()


class _PostgresConnWithSqliteTrap:
    def __init__(self) -> None:
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, *args, **kwargs):  # noqa: ANN001, ANN002, ARG002
        raise AssertionError("Postgres backend create_invite should use conn.fetchrow")

    async def fetchrow(self, query: str, *params: Any) -> dict[str, Any]:
        lower_q = str(query).lower()
        if "?" in lower_q:
            raise AssertionError("Postgres backend path should not use SQLite placeholders")
        self.fetchrow_calls.append((str(query), tuple(params)))
        now = datetime.now(timezone.utc)
        return {
            "id": 41,
            "code": str(params[0]) if params else "INV-UNKNOWN",
            "org_id": 5,
            "team_id": None,
            "role_to_grant": "member",
            "created_by": 9,
            "created_at": now,
            "expires_at": now,
            "max_uses": 1,
            "uses_count": 0,
            "is_active": True,
            "description": None,
            "allowed_email_domain": None,
        }


@pytest.mark.asyncio
async def test_create_invite_sqlite_backend_selection_uses_execute():
    conn = _SqliteConnWithFetchrowTrap()
    repo = AuthnzOrgInvitesRepo(db_pool=_PoolStub(conn, postgres=False))

    created = await repo.create_invite(org_id=5, created_by=9)

    assert created["id"] == 33
    assert created["org_id"] == 5
    assert created["is_active"] is True
    assert conn.execute_calls
    assert "insert into org_invites" in conn.execute_calls[0][0].lower()
    assert "from org_invites where id = ?" in conn.execute_calls[1][0].lower()


@pytest.mark.asyncio
async def test_create_invite_postgres_backend_selection_uses_fetchrow():
    conn = _PostgresConnWithSqliteTrap()
    repo = AuthnzOrgInvitesRepo(db_pool=_PoolStub(conn, postgres=True))

    created = await repo.create_invite(org_id=5, created_by=9)

    assert created["id"] == 41
    assert created["org_id"] == 5
    assert isinstance(created["created_at"], str)
    assert conn.fetchrow_calls
    query, params = conn.fetchrow_calls[0]
    assert "values ($1, $2, $3" in query.lower()
    assert "returning id, code" in query.lower()
    assert params and isinstance(params[0], str) and params[0].startswith("INV-")
