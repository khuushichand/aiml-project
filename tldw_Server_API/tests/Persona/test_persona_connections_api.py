import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import persona as persona_ep
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit

fastapi_app = FastAPI()
fastapi_app.include_router(persona_ep.router, prefix="/api/v1/persona")


def _client_for_user(user_id: int, db: CharactersRAGDB):
    async def override_user():
        return User(id=user_id, username=f"persona-user-{user_id}", email=None, is_active=True)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[get_chacha_db_for_user] = lambda: db
    return TestClient(fastapi_app)


@pytest.fixture()
def persona_db(tmp_path):
    db = CharactersRAGDB(str(tmp_path / "persona_connections_api.db"), client_id="persona-connections-api-tests")
    yield db
    db.close_connection()


def _create_persona(client: TestClient, *, name: str) -> str:
    response = client.post(
        "/api/v1/persona/profiles",
        json={"name": name, "mode": "persistent_scoped"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_persona_connections_create_and_list_are_scoped_and_redacted(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_a = _create_persona(client, name="Connection Builder A")
        persona_b = _create_persona(client, name="Connection Builder B")

        created = client.post(
            f"/api/v1/persona/profiles/{persona_a}/connections",
            json={
                "name": "Primary API",
                "base_url": "https://api.example.com/v1",
                "auth_type": "bearer",
                "headers_template": {"X-Client": "voice-builder"},
                "timeout_ms": 12000,
            },
        )
        assert created.status_code == 201, created.text
        created_payload = created.json()
        assert created_payload["persona_id"] == persona_a
        assert created_payload["name"] == "Primary API"
        assert created_payload["allowed_hosts"] == ["api.example.com"]
        assert created_payload["secret_configured"] is False
        assert created_payload["key_hint"] is None

        listed_a = client.get(f"/api/v1/persona/profiles/{persona_a}/connections")
        assert listed_a.status_code == 200, listed_a.text
        list_a_payload = listed_a.json()
        assert len(list_a_payload) == 1
        assert list_a_payload[0]["id"] == created_payload["id"]

        listed_b = client.get(f"/api/v1/persona/profiles/{persona_b}/connections")
        assert listed_b.status_code == 200, listed_b.text
        assert listed_b.json() == []

    fastapi_app.dependency_overrides.clear()
