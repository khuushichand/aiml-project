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

    assert db.calls == [("UPDATE users SET password_hash = ? WHERE id = ?", ("new-hash", 42))]
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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_password_reset_token_sqlite_fallback_normalizes_placeholders() -> None:
    class _SqliteLikeConn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...]]] = []
            self.commits = 0

        async def execute(self, query: str, params: tuple[Any, ...]) -> None:
            self.calls.append((query, params))

        async def commit(self) -> None:
            self.commits += 1

    db = _SqliteLikeConn()
    expires = datetime(2026, 2, 9, 12, 30, 0)

    await auth_service.store_password_reset_token(
        db,
        user_id=7,
        token_hash="tok-hash",
        expires_at=expires,
        ip_address="203.0.113.9",
    )

    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "INSERT INTO password_reset_tokens" in query
    assert "VALUES (?, ?, ?, ?)" in query
    assert params == (7, "tok-hash", expires, "203.0.113.9")
    assert db.commits == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_password_reset_token_record_sqlite_fallback_dynamic_in_clause() -> None:
    class _SqliteLikeConn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, tuple[Any, ...]]] = []

        async def execute(self, query: str, params: tuple[Any, ...]) -> _Cursor:
            self.calls.append((query, params))
            return _Cursor((55, None))

    db = _SqliteLikeConn()
    token_id, used_at = await auth_service.fetch_password_reset_token_record(
        db,
        user_id=4,
        hash_candidates=["h1", "h2"],
    )

    assert token_id == 55
    assert used_at is None
    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert "FROM password_reset_tokens" in query
    assert "token_hash IN (?, ?)" in query
    assert params == (4, "h1", "h2")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_verify_user_email_once_uses_postgres_update_count_when_available() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value="UPDATE 1")
    db.fetchrow = AsyncMock()
    db.commit = AsyncMock()

    updated = await auth_service.verify_user_email_once(
        db,
        user_id=9,
        email="User@Example.com",
        now_utc=datetime(2026, 2, 9, 13, 0, 0),
    )

    assert updated == 1
    db.fetchrow.assert_not_awaited()
