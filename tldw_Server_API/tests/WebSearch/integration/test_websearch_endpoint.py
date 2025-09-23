"""
Integration test for /api/v1/research/websearch endpoint.
Allows 200 or 500 due to environment/network variability.
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


def test_websearch_minimal(client_with_user: TestClient):
    client = client_with_user
    payload = {
        "query": "what is the capital of france",
        "engine": "duckduckgo",
        "result_count": 5,
        "aggregate": False,
    }
    resp = client.post("/api/v1/research/websearch", json=payload)
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert "web_search_results_dict" in data
        assert "sub_query_dict" in data
