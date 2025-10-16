import os
import pytest

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.tests.Embeddings.fakes import FakeAsyncRedisSummary


@pytest.fixture
def disable_heavy_startup(monkeypatch):
    monkeypatch.setenv("DISABLE_HEAVY_STARTUP", "1")
    yield


@pytest.fixture
def admin_user():
    async def _admin():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=42, username="admin", email="a@x", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = _admin
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_request_user, None)


@pytest.fixture
def fake_redis(monkeypatch):
    import redis.asyncio as aioredis
    fake = FakeAsyncRedisSummary()

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    return fake

