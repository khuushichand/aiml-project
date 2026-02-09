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
