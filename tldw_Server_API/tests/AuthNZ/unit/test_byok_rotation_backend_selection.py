from __future__ import annotations

import base64

import pytest

import tldw_Server_API.app.core.AuthNZ.byok_rotation as byok_rotation_module
from tldw_Server_API.app.core.AuthNZ.byok_rotation import RotationStats, rotate_byok_secrets
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


class _PoolStub:
    def __init__(self, *, postgres: bool) -> None:
        self.pool = object() if postgres else None


class _ConnStub:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []
        self.executemany_calls: list[tuple[str, list[tuple[str, int]]]] = []

    async def execute(self, query: str, *params: object) -> None:
        self.execute_calls.append((query, params))

    async def executemany(self, query: str, params: list[tuple[str, int]]) -> None:
        self.executemany_calls.append((query, params))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rotate_byok_secrets_uses_sqlite_when_pool_has_no_asyncpg_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_is_postgres: list[bool] = []

    async def _fake_rotate_table(
        *,
        pool,
        table: str,
        batch_size: int,
        dry_run: bool,
        is_postgres: bool,
    ) -> RotationStats:
        assert pool is sqlite_pool
        assert table in {"user_provider_secrets", "org_provider_secrets"}
        assert batch_size == 9
        assert dry_run is True
        captured_is_postgres.append(is_postgres)
        return RotationStats()

    monkeypatch.setattr(byok_rotation_module, "_rotate_table", _fake_rotate_table)
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"a"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()

    sqlite_pool = _PoolStub(postgres=False)
    summary = await rotate_byok_secrets(pool=sqlite_pool, batch_size=9, dry_run=True)

    assert summary.dry_run is True
    assert captured_is_postgres == [False, False]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_rotate_byok_secrets_uses_postgres_when_pool_has_asyncpg_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_is_postgres: list[bool] = []

    async def _fake_rotate_table(
        *,
        pool,
        table: str,
        batch_size: int,
        dry_run: bool,
        is_postgres: bool,
    ) -> RotationStats:
        assert pool is postgres_pool
        assert table in {"user_provider_secrets", "org_provider_secrets"}
        assert batch_size == 11
        assert dry_run is False
        captured_is_postgres.append(is_postgres)
        return RotationStats()

    monkeypatch.setattr(byok_rotation_module, "_rotate_table", _fake_rotate_table)
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"b"))
    monkeypatch.delenv("BYOK_SECONDARY_ENCRYPTION_KEY", raising=False)
    reset_settings()

    postgres_pool = _PoolStub(postgres=True)
    summary = await rotate_byok_secrets(pool=postgres_pool, batch_size=11, dry_run=False)

    assert summary.dry_run is False
    assert captured_is_postgres == [True, True]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_apply_updates_sqlite_path_uses_execute_even_when_executemany_exists() -> None:
    conn = _ConnStub()

    await byok_rotation_module._apply_updates(
        conn,
        table="user_provider_secrets",
        updates=[("blob-a", 1), ("blob-b", 2)],
        is_postgres=False,
    )

    assert conn.executemany_calls == []
    assert len(conn.execute_calls) == 2
    assert all("?" in query for query, _ in conn.execute_calls)
    assert all("$1" not in query for query, _ in conn.execute_calls)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_apply_updates_postgres_path_uses_executemany() -> None:
    conn = _ConnStub()

    await byok_rotation_module._apply_updates(
        conn,
        table="org_provider_secrets",
        updates=[("blob-c", 3), ("blob-d", 4)],
        is_postgres=True,
    )

    assert conn.execute_calls == []
    assert len(conn.executemany_calls) == 1
    query, params = conn.executemany_calls[0]
    assert "$1" in query
    assert "?" not in query
    assert params == [("blob-c", 3), ("blob-d", 4)]
