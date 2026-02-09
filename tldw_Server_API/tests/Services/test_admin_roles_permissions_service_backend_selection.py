from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.services import admin_roles_permissions_service as svc


class _CursorStub:
    def __init__(self, *, rows: list[Any] | None = None, lastrowid: int | None = None) -> None:
        self._rows = list(rows or [])
        self.lastrowid = lastrowid

    async def fetchall(self) -> list[Any]:
        return list(self._rows)

    async def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None


class _SqliteDbWithPgTraps:
    def __init__(self) -> None:
        self._is_sqlite = True
        self.execute_calls: list[tuple[str, Any]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.commit_calls = 0

    async def fetch(self, query: str, *args: Any) -> list[Any]:  # pragma: no cover - trap
        self.fetch_calls.append((str(query), tuple(args)))
        raise AssertionError("SQLite backend selection should not use fetch()")

    async def fetchrow(self, query: str, *args: Any) -> Any:  # pragma: no cover - trap
        self.fetchrow_calls.append((str(query), tuple(args)))
        raise AssertionError("SQLite backend selection should not use fetchrow()")

    async def execute(self, query: str, params: Any = ()) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        q = str(query).lower()
        if "select id, name, description, coalesce(is_system, 0)" in q:
            return _CursorStub(rows=[(1, "role-sqlite", "desc", 0)])
        if "select 1 from roles where lower(name) = lower(?)" in q:
            return _CursorStub(rows=[])
        if "insert into roles" in q:
            return _CursorStub(rows=[], lastrowid=2)
        if "select id, name, description, coalesce(is_system,0) from roles where id =" in q:
            return _CursorStub(rows=[(2, "new-role", "desc", 1)])
        return _CursorStub(rows=[])

    async def commit(self) -> None:
        self.commit_calls += 1


class _PostgresDbWithSqliteTraps:
    def __init__(self) -> None:
        self._is_sqlite = False
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((str(query), tuple(args)))
        if "?" in query:
            raise AssertionError("Postgres path should not use sqlite placeholders")
        return "OK"

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((str(query), tuple(args)))
        if "?" in query:
            raise AssertionError("Postgres path should not use sqlite placeholders")
        return [{"id": 5, "name": "role-pg", "description": "desc", "is_system": False}]

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((str(query), tuple(args)))
        if "?" in query:
            raise AssertionError("Postgres path should not use sqlite placeholders")
        if "select 1 from roles" in query.lower():
            return None
        if "returning id, name, description, is_system" in query.lower():
            return {"id": 6, "name": "new-role", "description": "desc", "is_system": True}
        return {"id": 6, "name": "new-role", "description": "desc", "is_system": True}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_roles_sqlite_backend_selection_uses_execute() -> None:
    db = _SqliteDbWithPgTraps()

    rows = await svc.list_roles(db)

    assert rows and rows[0]["name"] == "role-sqlite"
    assert db.execute_calls
    assert not db.fetch_calls
    assert not db.fetchrow_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_roles_postgres_backend_selection_uses_fetch() -> None:
    db = _PostgresDbWithSqliteTraps()

    rows = await svc.list_roles(db)

    assert rows and rows[0]["name"] == "role-pg"
    assert db.fetch_calls
    assert not db.execute_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_role_sqlite_backend_selection_uses_sqlite_queries() -> None:
    db = _SqliteDbWithPgTraps()

    row = await svc.create_role(db, "new-role", "desc", True)

    assert row["name"] == "new-role"
    assert any("lower(name) = lower(?)" in q.lower() for q, _ in db.execute_calls)
    assert any("insert into roles" in q.lower() and "?" in q for q, _ in db.execute_calls)
    assert db.commit_calls >= 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_role_postgres_backend_selection_uses_postgres_queries() -> None:
    db = _PostgresDbWithSqliteTraps()

    row = await svc.create_role(db, "new-role", "desc", True)

    assert row["name"] == "new-role"
    assert db.fetchrow_calls
    assert any("$1" in q for q, _ in db.fetchrow_calls)
