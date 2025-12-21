from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.api_keys_repo import AuthnzApiKeysRepo


class _FakeConn:
    """Minimal asyncpg-like connection for status parsing tests."""

    def __init__(self, status: str):
        self._status = status

    async def execute(self, *args, **kwargs):
        return self._status

    async def fetchrow(self, *args, **kwargs):  # pragma: no cover - not used
        return None


class _FakeTx:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    """Pool stub exposing a transaction() context manager."""

    def __init__(self, status: str):
        self._conn = _FakeConn(status)

    def transaction(self):
        return _FakeTx(self._conn)


@pytest.mark.asyncio
async def test_expire_keys_before_parses_update_count_from_status_string():
    """expire_keys_before should parse the affected-row count from asyncpg status."""
    repo = AuthnzApiKeysRepo(db_pool=_FakePool("UPDATE 3"))
    now = datetime.now(timezone.utc)
    count = await repo.expire_keys_before(
        now=now,
        expired_status="expired",
        active_status="active",
    )
    assert count == 3


@pytest.mark.asyncio
async def test_expire_keys_before_returns_zero_for_update_zero_status():
    """expire_keys_before should return 0 when asyncpg reports UPDATE 0."""
    repo = AuthnzApiKeysRepo(db_pool=_FakePool("UPDATE 0"))
    now = datetime.now(timezone.utc)
    count = await repo.expire_keys_before(
        now=now,
        expired_status="expired",
        active_status="active",
    )
    assert count == 0
