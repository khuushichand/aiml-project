import json
import os

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


class FakeRedisBP:
    def __init__(self, depth=0, age_first_ms=0):
        self.depth = depth
        self.age_first_ms = age_first_ms
        self._kv = {}
        self._incr = {}

    async def xlen(self, name):  # noqa: ARG002
        return self.depth

    async def xrange(self, name, min, max, count=None):  # noqa: ARG002
        if self.age_first_ms <= 0:
            return []
        return [(f"{self.age_first_ms}-0", {})]

    async def close(self):
        return True

    async def get(self, key):
        return self._kv.get(key)

    async def incr(self, key):
        self._incr[key] = self._incr.get(key, 0) + 1
        return self._incr[key]

    async def expire(self, key, ttl):  # noqa: ARG002
        return True


def _override_user(admin=False, uid="u1"):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=uid, username="admin" if admin else uid, email=f"{uid}@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_backpressure_by_age_returns_429(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_request_user] = _override_user(admin=True)
    # Force age above threshold
    fake = FakeRedisBP(depth=0, age_first_ms=1000)  # 1 second epoch

    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):  # noqa: ARG001
        return fake

    monkeypatch.setenv("EMB_BACKPRESSURE_MAX_AGE_SECONDS", "0.1")
    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    r = client.post("/api/v1/embeddings", json={"input": "hello", "model": "text-embedding-3-small"})
    assert r.status_code == 429
    assert r.headers.get("Retry-After") is not None
    app.dependency_overrides.pop(get_request_user, None)


@pytest.mark.unit
def test_tenant_quota_429(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_request_user] = _override_user(admin=False, uid="tenant1")
    fake = FakeRedisBP(depth=0, age_first_ms=0)
    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):  # noqa: ARG001
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("EMBEDDINGS_TENANT_RPS", "1")

    r1 = client.post("/api/v1/embeddings", json={"input": "hello", "model": "text-embedding-3-small"})
    # First should pass through to provider path; in CI it may 503 if providers missing; allow 200-503
    assert r1.status_code in (200, 503, 429)
    r2 = client.post("/api/v1/embeddings", json={"input": "hello", "model": "text-embedding-3-small"})
    assert r2.status_code == 429
    assert r2.headers.get("Retry-After") == "1"
    app.dependency_overrides.pop(get_request_user, None)
