import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


class FakeRedisKV:
    def __init__(self):
        self.kv = {}

    async def set(self, k, v):
        self.kv[k] = v
        return True

    async def expire(self, k, ttl):  # noqa: ARG002
        return True

    async def close(self):
        return True


def _override_admin():
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin", email="a@x", is_active=True, is_admin=True)
    return _f


@pytest.mark.unit
def test_bump_priority_sets_override(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_request_user] = _override_admin()
    fake = FakeRedisKV()
    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):  # noqa: ARG001
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    r = client.post("/api/v1/embeddings/job/priority/bump", json={"job_id": "j1", "priority": "high", "ttl_seconds": 60})
    assert r.status_code == 200
    assert fake.kv.get("embeddings:priority:override:j1") == "high"
    app.dependency_overrides.pop(get_request_user, None)
