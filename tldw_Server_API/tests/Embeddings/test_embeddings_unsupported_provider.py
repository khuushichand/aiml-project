import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


@pytest.fixture(autouse=True)
def _testing_env():
    os.environ["TESTING"] = "true"
    yield
    os.environ.pop("TESTING", None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.cookies.set("csrf_token", "csrf")
        c.headers["X-CSRF-Token"] = "csrf"
        c.headers["Authorization"] = "Bearer test-api-key"
        yield c


def _override_user(admin=False):
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=admin)
    return _f


@pytest.mark.unit
def test_unsupported_provider_returns_501(client):
    # Ensure admin bypass does not affect behavior (use non-admin)
    app.dependency_overrides[get_request_user] = _override_user(admin=False)
    # request with an enum-known but not implemented provider (mistral)
    r = client.post(
        "/api/v1/embeddings",
        headers={"x-provider": "mistral"},
        json={"input": "hello", "model": "mistral-embed"}
    )
    assert r.status_code == 501
    body = r.json()
    assert "not implemented" in body.get("detail", "").lower()
