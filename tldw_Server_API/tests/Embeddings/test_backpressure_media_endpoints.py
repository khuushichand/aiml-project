import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


class FakeRedisBP:
    def __init__(self, depth=0, age_first_ms=0):
        self.depth = depth
        self.age_first_ms = age_first_ms

    async def xlen(self, name):  # noqa: ARG002
        return self.depth

    async def xrange(self, name, min, max, count=None):  # noqa: ARG002
        if self.age_first_ms <= 0:
            return []
        return [(f"{self.age_first_ms}-0", {})]

    async def close(self):
        return True


def _override_user():
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin", email="a@x", is_active=True, is_admin=True)
    return _f


@pytest.mark.unit
def test_backpressure_blocks_paper_arxiv_ingest(monkeypatch):
    client = TestClient(app)
    app.dependency_overrides[get_request_user] = _override_user()
    fake = FakeRedisBP(depth=0, age_first_ms=1000)
    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):  # noqa: ARG001
        return fake

    monkeypatch.setenv("EMB_BACKPRESSURE_MAX_AGE_SECONDS", "0.1")
    monkeypatch.setattr(aioredis, "from_url", fake_from_url)
    r = client.post("/api/v1/paper-search/arxiv/ingest", params={"arxiv_id": "1706.03762"})
    assert r.status_code == 429
    app.dependency_overrides.pop(get_request_user, None)
