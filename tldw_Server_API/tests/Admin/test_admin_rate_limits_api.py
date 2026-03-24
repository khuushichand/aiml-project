from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.api.v1.endpoints.admin import admin_rate_limits


class _CursorStub:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = list(rows)

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class _SqliteRowLike:
    def __init__(self, keys: list[str], values: tuple[Any, ...]) -> None:
        self._keys = list(keys)
        self._values = tuple(values)

    def keys(self) -> list[str]:
        return list(self._keys)

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self._values[key]
        idx = self._keys.index(str(key))
        return self._values[idx]


class _SqliteDbStub:
    def __init__(self) -> None:
        self._is_sqlite = True
        self.execute_calls: list[tuple[str, Any]] = []

    async def execute(self, query: str, params: Any = ()) -> _CursorStub:
        self.execute_calls.append((str(query), params))
        normalized = str(query).lower()
        if "from rbac_role_rate_limits" in normalized:
            return _CursorStub(
                [
                    _SqliteRowLike(
                        ["scope", "id", "resource", "limit_per_min", "burst"],
                        ("role", 7, "/api/v1/chat/completions", 30, 5),
                    )
                ]
            )
        if "from rbac_user_rate_limits" in normalized:
            return _CursorStub(
                [
                    _SqliteRowLike(
                        ["scope", "id", "resource", "limit_per_min", "burst"],
                        ("user", 11, "/api/v1/rag/search", 12, 2),
                    )
                ]
            )
        raise AssertionError(f"Unexpected query: {query!r}")


class _PostgresDbStub:
    def __init__(self) -> None:
        self._is_sqlite = False
        self.fetch_calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls.append((str(query), tuple(args)))
        normalized = str(query).lower()
        if "from rbac_role_rate_limits" in normalized:
            return [
                {
                    "scope": "role",
                    "id": 3,
                    "resource": "/api/v1/media/search",
                    "limit_per_min": 60,
                    "burst": 10,
                }
            ]
        if "from rbac_user_rate_limits" in normalized:
            return [
                {
                    "scope": "user",
                    "id": 9,
                    "resource": "/api/v1/media/ingest/jobs",
                    "limit_per_min": 6,
                    "burst": 1,
                }
            ]
        raise AssertionError(f"Unexpected query: {query!r}")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_admin_rate_limits_reads_sqlite_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_is_postgres() -> bool:
        return False

    monkeypatch.setattr(
        admin_rate_limits,
        "_get_is_postgres_backend_fn",
        lambda: _fake_is_postgres,
    )
    db = _SqliteDbStub()

    response = await admin_rate_limits.list_admin_rate_limits(db=db)

    assert [item.model_dump() for item in response] == [  # nosec B101
        {
            "scope": "role",
            "id": 7,
            "resource": "/api/v1/chat/completions",
            "limit_per_min": 30,
            "burst": 5,
        },
        {
            "scope": "user",
            "id": 11,
            "resource": "/api/v1/rag/search",
            "limit_per_min": 12,
            "burst": 2,
        },
    ]
    assert len(db.execute_calls) == 2  # nosec B101


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_admin_rate_limits_reads_postgres_tables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_is_postgres() -> bool:
        return True

    monkeypatch.setattr(
        admin_rate_limits,
        "_get_is_postgres_backend_fn",
        lambda: _fake_is_postgres,
    )
    db = _PostgresDbStub()

    response = await admin_rate_limits.list_admin_rate_limits(db=db)

    assert [item.model_dump() for item in response] == [  # nosec B101
        {
            "scope": "role",
            "id": 3,
            "resource": "/api/v1/media/search",
            "limit_per_min": 60,
            "burst": 10,
        },
        {
            "scope": "user",
            "id": 9,
            "resource": "/api/v1/media/ingest/jobs",
            "limit_per_min": 6,
            "burst": 1,
        },
    ]
    assert len(db.fetch_calls) == 2  # nosec B101
