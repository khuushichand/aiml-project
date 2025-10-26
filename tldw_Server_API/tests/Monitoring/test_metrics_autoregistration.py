import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.Metrics import track_metrics
from tldw_Server_API.app.core.Metrics import get_metrics_registry

pytestmark = pytest.mark.monitoring


def _make_test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/metrics", include_in_schema=False)
    async def metrics_root():
        registry = get_metrics_registry()
        metrics_text = registry.export_prometheus_format()
        return PlainTextResponse(metrics_text, media_type="text/plain; version=0.0.4")

    return app


@pytest.fixture
def client():
    app = _make_test_app()
    with TestClient(app) as c:
        yield c


def test_track_metrics_autoregisters_metrics(client):
    # Use a unique base name to avoid interference
    @track_metrics(name="test_auto_reg.myop")
    def sample_op():
        return 42

    # Invoke a few times
    for _ in range(3):
        sample_op()

    # Scrape metrics
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text

    # Ensure both counter and histogram appear in exposition
    assert "test_auto_reg.myop_calls_total" in text
    assert "test_auto_reg.myop_duration_seconds_bucket" in text
