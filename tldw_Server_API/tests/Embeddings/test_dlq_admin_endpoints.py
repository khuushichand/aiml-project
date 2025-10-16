import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


class FakeAsyncRedis:
    def __init__(self):
        self.streams = {}
        self.closed = False

    async def xrevrange(self, name, max, min, count=None):
        items = self.streams.get(name, [])
        # items stored as list[(id, fields)] oldest->newest
        res = list(reversed(items))
        if count is not None:
            res = res[:count]
        return res

    async def xrange(self, name, min, max, count=None):
        items = self.streams.get(name, [])
        filtered = [item for item in items if item[0] == min]
        if count is not None:
            filtered = filtered[:count]
        return filtered

    async def xadd(self, name, fields):
        arr = self.streams.setdefault(name, [])
        eid = f"{len(arr)+1}-0"
        arr.append((eid, dict(fields)))
        return eid

    async def xdel(self, name, *ids):
        arr = self.streams.get(name, [])
        keep = [(i, f) for (i, f) in arr if i not in ids]
        self.streams[name] = keep
        return len(arr) - len(keep)

    async def close(self):
        self.closed = True


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin" if admin else "u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_dlq_list_and_requeue(monkeypatch):
    client = TestClient(app)
    client.cookies.set("csrf_token", "x")
    client.headers["X-CSRF-Token"] = "x"
    client.headers["Authorization"] = "Bearer key"
    app.dependency_overrides[get_request_user] = _override_user(admin=True)

    # Patch redis client factory used by endpoints
    fake = FakeAsyncRedis()
    dlq_stream = "embeddings:embedding:dlq"
    entry_id = "1-0"
    fake.streams[dlq_stream] = [
        (entry_id, {
            "original_queue": "embeddings:embedding",
            "consumer_group": "embedding-group",
            "worker_id": "w1",
            "job_id": "job-123",
            "job_type": "embedding",
            "error": "boom",
            "retry_count": "3",
            "max_retries": "3",
            "failed_at": "2025-01-01T00:00:00Z",
            "payload": json.dumps({"job_id": "job-123"}),
        })
    ]

    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)

    # List DLQ
    r1 = client.get("/api/v1/embeddings/dlq", params={"stage": "embedding", "count": 10})
    assert r1.status_code == 200
    data = r1.json()
    assert data["stream"] == dlq_stream
    assert data["count"] == 1
    assert data["items"][0]["job_id"] == "job-123"

    # Requeue the item
    r2 = client.post(
        "/api/v1/embeddings/dlq/requeue",
        json={"stage": "embedding", "entry_id": entry_id, "delete_from_dlq": True}
    )
    assert r2.status_code == 200
    # Verify it was moved to live stream
    live = fake.streams.get("embeddings:embedding", [])
    assert len(live) == 1
    # Verify DLQ deletion
    assert len(fake.streams.get(dlq_stream, [])) == 0

    # Cleanup override
    app.dependency_overrides.pop(get_request_user, None)
