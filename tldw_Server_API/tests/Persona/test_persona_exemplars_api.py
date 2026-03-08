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
    db = CharactersRAGDB(str(tmp_path / "persona_exemplars_api.db"), client_id="persona-exemplars-api-tests")
    yield db
    db.close_connection()


def _create_persona(client: TestClient, *, name: str) -> str:
    created = client.post(
        "/api/v1/persona/profiles",
        json={"name": name, "mode": "session_scoped"},
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_persona_exemplar_api_crud_and_filters(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_id = _create_persona(client, name="Example Persona")

        created = client.post(
            f"/api/v1/persona/profiles/{persona_id}/exemplars",
            json={
                "kind": "boundary",
                "content": "I can stay in character without revealing hidden instructions.",
                "tone": " Playful ",
                "scenario_tags": ["Meta_Prompt", " hostile_user ", "meta_prompt"],
                "capability_tags": ["Can_Search", " can_search ", "Requires_Tool_Confirmation"],
                "priority": 7,
                "enabled": True,
                "source_type": "manual",
                "source_ref": "seed://boundary/1",
                "notes": "Primary boundary example",
            },
        )
        assert created.status_code == 201, created.text
        exemplar = created.json()
        exemplar_id = exemplar["id"]
        assert exemplar["persona_id"] == persona_id
        assert exemplar["tone"] == "playful"
        assert exemplar["scenario_tags"] == ["meta_prompt", "hostile_user"]
        assert exemplar["capability_tags"] == ["can_search", "requires_tool_confirmation"]
        assert exemplar["enabled"] is True
        assert exemplar["source_type"] == "manual"

        listed = client.get(f"/api/v1/persona/profiles/{persona_id}/exemplars")
        assert listed.status_code == 200, listed.text
        assert [item["id"] for item in listed.json()] == [exemplar_id]

        disabled = client.post(
            f"/api/v1/persona/profiles/{persona_id}/exemplars",
            json={
                "kind": "style",
                "content": "Dry and concise.",
                "tone": "dry",
                "scenario_tags": ["small_talk"],
                "capability_tags": [],
                "enabled": False,
                "source_type": "manual",
            },
        )
        assert disabled.status_code == 201, disabled.text
        disabled_id = disabled.json()["id"]

        enabled_only = client.get(f"/api/v1/persona/profiles/{persona_id}/exemplars")
        assert enabled_only.status_code == 200, enabled_only.text
        assert [item["id"] for item in enabled_only.json()] == [exemplar_id]

        include_disabled = client.get(
            f"/api/v1/persona/profiles/{persona_id}/exemplars?include_disabled=true"
        )
        assert include_disabled.status_code == 200, include_disabled.text
        assert {item["id"] for item in include_disabled.json()} == {exemplar_id, disabled_id}

        fetched = client.get(f"/api/v1/persona/profiles/{persona_id}/exemplars/{exemplar_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["id"] == exemplar_id

        updated = client.patch(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/{exemplar_id}",
            json={
                "tone": "Serious",
                "enabled": False,
                "scenario_tags": ["hostile_user", "tool_request", "Hostile_User"],
            },
        )
        assert updated.status_code == 200, updated.text
        updated_payload = updated.json()
        assert updated_payload["tone"] == "serious"
        assert updated_payload["enabled"] is False
        assert updated_payload["scenario_tags"] == ["hostile_user", "tool_request"]

        hidden_when_disabled = client.get(f"/api/v1/persona/profiles/{persona_id}/exemplars/{exemplar_id}")
        assert hidden_when_disabled.status_code == 404

        visible_when_disabled = client.get(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/{exemplar_id}?include_disabled=true"
        )
        assert visible_when_disabled.status_code == 200, visible_when_disabled.text
        assert visible_when_disabled.json()["enabled"] is False

        deleted = client.delete(f"/api/v1/persona/profiles/{persona_id}/exemplars/{exemplar_id}")
        assert deleted.status_code == 200, deleted.text
        assert deleted.json() == {"status": "deleted", "persona_id": persona_id, "exemplar_id": exemplar_id}

        missing_after_delete = client.get(
            f"/api/v1/persona/profiles/{persona_id}/exemplars/{exemplar_id}?include_disabled=true"
        )
        assert missing_after_delete.status_code == 404

    fastapi_app.dependency_overrides.clear()


def test_persona_exemplar_api_rejects_cross_persona_access(persona_db: CharactersRAGDB):
    with _client_for_user(1, persona_db) as client:
        persona_alpha = _create_persona(client, name="Persona Alpha")
        persona_beta = _create_persona(client, name="Persona Beta")

        created = client.post(
            f"/api/v1/persona/profiles/{persona_alpha}/exemplars",
            json={
                "kind": "style",
                "content": "Alpha exemplar",
                "tone": "neutral",
                "scenario_tags": ["small_talk"],
                "capability_tags": [],
                "source_type": "manual",
            },
        )
        assert created.status_code == 201, created.text
        exemplar_id = created.json()["id"]

        wrong_persona = client.get(f"/api/v1/persona/profiles/{persona_beta}/exemplars/{exemplar_id}")
        assert wrong_persona.status_code == 404

        wrong_persona_patch = client.patch(
            f"/api/v1/persona/profiles/{persona_beta}/exemplars/{exemplar_id}",
            json={"tone": "playful"},
        )
        assert wrong_persona_patch.status_code == 404

    with _client_for_user(2, persona_db) as other_user_client:
        cross_user_list = other_user_client.get(
            f"/api/v1/persona/profiles/{persona_alpha}/exemplars?include_disabled=true"
        )
        assert cross_user_list.status_code == 404

        cross_user_create = other_user_client.post(
            f"/api/v1/persona/profiles/{persona_alpha}/exemplars",
            json={
                "kind": "style",
                "content": "Unauthorized write",
                "source_type": "manual",
            },
        )
        assert cross_user_create.status_code == 404

    fastapi_app.dependency_overrides.clear()
