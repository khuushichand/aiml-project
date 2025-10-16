import pytest
import asyncio
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.app.core.Embeddings.workers.base_worker import BaseWorker, WorkerConfig


class _FakeRedisSkip:
    def __init__(self):
        self.kv = {}

    async def set(self, key, value, ex=None):
        self.kv[key] = value
        return True

    async def get(self, key):
        return self.kv.get(key)

    async def close(self):
        return True


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin" if admin else "u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_job_skip_mark_and_status(monkeypatch):
    client = TestClient(app)
    client.cookies.set("csrf_token", "x")
    client.headers["X-CSRF-Token"] = "x"
    client.headers["Authorization"] = "Bearer key"
    app.dependency_overrides[get_request_user] = _override_user(admin=True)

    import redis.asyncio as aioredis
    fake = _FakeRedisSkip()

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)

    # Mark skip
    r1 = client.post("/api/v1/embeddings/job/skip", json={"job_id": "job-x", "ttl_seconds": 600})
    assert r1.status_code == 200
    # Check status
    r2 = client.get("/api/v1/embeddings/job/skip/status", params={"job_id": "job-x"})
    assert r2.status_code == 200
    assert r2.json().get("skipped") is True

    app.dependency_overrides.pop(get_request_user, None)


@pytest.mark.unit
def test_worker_is_job_skipped_check():
    class _W(BaseWorker):
        def __init__(self):
            cfg = WorkerConfig(
                worker_id="storage-0",
                worker_type="storage",
                redis_url="redis://localhost:6379",
                queue_name="embeddings:storage",
                consumer_group="storage-workers",
            )
            super().__init__(cfg)
            self.redis_client = _FakeRedisSkip()

        async def process_message(self, message):
            return None

        def _parse_message(self, data):
            from tldw_Server_API.app.core.Embeddings.queue_schemas import StorageMessage
            return StorageMessage(
                job_id=data.get("job_id", "j"),
                user_id="u",
                media_id=1,
                embeddings=[],
                collection_name="c",
                total_chunks=0,
                processing_time_ms=1,
            )

        async def _send_to_next_stage(self, result):
            return None

    w = _W()
    # no skip key
    assert asyncio.run(w._is_job_skipped("job-y")) is False
    # set skip key
    asyncio.run(w.redis_client.set("embeddings:skip:job:job-y", "1"))
    assert asyncio.run(w._is_job_skipped("job-y")) is True
