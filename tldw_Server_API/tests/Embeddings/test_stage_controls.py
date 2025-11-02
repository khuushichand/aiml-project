import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


class FakeAsyncRedisCtl:
    def __init__(self):
        self.kv = {}
        self.closed = False

    async def get(self, key):
        return self.kv.get(key)

    async def set(self, key, val):
        self.kv[key] = str(val)
        return True

    async def delete(self, key):
        if key in self.kv:
            del self.kv[key]
            return 1
        return 0

    async def close(self):
        self.closed = True


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin" if admin else "u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_stage_pause_resume_drain(monkeypatch):
    client = TestClient(app)
    client.cookies.set("csrf_token", "x")
    client.headers["X-CSRF-Token"] = "x"
    client.headers["Authorization"] = "Bearer key"
    app.dependency_overrides[get_request_user] = _override_user(admin=True)

    fake = FakeAsyncRedisCtl()

    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)

    # Initial status should be false
    r0 = client.get("/api/v1/embeddings/stage/status")
    assert r0.status_code == 200
    st = r0.json()
    assert st["embedding"]["paused"] is False

    # Pause embedding
    r1 = client.post("/api/v1/embeddings/stage/control", json={"stage": "embedding", "action": "pause"})
    assert r1.status_code == 200
    r2 = client.get("/api/v1/embeddings/stage/status")
    assert r2.status_code == 200
    assert r2.json()["embedding"]["paused"] is True

    # Drain embedding (sets paused + drain)
    r3 = client.post("/api/v1/embeddings/stage/control", json={"stage": "embedding", "action": "drain"})
    assert r3.status_code == 200
    r4 = client.get("/api/v1/embeddings/stage/status")
    assert r4.json()["embedding"]["paused"] is True
    assert r4.json()["embedding"]["drain"] is True

    # Resume embedding
    r5 = client.post("/api/v1/embeddings/stage/control", json={"stage": "embedding", "action": "resume"})
    assert r5.status_code == 200
    r6 = client.get("/api/v1/embeddings/stage/status")
    assert r6.json()["embedding"]["paused"] is False
    assert r6.json()["embedding"]["drain"] is False

    app.dependency_overrides.pop(get_request_user, None)
