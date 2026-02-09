from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.services import admin_tool_catalog_service as svc


class _CursorStub:
    def __init__(self, *, rows: list[Any] | None = None) -> None:
        self._rows = list(rows or [])

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class _SqliteDbWithPgTraps:
    def __init__(self) -> None:
        self._is_sqlite = True
        self.execute_calls: list[tuple[str, Any]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[Any]:  # pragma: no cover - trap
        self.fetch_calls.append((str(query), tuple(args)))
        raise AssertionError("SQLite backend selection should not use fetch()")

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        return _CursorStub(
            rows=[
                (1, "sqlite-cat", "desc", None, None, 1, "2026-01-01", "2026-01-01"),
            ]
        )


class _PostgresDbWithSqliteTraps:
    def __init__(self) -> None:
        self._is_sqlite = False
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> str:  # pragma: no cover - trap
        raise AssertionError("Postgres backend selection should not use sqlite execute() in this path")

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((str(query), tuple(args)))
        if "?" in query:
            raise AssertionError("Postgres path should not use sqlite placeholders")
        return [
            {
                "id": 2,
                "name": "pg-cat",
                "description": "desc",
                "org_id": None,
                "team_id": None,
                "is_active": True,
                "created_at": "2026-01-01",
                "updated_at": "2026-01-01",
            }
        ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_tool_catalogs_sqlite_backend_selection_uses_execute() -> None:
    db = _SqliteDbWithPgTraps()

    rows = await svc.list_tool_catalogs(db, org_id=None, team_id=None, limit=10, offset=0)

    assert db.execute_calls
    assert not db.fetch_calls
    assert rows and rows[0]["name"] == "sqlite-cat"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_tool_catalogs_postgres_backend_selection_uses_fetch() -> None:
    db = _PostgresDbWithSqliteTraps()

    rows = await svc.list_tool_catalogs(db, org_id=None, team_id=None, limit=10, offset=0)

    assert db.fetch_calls
    query, params = db.fetch_calls[0]
    assert "$1" in query and "$2" in query
    assert params[-2:] == (10, 0)
    assert rows and rows[0]["name"] == "pg-cat"
