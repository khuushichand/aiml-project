from __future__ import annotations

from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
from tldw_Server_API.app.main import app


def test_user_profile_metrics_emitted(auth_headers) -> None:
    registry = get_metrics_registry()
    before_fetch = len(registry.values.get("profile_fetch_latency_ms", []))
    before_section = len(registry.values.get("profile_section_latency_ms", []))

    with TestClient(app) as client:
        resp = client.get("/api/v1/users/me/profile", headers=auth_headers)
        assert resp.status_code == 200

    after_fetch = len(registry.values.get("profile_fetch_latency_ms", []))
    after_section = len(registry.values.get("profile_section_latency_ms", []))
    assert after_fetch > before_fetch
    assert after_section > before_section
