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
    db = CharactersRAGDB(str(tmp_path / "persona_command_test_api.db"), client_id="persona-command-test-api-tests")
    yield db
    db.close_connection()


def _create_persona(client: TestClient, *, name: str) -> str:
    response = client.post(
        "/api/v1/persona/profiles",
        json={"name": name, "mode": "persistent_scoped"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_persona_command_dry_run_matches_parameterized_phrase(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Dry Run Builder")

        created = client.post(
            f"/api/v1/persona/profiles/{persona_id}/voice-commands",
            json={
                "name": "Search Notes",
                "phrases": ["search notes for {topic}"],
                "action_type": "mcp_tool",
                "action_config": {"tool_name": "notes.search"},
                "priority": 10,
                "enabled": True,
                "requires_confirmation": False,
            },
        )
        assert created.status_code == 201, created.text

        tested = client.post(
            f"/api/v1/persona/profiles/{persona_id}/voice-commands/test",
            json={"heard_text": "search notes for vector databases"},
        )
        assert tested.status_code == 200, tested.text
        payload = tested.json()
        assert payload["heard_text"] == "search notes for vector databases"
        assert payload["matched"] is True
        assert payload["match_reason"] == "phrase_pattern"
        assert payload["command_name"] == "Search Notes"
        assert payload["extracted_params"] == {"topic": "vector databases"}
        assert payload["planned_action"] == {
            "target_type": "mcp_tool",
            "target_name": "notes.search",
            "payload_preview": {"query": "vector databases"},
        }
        assert payload["safety_gate"] == {
            "classification": "read_only",
            "requires_confirmation": False,
            "reason": "persona_default",
        }
        assert payload["fallback_to_persona_planner"] is False

    fastapi_app.dependency_overrides.clear()


def test_persona_command_dry_run_returns_fallback_when_no_match(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Dry Run Builder")

        tested = client.post(
            f"/api/v1/persona/profiles/{persona_id}/voice-commands/test",
            json={"heard_text": "tell me a joke about tensors"},
        )
        assert tested.status_code == 200, tested.text
        payload = tested.json()
        assert payload["matched"] is False
        assert payload["fallback_to_persona_planner"] is True
        assert payload["failure_phase"] == "no_match"

    fastapi_app.dependency_overrides.clear()


def test_persona_command_dry_run_surfaces_missing_connection_dependency(
    persona_db: CharactersRAGDB,
):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Dry Run Broken Connection Builder")

        created_connection = client.post(
            f"/api/v1/persona/profiles/{persona_id}/connections",
            json={
                "name": "Alerts API",
                "base_url": "https://api.example.com/hooks",
                "auth_type": "none",
            },
        )
        assert created_connection.status_code == 201, created_connection.text
        connection_id = created_connection.json()["id"]

        created_command = client.post(
            f"/api/v1/persona/profiles/{persona_id}/voice-commands",
            json={
                "name": "Send Alert",
                "phrases": ["send alert for {query}"],
                "action_type": "custom",
                "connection_id": connection_id,
                "action_config": {
                    "action": "external_request",
                    "method": "POST",
                    "path": "alerts/send",
                },
                "priority": 10,
                "enabled": True,
                "requires_confirmation": True,
            },
        )
        assert created_command.status_code == 201, created_command.text
        command_id = created_command.json()["id"]

        deleted_connection = client.delete(
            f"/api/v1/persona/profiles/{persona_id}/connections/{connection_id}"
        )
        assert deleted_connection.status_code == 200, deleted_connection.text

        tested = client.post(
            f"/api/v1/persona/profiles/{persona_id}/voice-commands/test",
            json={"heard_text": "send alert for model drift"},
        )
        assert tested.status_code == 200, tested.text
        payload = tested.json()
        assert payload["heard_text"] == "send alert for model drift"
        assert payload["matched"] is True
        assert payload["command_id"] == command_id
        assert payload["command_name"] == "Send Alert"
        assert payload["connection_id"] == connection_id
        assert payload["connection_status"] == "missing"
        assert payload["connection_name"] is None
        assert payload["failure_phase"] == "missing_connection"
        assert payload["fallback_to_persona_planner"] is False

    fastapi_app.dependency_overrides.clear()
