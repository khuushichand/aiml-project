import pytest

import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint
from tldw_Server_API.app.core.AuthNZ.principal_model import AuthPrincipal


class _FakeSQLiteConn:
    def __init__(self) -> None:
        self.calls = []
        self.commits = 0

    async def execute(self, query, params):
        self.calls.append((query, params))

    async def commit(self):
        self.commits += 1


class _FakeAsyncPGConn:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, query, *params):
        self.calls.append((query, params))


# Mimic asyncpg module name so detection logic treats it as Postgres
_FakeAsyncPGConn.__module__ = "asyncpg.connection"


@pytest.mark.asyncio
async def test_setup_self_verify_updates_sqlite(monkeypatch):
    """SQLite-compatible execute receives normalized placeholders and commits."""
    monkeypatch.setattr(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        lambda: {"needs_setup": True},
    )

    fake_db = _FakeSQLiteConn()

    result = await setup_endpoint.setup_self_verify(
        principal=AuthPrincipal(kind="user", user_id=9, username="setup-user"),
        db=fake_db,
        _guard=None,
    )

    assert result["success"] is True
    assert len(fake_db.calls) == 1
    query, params = fake_db.calls[0]
    assert query == "UPDATE users SET is_verified = ?, updated_at = ? WHERE id = ?"
    assert params[0] is True
    assert params[2] == 9
    assert fake_db.commits == 1


@pytest.mark.asyncio
async def test_setup_self_verify_updates_asyncpg(monkeypatch):
    """AsyncPG-style execute preserves `$n` placeholders."""
    monkeypatch.setattr(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        lambda: {"needs_setup": True},
    )

    fake_db = _FakeAsyncPGConn()

    result = await setup_endpoint.setup_self_verify(
        principal=AuthPrincipal(kind="user", user_id=3, username="setup-user"),
        db=fake_db,
        _guard=None,
    )

    assert result["success"] is True
    assert len(fake_db.calls) == 1
    query, params = fake_db.calls[0]
    assert query == "UPDATE users SET is_verified = $1, updated_at = $2 WHERE id = $3"
    assert params[0] is True
    assert params[2] == 3
