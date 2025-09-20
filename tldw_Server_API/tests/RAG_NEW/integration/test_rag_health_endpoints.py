"""
Integration tests for RAG health endpoints.
No mocks; assert JSON shape and expected status codes.
"""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


pytestmark = pytest.mark.integration


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_rag_liveness_and_readiness(client: TestClient):
    live = client.get("/api/v1/rag/health/live")
    assert live.status_code == 200
    assert live.json().get("status") == "alive"

    ready = client.get("/api/v1/rag/health/ready")
    assert ready.status_code in (200, 503)
    if ready.status_code == 200:
        assert ready.json().get("status") == "ready"


def test_rag_full_health_and_cache_stats(client: TestClient):
    health = client.get("/api/v1/rag/health")
    assert health.status_code == 200
    h = health.json()
    assert isinstance(h, dict)
    assert "status" in h and "components" in h
    assert isinstance(h["components"], dict)

    cache = client.get("/api/v1/rag/cache/stats")
    assert cache.status_code in (200, 500)
    if cache.status_code == 200:
        stats = cache.json()
        assert isinstance(stats, dict)


def test_rag_health_components_when_present(client: TestClient):
    """If components are present in health report, validate basic shape and allowed statuses."""
    resp = client.get("/api/v1/rag/health")
    assert resp.status_code == 200
    h = resp.json()
    comps = h.get("components", {})
    assert isinstance(comps, dict)

    # Check known components if present
    for key in list(comps.keys()):
        comp = comps[key]
        assert isinstance(comp, dict)
        assert comp.get("status") in ("healthy", "degraded", "unhealthy")
        if key.startswith("circuit_breaker_"):
            # Circuit breaker component should include state and failure_rate
            if "state" not in comp or "failure_rate" not in comp:
                pytest.skip("Circuit breaker details not exposed in this environment")
        if key == "cache":
            # Cache component provides hit_rate/size where available
            if "hit_rate" not in comp or "size" not in comp:
                pytest.skip("Cache stats not exposed in this environment")
        if key == "metrics":
            # Metrics component should include recent_queries when available
            if "recent_queries" not in comp:
                pytest.skip("Metrics stats not exposed in this environment")
        if key == "batch_processor":
            # Batch processor should include active_jobs and success_rate
            if "active_jobs" not in comp or "success_rate" not in comp:
                pytest.skip("Batch processor stats not exposed in this environment")
