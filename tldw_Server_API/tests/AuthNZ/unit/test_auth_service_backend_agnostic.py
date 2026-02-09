from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from tldw_Server_API.app.services import auth_service


class _Cursor:
    def __init__(self, row: Any) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_user_by_login_identifier_prefers_fetchrow() -> None:
    db = AsyncMock()
    db.fetchrow = AsyncMock(return_value={"id": 7, "username": "alice"})

    result = await auth_service.fetch_user_by_login_identifier(db, "Alice@Example.com")

    assert result == {"id": 7, "username": "alice"}
    db.fetchrow.assert_awaited_once_with(
        "SELECT * FROM users WHERE lower(username) = $1 OR lower(email) = $2",
        "alice@example.com",
        "alice@example.com",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_user_by_login_identifier_sqlite_fallback_uses_qmark() -> None:
    class _SqliteLikeConn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...]]] = []

        async def execute(self, query: str, params: tuple[Any, ...]) -> _Cursor:
            self.calls.append((query, params))
            return _Cursor({"id": 3, "username": "bob"})

    db = _SqliteLikeConn()

    result = await auth_service.fetch_user_by_login_identifier(db, "BOB")

    assert result == {"id": 3, "username": "bob"}
    assert db.calls == [
        (
            "SELECT * FROM users WHERE lower(username) = ? OR lower(email) = ?",
            ("bob", "bob"),
        )
    ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_password_hash_commits_sqlite_like_connection() -> None:
    class _SqliteLikeConn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...]]] = []
            self.commits = 0

        async def execute(self, query: str, params: tuple[Any, ...]) -> None:
            self.calls.append((query, params))

        async def commit(self) -> None:
            self.commits += 1

    db = _SqliteLikeConn()

    await auth_service.update_user_password_hash(db, 42, "new-hash")

    assert db.calls == [("UPDATE users SET password_hash = $1 WHERE id = $2", ("new-hash", 42))]
    assert db.commits == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_active_user_by_id_normalizes_sqlite_tuple_boolean() -> None:
    class _SqliteLikeConn:
        async def execute(self, query: str, params: tuple[Any, ...]) -> _Cursor:
            assert query == "SELECT * FROM users WHERE id = ? AND is_active = ?"
            assert params == (9, True)
            return _Cursor(
                (
                    9,
                    "f7d8d7ac-2c08-4f50-92dd-111111111111",
                    "carol",
                    "carol@example.com",
                    "hash",
                    "user",
                    1,
                    0,
                    "2026-01-01T00:00:00",
                    "2026-01-01T00:00:00",
                    "2026-01-01T00:00:00",
                    1024,
                    12.5,
                )
            )

    result = await auth_service.fetch_active_user_by_id(_SqliteLikeConn(), 9)

    assert result is not None
    assert result["id"] == 9
    assert result["is_active"] is True
    assert result["username"] == "carol"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_user_last_login_uses_adapter_query_shape() -> None:
    now = datetime(2026, 2, 9, 12, 0, 0)
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()

    await auth_service.update_user_last_login(db, 17, now)

    db.execute.assert_awaited_once_with(
        "UPDATE users SET last_login = $1 WHERE id = $2",
        now,
        17,
    )
