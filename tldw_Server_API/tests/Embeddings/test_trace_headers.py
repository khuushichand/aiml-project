import os
from fastapi.testclient import TestClient


def test_health_includes_trace_headers(monkeypatch):
    # Reduce startup work
    monkeypatch.setenv("TEST_MODE", "true")

    from tldw_Server_API.app.main import app

    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200
    # RequestIDMiddleware should set request id
    assert "X-Request-ID" in r.headers
    # Trace headers middleware should attach trace headers
    assert "traceparent" in r.headers
    assert "X-Trace-Id" in r.headers
