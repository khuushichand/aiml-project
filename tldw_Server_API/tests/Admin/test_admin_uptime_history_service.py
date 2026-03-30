from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.services.admin_uptime_history_service import AdminUptimeHistoryService


pytestmark = pytest.mark.unit


class _FetchAllStubPool:
    def __init__(self, *, is_sqlite: bool, rows: list[dict[str, Any]] | None = None) -> None:
        self._is_sqlite = is_sqlite
        self.fetchall_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self._rows = list(rows or [])

    async def fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self.fetchall_calls.append((str(query), tuple(params)))
        return list(self._rows)

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        self.execute_calls.append((str(query), tuple(params)))
        return type("Result", (), {"rowcount": 0})()


@pytest.mark.asyncio
async def test_get_uptime_history_sqlite_uses_bucket_hours_expression() -> None:
    pool = _FetchAllStubPool(
        is_sqlite=True,
        rows=[{"bucket": "2026-03-01T00:00:00Z", "probes": 2, "healthy_count": 1}],
    )
    svc = AdminUptimeHistoryService(db_pool=pool)

    result = await svc.get_uptime_history("db", range_days=7, bucket_hours=6)

    assert result == [{"bucket": "2026-03-01T00:00:00Z", "uptime_pct": 50.0, "probes": 2}]
    query, params = pool.fetchall_calls[0]
    assert "strftime('%s', checked_at)" in query
    assert params == ("db", 21600, "-7 days")


@pytest.mark.asyncio
async def test_get_uptime_history_postgres_uses_date_bin_and_pg_placeholders() -> None:
    pool = _FetchAllStubPool(
        is_sqlite=False,
        rows=[{"bucket": "2026-03-01T00:00:00+00:00", "probes": 4, "healthy_count": 3}],
    )
    svc = AdminUptimeHistoryService(db_pool=pool)

    result = await svc.get_uptime_history("cache", range_days=14, bucket_hours=12)

    assert result == [{"bucket": "2026-03-01T00:00:00+00:00", "uptime_pct": 75.0, "probes": 4}]
    query, params = pool.fetchall_calls[0]
    assert "DATE_BIN" in query
    assert "$1" in query
    assert params == ("cache", "12 hours", 14)
