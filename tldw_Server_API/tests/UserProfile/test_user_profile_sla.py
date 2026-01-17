from __future__ import annotations

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


def _reset_metrics(registry) -> None:
    registry.values.clear()
    registry._cumulative_counters.clear()


def test_user_profile_sla_breach_metric(auth_headers, monkeypatch) -> None:
    registry = get_metrics_registry()
    _reset_metrics(registry)
    monkeypatch.setenv("PROFILE_SLA_MS", "0")

    with TestClient(app) as client:
        resp = client.get("/api/v1/users/me/profile", headers=auth_headers)
        assert resp.status_code == 200

    counters = registry._cumulative_counters.get("profile_sla_breach_total", {})
    assert counters


def test_admin_profile_batch_sla_breach_metric(auth_headers, monkeypatch) -> None:
    registry = get_metrics_registry()
    _reset_metrics(registry)
    monkeypatch.setenv("PROFILE_BATCH_BASE_MS", "0")

    with TestClient(app) as client:
        resp = client.get("/api/v1/admin/users/profile", headers=auth_headers)
        assert resp.status_code == 200

    counters = registry._cumulative_counters.get("profile_batch_sla_breach_total", {})
    assert counters
