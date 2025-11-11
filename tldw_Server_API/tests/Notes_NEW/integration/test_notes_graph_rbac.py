import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.AuthNZ.jwt_service import JWTService
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings, get_settings


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_with_user_override(monkeypatch):
    # Configure JWT for tests (multi-user style virtual key)
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_SECRET_KEY", "graph_rbac_tests_secret_1234567890")
    reset_settings()

    async def override_user():
        # Provide a benign user object; auth is enforced by require_token_scope
        return User(id=1, username="tester", email="t@e.com", is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()
    # Ensure global settings cache is cleared so later tests aren't affected
    reset_settings()


def _make_token(scope: str) -> str:
    svc = JWTService(get_settings())
    return svc.create_virtual_access_token(user_id=1, username="tester", role="user", scope=scope, ttl_minutes=5)


def test_graph_read_forbidden_with_wrong_scope(client_with_user_override: TestClient):
    bad_token = _make_token(scope="media")  # Endpoint requires scope="notes"
    headers = {"Authorization": f"Bearer {bad_token}"}
    resp = client_with_user_override.get("/api/v1/notes/graph", headers=headers)
    assert resp.status_code == 403


def test_graph_read_allows_with_correct_scope(client_with_user_override: TestClient):
    good_token = _make_token(scope="notes")
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = client_with_user_override.get("/api/v1/notes/graph", headers=headers)
    # Handler is a stub; it should pass auth and return a 200 with empty graph structure
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "nodes" in data and "edges" in data


def test_graph_write_forbidden_with_wrong_scope(client_with_user_override: TestClient):
    bad_token = _make_token(scope="media")
    headers = {"Authorization": f"Bearer {bad_token}"}
    resp = client_with_user_override.post(
        "/api/v1/notes/n-1/links",
        headers=headers,
        json={"to_note_id": "n-2"},
    )
    assert resp.status_code == 403


def test_graph_write_allows_with_correct_scope(client_with_user_override: TestClient):
    good_token = _make_token(scope="notes")
    headers = {"Authorization": f"Bearer {good_token}"}
    resp = client_with_user_override.post(
        "/api/v1/notes/n-1/links",
        headers=headers,
        json={"to_note_id": "n-2"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload.get("status") == "stub"
