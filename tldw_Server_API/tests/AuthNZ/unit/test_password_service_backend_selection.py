from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.AuthNZ.password_service import PasswordService
from tldw_Server_API.app.core.AuthNZ.settings import get_settings, reset_settings


class _CursorStub:
    def __init__(self, *, rows: list[Any] | None = None) -> None:
        self._rows = list(rows or [])

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class _SQLiteConnWithPgTraps:
    def __init__(self) -> None:
        self.fetch_called = False
        self.execute_calls: list[tuple[str, Any]] = []
        self._is_sqlite = True

    async def fetch(self, *args: Any, **kwargs: Any) -> list[Any]:  # pragma: no cover - should never run
        self.fetch_called = True
        raise AssertionError("sqlite backend path should not use fetch()")

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        q = str(query).lower()
        if "select password_hash from password_history" in q:
            return _CursorStub(rows=[{"password_hash": "old-hash"}])
        return _CursorStub()


class _PostgresConnWithSqliteTraps:
    def __init__(self) -> None:
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self._is_sqlite = False

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.fetch_calls.append((str(query), tuple(args)))
        if "?" in str(query):
            raise AssertionError("postgres path should not use sqlite placeholders")
        return [{"password_hash": "old-hash"}]

    async def execute(self, query: str, *args: Any) -> str:
        self.execute_calls.append((str(query), tuple(args)))
        if "?" in str(query):
            raise AssertionError("postgres path should not use sqlite placeholders")
        return "OK"


@pytest.mark.asyncio
async def test_check_password_history_sqlite_path_uses_execute(
) -> None:
    reset_settings()
    service = PasswordService(settings=get_settings())
    service.verify_password = lambda *_: (False, False)  # type: ignore[method-assign]
    conn = _SQLiteConnWithPgTraps()

    ok = await service.check_password_history(
        user_id=1,
        new_password="N3w$trongPass",
        db_connection=conn,
        is_postgres=False,
    )

    assert ok is True
    assert conn.fetch_called is False
    assert conn.execute_calls
    assert "?" in conn.execute_calls[0][0]


@pytest.mark.asyncio
async def test_check_password_history_infers_sqlite_from_connection_hint() -> None:
    reset_settings()
    service = PasswordService(settings=get_settings())
    service.verify_password = lambda *_: (False, False)  # type: ignore[method-assign]
    conn = _SQLiteConnWithPgTraps()

    ok = await service.check_password_history(
        user_id=1,
        new_password="N3w$trongPass",
        db_connection=conn,
    )

    assert ok is True
    assert conn.fetch_called is False
    assert conn.execute_calls
    assert "?" in conn.execute_calls[0][0]


@pytest.mark.asyncio
async def test_check_password_history_postgres_path_uses_fetch(
) -> None:
    reset_settings()
    service = PasswordService(settings=get_settings())
    service.verify_password = lambda *_: (False, False)  # type: ignore[method-assign]
    conn = _PostgresConnWithSqliteTraps()

    ok = await service.check_password_history(
        user_id=1,
        new_password="N3w$trongPass",
        db_connection=conn,
        is_postgres=True,
    )

    assert ok is True
    assert conn.fetch_calls
    assert not conn.execute_calls
    assert "$1" in conn.fetch_calls[0][0]


@pytest.mark.asyncio
async def test_add_to_password_history_sqlite_path_uses_qmark_queries(
) -> None:
    reset_settings()
    service = PasswordService(settings=get_settings())
    conn = _SQLiteConnWithPgTraps()

    await service.add_to_password_history(
        user_id=1,
        password_hash="hash-1",
        db_connection=conn,
        is_postgres=False,
    )

    assert len(conn.execute_calls) == 2
    assert all("?" in query for query, _ in conn.execute_calls)


@pytest.mark.asyncio
async def test_add_to_password_history_postgres_path_uses_dollar_queries(
) -> None:
    reset_settings()
    service = PasswordService(settings=get_settings())
    conn = _PostgresConnWithSqliteTraps()

    await service.add_to_password_history(
        user_id=1,
        password_hash="hash-1",
        db_connection=conn,
        is_postgres=True,
    )

    assert len(conn.execute_calls) == 2
    assert all("$1" in query for query, _ in conn.execute_calls)
