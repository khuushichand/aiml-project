import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


class _FakeAsyncRedis:
    def __init__(self):
        self.streams = {}
        self.kv = {}
        self.hash = {}

    async def xrevrange(self, name, max, min, count=None):
        items = self.streams.get(name, [])
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

    async def hgetall(self, key):
        return self.hash.get(key, {}).copy()

    async def hset(self, key, mapping=None, **kwargs):
        m = dict(mapping or {})
        h = self.hash.setdefault(key, {})
        h.update(m)
        return True

    async def close(self):
        return True


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin" if admin else "u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_dlq_quarantine_blocks_requeue_then_approve(monkeypatch):
    client = TestClient(app)
    client.cookies.set("csrf_token", "x")
    client.headers["X-CSRF-Token"] = "x"
    client.headers["Authorization"] = "Bearer key"
    app.dependency_overrides[get_request_user] = _override_user(admin=True)

    import redis.asyncio as aioredis
    fake = _FakeAsyncRedis()
    dlq_stream = "embeddings:embedding:dlq"
    entry_id = "1-0"
    # Add a DLQ entry with default fields (dlq_state optional)
    fake.streams[dlq_stream] = [
        (entry_id, {
            "original_queue": "embeddings:embedding",
            "consumer_group": "embedding-group",
            "worker_id": "w1",
            "job_id": "job-abc",
            "job_type": "embedding",
            "error": "boom",
            "retry_count": "3",
            "max_retries": "3",
            "failed_at": "2025-01-01T00:00:00Z",
            "payload": json.dumps({"job_id": "job-abc"}),
        })
    ]

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)

    # Put state to quarantined via API
    r1 = client.post("/api/v1/embeddings/dlq/state", json={
        "stage": "embedding",
        "entry_id": entry_id,
        "state": "quarantined"
    })
    assert r1.status_code == 200

    # Requeue should be blocked
    r2 = client.post("/api/v1/embeddings/dlq/requeue", json={"stage": "embedding", "entry_id": entry_id, "delete_from_dlq": False})
    assert r2.status_code == 400

    # Approve with operator note
    r3 = client.post("/api/v1/embeddings/dlq/state", json={
        "stage": "embedding",
        "entry_id": entry_id,
        "state": "approved_for_requeue",
        "operator_note": "OK after fix"
    })
    assert r3.status_code == 200

    # Requeue should succeed now
    r4 = client.post("/api/v1/embeddings/dlq/requeue", json={"stage": "embedding", "entry_id": entry_id, "delete_from_dlq": True})
    assert r4.status_code == 200
    # Ensure moved to live stream
    live = fake.streams.get("embeddings:embedding", [])
    assert len(live) == 1

    app.dependency_overrides.pop(get_request_user, None)
