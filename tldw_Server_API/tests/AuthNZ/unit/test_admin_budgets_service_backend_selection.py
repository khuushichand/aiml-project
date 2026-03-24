from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.services import admin_budgets_service


class _CursorStub:
    def __init__(self, *, row: Any = None, rows: list[Any] | None = None) -> None:
        self._row = row
        self._rows = rows if rows is not None else ([] if row is None else [row])

    async def fetchone(self) -> Any:
        return self._row

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class _SQLiteConnWithFetchvalTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchval(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should never run
        raise AssertionError("sqlite backend path should not call conn.fetchval")

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        return _CursorStub(row=(5,))


class _SQLiteConnWithFetchrowTrap:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchrow(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should never run
        raise AssertionError("sqlite backend path should not call conn.fetchrow")

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        return _CursorStub(row={"id": 9, "name": "acme"})


class _SqliteBudgetAdapter:
    _is_sqlite = True


class _PostgresBudgetAdapter:
    _is_sqlite = False


@pytest.mark.asyncio
async def test_fetchval_sqlite_backend_selection_uses_execute() -> None:
    conn = _SQLiteConnWithFetchvalTrap()

    result = await admin_budgets_service._fetchval(
        conn,
        "SELECT COUNT(*) FROM organizations WHERE id = $1",
        [1],
        pg=False,
    )

    assert result == 5
    assert conn.execute_calls, "expected sqlite execute path"


@pytest.mark.asyncio
async def test_fetchrow_sqlite_backend_selection_uses_execute() -> None:
    conn = _SQLiteConnWithFetchrowTrap()

    row = await admin_budgets_service._fetchrow(
        conn,
        "SELECT id, name FROM organizations WHERE id = $1",
        [9],
        pg=False,
    )

    assert row == {"id": 9, "name": "acme"}
    assert conn.execute_calls, "expected sqlite execute path"


@pytest.mark.asyncio
async def test_list_org_budgets_sqlite_backend_selection_uses_sqlite_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, bool] = {}

    async def _fake_fetchval(db, query: str, params: list[Any], *, pg: bool) -> int:
        captured["pg"] = pg
        return 0

    async def _fake_fetchrows(db, query: str, params: list[Any], *, pg: bool) -> list[Any]:
        captured["rows_pg"] = pg
        return []

    monkeypatch.setattr(admin_budgets_service, "_fetchval", _fake_fetchval)
    monkeypatch.setattr(admin_budgets_service, "_fetchrows", _fake_fetchrows)

    items, total = await admin_budgets_service.list_org_budgets(
        _SqliteBudgetAdapter(),
        org_ids=None,
        page=1,
        limit=10,
    )

    assert items == []
    assert total == 0
    assert captured["pg"] is False
    assert captured["rows_pg"] is False


@pytest.mark.asyncio
async def test_list_org_budgets_postgres_backend_selection_uses_postgres_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_fetchval(db, query: str, params: list[Any], *, pg: bool) -> int:
        captured["pg"] = pg
        return 0

    async def _fake_fetchrows(db, query: str, params: list[Any], *, pg: bool) -> list[Any]:
        captured["rows_pg"] = pg
        captured["query"] = query
        return []

    monkeypatch.setattr(admin_budgets_service, "_fetchval", _fake_fetchval)
    monkeypatch.setattr(admin_budgets_service, "_fetchrows", _fake_fetchrows)

    items, total = await admin_budgets_service.list_org_budgets(
        _PostgresBudgetAdapter(),
        org_ids=None,
        page=1,
        limit=10,
    )

    assert items == []
    assert total == 0
    assert captured["pg"] is True
    assert captured["rows_pg"] is True
    assert "org_subscriptions" not in captured["query"]
    assert "subscription_plans" not in captured["query"]


@pytest.mark.asyncio
async def test_upsert_org_budget_no_longer_reads_legacy_subscription_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def _fake_fetchrow(db, query: str, params: list[Any], *, pg: bool) -> Any:
        calls.append(query)
        if "FROM organizations" in query:
            return {"id": 7, "name": "Acme", "slug": "acme"}
        if "FROM org_budgets" in query:
            return None
        return None

    async def _fake_emit(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(admin_budgets_service, "_fetchrow", _fake_fetchrow)
    monkeypatch.setattr(admin_budgets_service, "_emit_budget_audit_event", _fake_emit)

    class _DbStub:
        _is_sqlite = False

        async def execute(self, query: str, *params: Any) -> None:
            calls.append(query)

    item, changes = await admin_budgets_service.upsert_org_budget(
        _DbStub(),
        org_id=7,
        budget_updates={"budget_month_usd": 10.0},
        clear_budgets=False,
    )

    assert item["org_id"] == 7
    assert item["budgets"]["budget_month_usd"] == 10.0
    assert changes
    assert all("org_subscriptions" not in call for call in calls)
    assert all("subscription_plans" not in call for call in calls)
