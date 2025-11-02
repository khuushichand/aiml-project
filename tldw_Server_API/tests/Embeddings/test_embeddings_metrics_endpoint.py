import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.cookies.set("csrf_token", "x")
        c.headers["X-CSRF-Token"] = "x"
        c.headers["Authorization"] = "Bearer key"
        yield c


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="admin" if admin else "u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_metrics_endpoint_details_shape(client):
    # Make a simple request to increment counters
    os.environ["TESTING"] = "true"
    try:
        app.dependency_overrides[get_request_user] = _override_user(admin=True)
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
