import re
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.Chunking.Chunk_Lib import _ensure_chunk_metrics_registered


client = TestClient(app)


def test_prometheus_metrics_contains_http_and_chunking_fields():
    # Make a simple request to ensure HTTP middleware increments counters
    r = client.get("/favicon.ico")
    assert r.status_code in (200, 404)

    # Ensure chunking metrics are registered, then manually observe one
    reg = get_metrics_registry()
    _ensure_chunk_metrics_registered()
    reg.observe("chunk_time_seconds", 0.0123, labels={"method": "words", "unit": "seconds"})

    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text

    # HTTP metrics should appear
    assert "http_requests_total" in text
    assert "http_request_duration_seconds_bucket" in text

    # Chunking metric we observed should appear
    assert "chunk_time_seconds_bucket" in text


def test_chat_metrics_json_shape_basic():
    resp = client.get("/api/v1/metrics/chat")
    assert resp.status_code == 200
    data = resp.json()

    # Expected top-level keys
    assert "active_operations" in data
    assert "token_costs" in data
    assert isinstance(data["active_operations"], dict)
    assert isinstance(data["token_costs"], dict)
