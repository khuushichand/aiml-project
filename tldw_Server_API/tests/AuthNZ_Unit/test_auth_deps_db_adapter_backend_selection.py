from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.api.v1.API_Deps import auth_deps


class _AcquireCM:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    async def __aenter__(self) -> Any:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _PoolStub:
    def __init__(self, conn: Any, *, pool_marker: Any) -> None:
        self._conn = conn
        self.pool = pool_marker

    def acquire(self) -> _AcquireCM:
        return _AcquireCM(self._conn)


class _PostgresConnWithoutFetchrowProbe:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.commit_calls = 0

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - failure guard only
        if name == "fetchrow":
            raise AssertionError("adapter should not inspect connection capability via fetchrow")
        raise AttributeError(name)

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((str(query), tuple(args)))
        return "OK"

    async def commit(self) -> None:
        self.commit_calls += 1


class _SqliteConnWithFetchrowCapability:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, Any]] = []
        self.commit_calls = 0

    async def fetchrow(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - sqlite path should ignore
        raise AssertionError("sqlite adapter path should not call fetchrow")

    async def execute(self, query: str, params: Any) -> Any:
        self.execute_calls.append((str(query), params))
        return SimpleNamespace()

    async def commit(self) -> None:
        self.commit_calls += 1


@pytest.mark.asyncio
async def test_get_db_transaction_adapter_uses_pool_backend_for_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_get_db_pool() -> _PoolStub:
        return _PoolStub(_PostgresConnWithoutFetchrowProbe(), pool_marker=object())

    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setattr(auth_deps, "get_db_pool", _fake_get_db_pool)

    agen = auth_deps.get_db_transaction()
    adapter = await agen.__anext__()
    try:
        await adapter.execute("SELECT $1", 1)
        conn = adapter._conn  # noqa: SLF001 - test verifies adapter behavior
        assert conn.execute_calls == [("SELECT $1", (1,))]
        assert conn.commit_calls == 0
    finally:
        await agen.aclose()


@pytest.mark.asyncio
async def test_get_db_transaction_adapter_uses_pool_backend_for_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_get_db_pool() -> _PoolStub:
        return _PoolStub(_SqliteConnWithFetchrowCapability(), pool_marker=None)

    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setattr(auth_deps, "get_db_pool", _fake_get_db_pool)

    agen = auth_deps.get_db_transaction()
    adapter = await agen.__anext__()
    try:
        await adapter.execute("SELECT $1", 1)
        conn = adapter._conn  # noqa: SLF001 - test verifies adapter behavior
        assert conn.execute_calls and conn.execute_calls[0][0] == "SELECT ?"
        assert conn.commit_calls == 1
    finally:
        await agen.aclose()
