from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.services.admin_service import update_api_key_metadata


class _CursorStub:
    def __init__(self, row: Any) -> None:
        self._row = row

    async def fetchone(self) -> Any:
        return self._row


class _SqliteConnStub:
    def __init__(self, *, row: Any) -> None:
        self._row = row
        self.execute_calls: list[tuple[str, Any]] = []
        self.commit_calls = 0

    async def execute(self, query: str, params: Any) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        if "select * from api_keys" in str(query).lower():
            return _CursorStub(self._row)
        return _CursorStub(None)

    async def commit(self) -> None:
        self.commit_calls += 1


class _PostgresConnStub:
    def __init__(self, *, row: Any) -> None:
        self._row = row
        self.execute_calls: list[tuple[str, tuple[Any, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *params: Any) -> str:
        self.execute_calls.append((str(query), tuple(params)))
        return "OK"

    async def fetchrow(self, query: str, *params: Any) -> Any:
        self.fetchrow_calls.append((str(query), tuple(params)))
        return self._row


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_api_key_metadata_sqlite_path_uses_qmark_queries() -> None:
    db = _SqliteConnStub(
        row={
            "id": 7,
            "scope": "read",
            "key_hash": "secret-hash",
            "allowed_ips": '["10.0.0.1"]',
        }
    )

    result = await update_api_key_metadata(
        db,
        user_id=3,
        key_id=7,
        rate_limit=25,
        allowed_ips=["10.0.0.1"],
        is_postgres=False,
    )

    assert db.execute_calls
    assert "?" in db.execute_calls[0][0]
    assert "$" not in db.execute_calls[0][0]
    assert "?" in db.execute_calls[1][0]
    assert db.commit_calls == 1
    assert result["id"] == 7
    assert "key_hash" not in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_api_key_metadata_postgres_path_uses_dollar_queries() -> None:
    db = _PostgresConnStub(
        row={
            "id": 9,
            "scope": "admin",
            "key_hash": "secret-hash",
        }
    )

    result = await update_api_key_metadata(
        db,
        user_id=4,
        key_id=9,
        rate_limit=100,
        allowed_ips=["127.0.0.1"],
        is_postgres=True,
    )

    assert db.execute_calls
    update_query, update_params = db.execute_calls[0]
    assert "$1" in update_query
    assert "$2" in update_query
    assert "$3" in update_query
    assert "$4" in update_query
    assert "?" not in update_query
    assert update_params[-2:] == (9, 4)

    assert db.fetchrow_calls
    select_query, select_params = db.fetchrow_calls[0]
    assert "$1" in select_query and "$2" in select_query
    assert select_params == (9, 4)
    assert result["id"] == 9
    assert "key_hash" not in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_api_key_metadata_requires_at_least_one_field() -> None:
    db = _SqliteConnStub(row=None)
    with pytest.raises(ValueError, match="No updates provided"):
        await update_api_key_metadata(
            db,
            user_id=1,
            key_id=2,
            is_postgres=False,
        )
