from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.External_Sources import connectors_service as svc


class _CursorStub:
    def __init__(self, *, row: Any = None, rows: list[Any] | None = None) -> None:
        self._row = row
        self._rows = list(rows or ([] if row is None else [row]))

    async def fetchone(self) -> Any:
        return self._row

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


@pytest.mark.unit
def test_get_connector_by_name_supports_gmail_provider() -> None:
    connector = svc.get_connector_by_name("gmail")
    assert connector.name == "gmail"


class _SqliteDbWithPgTraps:
    def __init__(self) -> None:
        self._is_sqlite = True
        self.execute_calls: list[tuple[str, Any]] = []
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[Any]:  # pragma: no cover - trap
        self.fetch_calls.append((str(query), tuple(args)))
        raise AssertionError("sqlite path should not use fetch()")

    async def fetchrow(self, query: str, *args: Any) -> Any:  # pragma: no cover - trap
        self.fetchrow_calls.append((str(query), tuple(args)))
        raise AssertionError("sqlite path should not use fetchrow()")

    async def execute(self, query: str, params: Any = ()) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        q = str(query).lower()
        if "from external_accounts where user_id = ?" in q:
            return _CursorStub(rows=[(1, "drive", "Drive", "u@example.com", "2026-01-01")])
        if "select version, modified_at, hash from external_items" in q:
            return _CursorStub(row=("v1", "2026-01-01", "h1"))
        raise AssertionError(f"Unexpected sqlite query: {query!r}")


class _PostgresDbWithSqliteTraps:
    def __init__(self) -> None:
        self._is_sqlite = False
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, Any]] = []

    async def execute(self, query: str, params: Any = ()) -> Any:  # pragma: no cover - trap
        self.execute_calls.append((str(query), params))
        raise AssertionError("postgres path should not use sqlite execute() in these tests")

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((str(query), tuple(args)))
        if "?" in query:
            raise AssertionError("postgres path should not use sqlite placeholders")
        return [
            {
                "id": 2,
                "provider": "notion",
                "display_name": "Notion",
                "email": None,
                "created_at": "2026-01-02",
            }
        ]

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls.append((str(query), tuple(args)))
        if "?" in query:
            raise AssertionError("postgres path should not use sqlite placeholders")
        return {"version": "v2", "modified_at": "2026-01-02", "hash": "h2"}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_accounts_sqlite_backend_selection_uses_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_ensure_tables(_db: Any) -> None:
        return None

    monkeypatch.setattr(svc, "_ensure_tables", _noop_ensure_tables)
    db = _SqliteDbWithPgTraps()

    rows = await svc.list_accounts(db, user_id=10)

    assert rows and rows[0]["provider"] == "drive"
    assert db.execute_calls
    assert not db.fetch_calls
    assert not db.fetchrow_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_accounts_postgres_backend_selection_uses_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_ensure_tables(_db: Any) -> None:
        return None

    monkeypatch.setattr(svc, "_ensure_tables", _noop_ensure_tables)
    db = _PostgresDbWithSqliteTraps()

    rows = await svc.list_accounts(db, user_id=20)

    assert rows and rows[0]["provider"] == "notion"
    assert db.fetch_calls
    assert not db.execute_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_should_ingest_item_sqlite_backend_selection_uses_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_ensure_tables(_db: Any) -> None:
        return None

    monkeypatch.setattr(svc, "_ensure_tables", _noop_ensure_tables)
    db = _SqliteDbWithPgTraps()

    should_ingest = await svc.should_ingest_item(
        db,
        source_id=1,
        provider="drive",
        external_id="doc-1",
        version="v1",
        modified_at="2026-01-01",
        content_hash="h1",
    )

    assert should_ingest is False
    assert any("external_items" in q.lower() for q, _ in db.execute_calls)
    assert not db.fetchrow_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_should_ingest_item_postgres_backend_selection_uses_fetchrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _noop_ensure_tables(_db: Any) -> None:
        return None

    monkeypatch.setattr(svc, "_ensure_tables", _noop_ensure_tables)
    db = _PostgresDbWithSqliteTraps()

    should_ingest = await svc.should_ingest_item(
        db,
        source_id=1,
        provider="drive",
        external_id="doc-2",
        version="v2",
        modified_at="2026-01-02",
        content_hash=None,
    )

    assert should_ingest is False
    assert db.fetchrow_calls
    assert not db.execute_calls
