import pytest

import tldw_Server_API.app.api.v1.endpoints.setup as setup_endpoint


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
    """SQLite connections use '?' placeholders and commit."""
    monkeypatch.setattr(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        lambda: {"needs_setup": True},
    )

    fake_db = _FakeSQLiteConn()

    result = await setup_endpoint.setup_self_verify(
        current_user={"id": 9},
        db=fake_db,
        _guard=None,
    )

    assert result["success"] is True
    assert fake_db.calls == [
        ("UPDATE users SET is_verified = ?, updated_at = datetime('now') WHERE id = ?", (1, 9))
    ]
    assert fake_db.commits == 1


@pytest.mark.asyncio
async def test_setup_self_verify_updates_asyncpg(monkeypatch):
    """AsyncPG-style connections keep `$1` parameter style and skip commit."""
    monkeypatch.setattr(
        setup_endpoint.setup_manager,
        "get_status_snapshot",
        lambda: {"needs_setup": True},
    )

    fake_db = _FakeAsyncPGConn()

    result = await setup_endpoint.setup_self_verify(
        current_user={"id": 3},
        db=fake_db,
        _guard=None,
    )

    assert result["success"] is True
    assert fake_db.calls == [
        ("UPDATE users SET is_verified = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2", (True, 3))
    ]
