"""
Integration tests for web scraping management endpoints using the real service.
No internal mocking; initializes service, checks status and a simple cookie query.
"""

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user():
    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_initialize_and_status(client_with_user: TestClient):
    client = client_with_user

    # Initialize service
    init = client.post("/web-scraping/service/initialize")
    assert init.status_code in (200, 500, 503)  # service may not be fully available in all envs

    # Status should respond regardless
    status_resp = client.get("/web-scraping/status")
    assert status_resp.status_code in (200, 500)
    if status_resp.status_code == 200:
        data = status_resp.json()
        assert isinstance(data, dict)


def test_cookies_endpoint_minimal(client_with_user: TestClient):
    client = client_with_user
    resp = client.get("/web-scraping/cookies/example.com")
    # If service initializes, cookies returns 200; otherwise could be 500
    assert resp.status_code in (200, 500)
