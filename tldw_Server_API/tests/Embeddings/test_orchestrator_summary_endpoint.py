import json
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user
from tldw_Server_API.tests.Embeddings.fakes import FakeAsyncRedisSummary
from tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced import _build_orchestrator_snapshot


def _override_user_admin():
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=42, username="admin", email="a@x", is_active=True, is_admin=True)
    return _f


@pytest.mark.unit
def test_orchestrator_summary_endpoint(disable_heavy_startup, admin_user, redis_client):
    async def _seed():
        queues = {
            "embeddings:chunking": 1,
            "embeddings:embedding": 2,
            "embeddings:storage": 3,
        }
        for name, count in queues.items():
            for idx in range(count):
                await redis_client.xadd(name, {"seq": str(idx)})
        await redis_client.xadd("embeddings:embedding:dlq", {"error": "boom"})
        metrics = [
            {"worker_type": "chunking", "jobs_processed": 10, "jobs_failed": 1},
            {"worker_type": "embedding", "jobs_processed": 20, "jobs_failed": 2},
            {"worker_type": "storage", "jobs_processed": 30, "jobs_failed": 3},
        ]
        for idx, metric in enumerate(metrics):
            await redis_client.set(f"worker:metrics:{idx}", json.dumps(metric))

    redis_client.run(_seed())

    client = TestClient(app)
    resp = client.get("/api/v1/embeddings/orchestrator/summary")
    assert resp.status_code == 200
    data = resp.json()

    # Basic shape
    for key in ("queues", "dlq", "ages", "stages", "flags", "ts"):
        assert key in data

    # Depths reflect fake values
    assert data["queues"].get("embeddings:embedding") == 2
    assert data["dlq"].get("embeddings:embedding:dlq") == 1

    # Aggregated stage counters
    assert data["stages"].get("chunking", {}).get("processed") == 10
    assert data["stages"].get("embedding", {}).get("processed") == 20
    assert data["stages"].get("storage", {}).get("processed") == 30

    # Ages present and non-negative floats
    assert "embeddings:embedding" in data["ages"]
    assert isinstance(data["ages"]["embeddings:embedding"], (int, float))
    assert data["ages"]["embeddings:embedding"] >= 0

    # Flags default to false when keys missing
    assert data["flags"].get("embedding", {}).get("paused") is False
    assert data["flags"].get("embedding", {}).get("drain") is False


@pytest.mark.unit
def test_orchestrator_summary_endpoint_unauthorized(monkeypatch):
    # Force multi-user mode so require_admin enforces admin check
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()

    # Override auth dependency to simulate non-admin active user
    async def _non_admin_user():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=7, username="user", email="u@x", is_active=True, is_admin=False)

    app.dependency_overrides[get_request_user] = _non_admin_user

    # Patch redis client factory used by the endpoint
    import redis.asyncio as aioredis
    fake = FakeAsyncRedisSummary()

    async def fake_from_url(url, decode_responses=True):
        return fake

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)

    client = TestClient(app)
    resp = client.get("/api/v1/embeddings/orchestrator/summary")
    assert resp.status_code == 403

    # Cleanup overrides and reset settings back to default for isolation
    app.dependency_overrides.pop(get_request_user, None)
    reset_settings()


@pytest.mark.unit
@pytest.mark.parametrize('stage', ['chunking', 'embedding', 'storage'])
def test_orchestrator_summary_flags_per_stage(disable_heavy_startup, admin_user, redis_client, stage):
    # Set flags before request
    async def _set_flags():
        await redis_client.set(f"embeddings:stage:{stage}:paused", "1")
        await redis_client.set(f"embeddings:stage:{stage}:drain", "1")

    redis_client.run(_set_flags())

    client = TestClient(app)
    resp = client.get("/api/v1/embeddings/orchestrator/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data['flags'][stage]['paused'] is True
    assert data['flags'][stage]['drain'] is True


@pytest.mark.unit
def test_orchestrator_summary_no_redis(monkeypatch):
    # When Redis connection fails, endpoint should return 200 with zeroed structure
    app.dependency_overrides[get_request_user] = _override_user_admin()

    import redis.asyncio as aioredis

    async def fake_from_url(url, decode_responses=True):
        raise ConnectionError("cannot connect")

    monkeypatch.setattr(aioredis, "from_url", fake_from_url)

    client = TestClient(app)
    resp = client.get("/api/v1/embeddings/orchestrator/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"queues", "dlq", "ages", "stages", "flags", "ts"}
    assert data["queues"] == {}
    assert data["dlq"] == {}
    assert data["ages"] == {}
    assert data["stages"] == {}
    assert data["flags"] == {}

    app.dependency_overrides.pop(get_request_user, None)


@pytest.mark.unit
def test_build_orchestrator_snapshot_age_deterministic(monkeypatch):
    # Directly call the builder with a fixed now_ts to assert ages precisely
    fake = FakeAsyncRedisSummary()
    fixed_now = 1700000001.0  # seconds; 1 second after 1700000000000 ms id

    # Drive the builder
    import asyncio as _asyncio

    async def _run():
        return await _build_orchestrator_snapshot(fake, now_ts=fixed_now)

    snapshot = _asyncio.run(_run())
    assert snapshot["ages"]["embeddings:chunking"] == 1.0
    assert snapshot["ages"]["embeddings:embedding"] == 1.0
    assert snapshot["ages"]["embeddings:storage"] == 1.0


@pytest.mark.unit
def test_build_orchestrator_snapshot_age_zero_when_empty_xrange():
    # With empty XRANGE on a queue, age must be exactly 0.0
    fake = FakeAsyncRedisSummary()

    import asyncio as _asyncio

    async def _run():
        await fake.configure_xrange_empty("embeddings:embedding", True)
        return await _build_orchestrator_snapshot(fake, now_ts=1700000001.0)

    snapshot = _asyncio.run(_run())
    assert snapshot["ages"]["embeddings:embedding"] == 0.0


@pytest.mark.unit
def test_orchestrator_summary_priority_depths(disable_heavy_startup, admin_user, redis_client, monkeypatch):
    # Enable priority flag and seed per-priority queue depths
    monkeypatch.setenv("EMBEDDINGS_PRIORITY_ENABLED", "true")
    async def _seed_priority():
        for name, count in (
            ("embeddings:embedding:high", 5),
            ("embeddings:embedding:normal", 3),
            ("embeddings:embedding:low", 1),
        ):
            for idx in range(count):
                await redis_client.xadd(name, {"seq": f"{name}:{idx}"})

    redis_client.run(_seed_priority())
    client = TestClient(app)
    resp = client.get("/api/v1/embeddings/orchestrator/summary")
    assert resp.status_code == 200
    data = resp.json()
    # Queues dictionary includes sub-queues
    assert data["queues"].get("embeddings:embedding:high") == 5
    # Priority summary present
    assert data.get("priority", {}).get("embedding", {}).get("high") == 5
