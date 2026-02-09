from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.Claims_Extraction import claims_service


class _SqlitePoolWithPgTraps:
    def __init__(self) -> None:
        self._is_sqlite = True
        self.fetch_calls: list[tuple[str, Any]] = []
        self.fetchall_calls: list[tuple[str, Any]] = []

    async def fetch(self, query: str, params: Any) -> list[Any]:  # pragma: no cover - trap
        self.fetch_calls.append((str(query), params))
        raise AssertionError("sqlite backend selection should not use fetch()")

    async def fetchall(self, query: str, params: Any) -> list[Any]:
        self.fetchall_calls.append((str(query), params))
        q = str(query).lower()
        if "from llm_usage_log" not in q or "operation in (" not in q:
            raise AssertionError(f"Unexpected sqlite query: {query!r}")
        return [
            ("openai", "gpt-4o-mini", "claims_extract", 200, 120.0, 100, 0.02),
            ("openai", "gpt-4o-mini", "claims_extract", 500, 240.0, 150, 0.03),
        ]


class _PostgresPoolWithSqliteTraps:
    def __init__(self) -> None:
        self._is_sqlite = False
        self.fetch_calls: list[tuple[str, Any]] = []
        self.fetchall_calls: list[tuple[str, Any]] = []

    async def fetchall(self, query: str, params: Any) -> list[Any]:  # pragma: no cover - trap
        self.fetchall_calls.append((str(query), params))
        raise AssertionError("postgres backend selection should not use fetchall()")

    async def fetch(self, query: str, params: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((str(query), params))
        q = str(query).lower()
        if "from llm_usage_log" not in q or "operation = any(" not in q:
            raise AssertionError(f"Unexpected postgres query: {query!r}")
        return [
            {
                "provider": "anthropic",
                "model": "claude-3-5-haiku",
                "operation": "claims_verify",
                "requests": 3,
                "errors": 1,
                "total_tokens": 900,
                "total_cost_usd": 0.12,
                "latency_avg_ms": 180.5,
                "latency_p95_ms": 220.0,
            }
        ]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fetch_claims_provider_usage_sqlite_backend_selection_uses_fetchall(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = _SqlitePoolWithPgTraps()

    async def _fake_get_db_pool() -> _SqlitePoolWithPgTraps:
        return pool

    monkeypatch.setattr(claims_service, "get_db_pool", _fake_get_db_pool)

    rows = await claims_service._fetch_claims_provider_usage_async(owner_user_id="7")

    assert rows and rows[0]["provider"] == "openai"
    assert rows[0]["requests"] == 2
    assert rows[0]["errors"] == 1
    assert rows[0]["total_tokens"] == 250
    assert rows[0]["total_cost_usd"] == pytest.approx(0.05)
    assert pool.fetchall_calls
    assert not pool.fetch_calls


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fetch_claims_provider_usage_postgres_backend_selection_uses_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pool = _PostgresPoolWithSqliteTraps()

    async def _fake_get_db_pool() -> _PostgresPoolWithSqliteTraps:
        return pool

    monkeypatch.setattr(claims_service, "get_db_pool", _fake_get_db_pool)

    rows = await claims_service._fetch_claims_provider_usage_async(owner_user_id=None)

    assert rows and rows[0]["provider"] == "anthropic"
    assert rows[0]["requests"] == 3
    assert rows[0]["latency_p95_ms"] == pytest.approx(220.0)
    assert pool.fetch_calls
    assert not pool.fetchall_calls
