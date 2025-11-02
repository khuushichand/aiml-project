import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


client = TestClient(app)


def _api_key():
    return os.getenv("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def test_mcp_metrics_json_admin_only():
    # Without auth -> 401
    r0 = client.get("/api/v1/mcp/metrics")
    assert r0.status_code in (401, 403)

    # With single-user API key -> 200
    r1 = client.get("/api/v1/mcp/metrics", headers={"X-API-KEY": _api_key()})
    assert r1.status_code == 200, r1.text
    data = r1.json()
    assert isinstance(data, dict)
    assert "connections" in data and "modules" in data


def test_mcp_metrics_prometheus_gated_then_public(monkeypatch):
    # Default: gated; without auth -> 401
    r0 = client.get("/api/v1/mcp/metrics/prometheus")
    assert r0.status_code == 401

    # With admin (single-user) -> 200 and text/plain
    r1 = client.get("/api/v1/mcp/metrics/prometheus", headers={"X-API-KEY": _api_key()})
    assert r1.status_code == 200
    assert r1.headers.get("content-type", "").startswith("text/plain")
    assert isinstance(r1.content, (bytes, bytearray))

    # Public mode: unauthenticated allowed
    monkeypatch.setenv("MCP_PROMETHEUS_PUBLIC", "1")
    r2 = client.get("/api/v1/mcp/metrics/prometheus")
    assert r2.status_code == 200
    assert r2.headers.get("content-type", "").startswith("text/plain")
    # restore
    monkeypatch.delenv("MCP_PROMETHEUS_PUBLIC", raising=False)


_RUN_MCP = os.getenv("RUN_MCP_TESTS", "").lower() in ("1", "true", "yes")
pytestmark = pytest.mark.skipif(not _RUN_MCP, reason="MCP tests disabled by default; set RUN_MCP_TESTS=1 to enable")
