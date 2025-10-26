import re
import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.endpoints.metrics import router as metrics_router
from tldw_Server_API.app.core.Metrics import get_metrics_registry
from tldw_Server_API.app.core.Metrics.http_middleware import HTTPMetricsMiddleware
from tldw_Server_API.app.core.Metrics.metrics_manager import MetricDefinition, MetricType

pytestmark = pytest.mark.monitoring


def _make_test_app() -> FastAPI:
    a = FastAPI()

    # Root Prometheus metrics endpoint (mirror main.py behavior)
    @a.get("/metrics", include_in_schema=False)
    async def metrics_root():
        registry = get_metrics_registry()
        metrics_text = registry.export_prometheus_format()
        return PlainTextResponse(metrics_text, media_type="text/plain; version=0.0.4")

    # Include metrics router (JSON, health, chat, text)
    a.include_router(metrics_router, prefix="/api/v1", tags=["metrics"])

    # Add HTTP metrics middleware
    a.add_middleware(HTTPMetricsMiddleware)
    return a


@pytest.fixture
def client():
    app = _make_test_app()
    with TestClient(app) as c:
        yield c


def test_prometheus_metrics_contains_http_and_chunking_fields(client):
    # Make a simple request to ensure HTTP middleware increments counters
    r = client.get("/favicon.ico")
    assert r.status_code in (200, 404)

    # Ensure chunking metric is registered, then manually observe one
    reg = get_metrics_registry()
    reg.register_metric(MetricDefinition(
        name='chunk_time_seconds',
        type=MetricType.HISTOGRAM,
        description='Chunking operation duration in seconds',
        labels=['method', 'unit']
    ))
    reg.observe("chunk_time_seconds", 0.0123, labels={"method": "words", "unit": "seconds"})

    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text

    # HTTP metrics should appear
    assert "http_requests_total" in text
    assert "http_request_duration_seconds_bucket" in text

    # Chunking metric we observed should appear
    assert "chunk_time_seconds_bucket" in text


def test_chat_metrics_json_shape_basic(client):
    resp = client.get("/api/v1/metrics/chat")
    assert resp.status_code == 200
    data = resp.json()

    # Expected top-level keys
    assert "active_operations" in data
    assert "token_costs" in data
    assert isinstance(data["active_operations"], dict)
    assert isinstance(data["token_costs"], dict)
