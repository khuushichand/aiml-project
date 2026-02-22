import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_persona_user():
    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    with TestClient(fastapi_app) as client:
        yield client
    fastapi_app.dependency_overrides.clear()


def test_persona_catalog_requires_auth():
    with TestClient(fastapi_app) as c:
        r = c.get("/api/v1/persona/catalog")
        assert r.status_code == 401


def test_persona_session_requires_auth():
    with TestClient(fastapi_app) as c:
        r = c.post("/api/v1/persona/session", json={"persona_id": "research_assistant"})
        assert r.status_code == 401


def test_persona_catalog_smoke(client_with_persona_user: TestClient):


    r = client_with_persona_user.get("/api/v1/persona/catalog")
    assert r.status_code == 200
    # Returns empty list if disabled; else list of personas
    assert isinstance(r.json(), list)


def test_persona_catalog_returns_404_when_disabled(client_with_persona_user: TestClient, monkeypatch):
    monkeypatch.setattr(persona_ep, "is_persona_enabled", lambda: False)
    r = client_with_persona_user.get("/api/v1/persona/catalog")
    assert r.status_code == 404


def test_persona_session_returns_404_when_disabled(client_with_persona_user: TestClient, monkeypatch):
    monkeypatch.setattr(persona_ep, "is_persona_enabled", lambda: False)
    r = client_with_persona_user.post("/api/v1/persona/session", json={"persona_id": "research_assistant"})
    assert r.status_code == 404
