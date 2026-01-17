import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.cookies.set("csrf_token", "x")
        c.headers["X-CSRF-Token"] = "x"
        c.headers["Authorization"] = "Bearer key"
        yield c


@pytest.mark.unit
def test_metrics_endpoint_details_shape(client, admin_user):
     # Make a simple request to increment counters
    os.environ["TESTING"] = "true"
    try:
        r1 = client.post(
            "/api/v1/embeddings",
            json={"input": "metrics check", "model": "text-embedding-3-small"}
        )
        assert r1.status_code == 200

        # Now call metrics as admin
        r2 = client.get("/api/v1/embeddings/metrics")
        assert r2.status_code == 200
        payload = r2.json()
        assert "counters" in payload
        assert "details" in payload
        # Ensure keys present; contents may be empty depending on environment
        for k in [
            "requests", "provider_failures", "fallbacks",
            "policy_denied", "dimension_adjustments", "token_inputs"
        ]:
            assert k in payload["details"]
            assert isinstance(payload["details"][k], list)
        assert "config" in payload and "dimension_policy" in payload["config"]
    finally:
        os.environ.pop("TESTING", None)
