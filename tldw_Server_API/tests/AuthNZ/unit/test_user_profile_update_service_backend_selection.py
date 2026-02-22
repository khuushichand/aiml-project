from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.UserProfiles import update_service


class _CursorStub:
    def __init__(self, row: Any) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SQLiteConnWithFetchvalTrap:
    def __init__(self, username: str) -> None:
        self.username = username
        self.fetchval_called = False
        self.execute_calls: list[tuple[str, Any]] = []

    async def fetchval(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should never run
        self.fetchval_called = True
        raise AssertionError("sqlite path should not call fetchval()")

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        return _CursorStub((self.username,))


class _PostgresConnWithExecuteTrap:
    def __init__(self, username: str) -> None:
        self.username = username
        self.fetchval_calls: list[tuple[str, Any]] = []
        self.execute_called = False

    async def fetchval(self, query: str, user_id: int) -> Any:
        self.fetchval_calls.append((query, user_id))
        return self.username

    async def execute(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should never run
        self.execute_called = True
        raise AssertionError("postgres path should not call execute() for username fetch")


@pytest.mark.asyncio
async def test_fetch_username_sqlite_path_uses_execute() -> None:
    db = _SQLiteConnWithFetchvalTrap("alice")

    value = await update_service._fetch_username(
        db,
        5,
        is_postgres_backend=False,
    )

    assert value == "alice"
    assert db.fetchval_called is False
    assert db.execute_calls
    assert "select username from users where id = ?" in db.execute_calls[0][0].lower()


@pytest.mark.asyncio
async def test_fetch_username_postgres_path_uses_fetchval() -> None:
    db = _PostgresConnWithExecuteTrap("bob")

    value = await update_service._fetch_username(
        db,
        9,
        is_postgres_backend=True,
    )

    assert value == "bob"
    assert db.execute_called is False
    assert db.fetchval_calls
    assert "select username from users where id = $1" in db.fetchval_calls[0][0].lower()


def test_is_postgres_backend_for_pool_uses_pool_state() -> None:
    class _PoolState:
        def __init__(self, pool: Any) -> None:
            self.pool = pool

    assert update_service._is_postgres_backend_for_pool(_PoolState(pool=None)) is False
    assert update_service._is_postgres_backend_for_pool(_PoolState(pool=object())) is True
