import pytest


pytestmark = pytest.mark.integration


def _register_and_login(client, *, username: str, email: str, password: str) -> dict[str, str]:
    register = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    assert register.status_code == 200, register.text

    login = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _current_user_id(client, headers: dict[str, str]) -> str:
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200, me.text
    return str(me.json()["id"])


def _create_character_and_chat(client, headers: dict[str, str]) -> str:
    create_character = client.post(
        "/api/v1/characters/",
        json={
            "name": "Linked Research Character",
            "description": "For research-linked chat endpoint tests",
            "personality": "Helpful",
            "first_message": "Hello!",
        },
        headers=headers,
    )
    assert create_character.status_code == 201, create_character.text
    character_id = create_character.json()["id"]

    create_chat = client.post(
        "/api/v1/chats/",
        json={"character_id": character_id, "title": "Owner chat"},
        headers=headers,
    )
    assert create_chat.status_code == 201, create_chat.text
    return create_chat.json()["id"]


def test_chat_research_runs_endpoint_enforces_chat_ownership(isolated_test_environment):
    from tldw_Server_API.app.core.Research.service import ResearchService

    class DummyJobs:
        def create_job(self, **kwargs):
            return {"id": 41, "uuid": "job-41", "status": "queued"}

    client, _db_name = isolated_test_environment
    owner_headers = _register_and_login(
        client,
        username="research_owner",
        email="research_owner@example.com",
        password="Owner@Pass#2024!",
    )
    other_headers = _register_and_login(
        client,
        username="research_other",
        email="research_other@example.com",
        password="Other@Pass#2024!",
    )

    owner_user_id = _current_user_id(client, owner_headers)
    chat_id = _create_character_and_chat(client, owner_headers)

    service = ResearchService(
        research_db_path=None,
        outputs_dir=None,
        job_manager=DummyJobs(),
    )
    session = service.create_session(
        owner_user_id=owner_user_id,
        query="Verify chat-linked research ownership",
        source_policy="balanced",
        autonomy_mode="checkpointed",
        chat_handoff={"chat_id": chat_id},
    )

    owner_response = client.get(f"/api/v1/chats/{chat_id}/research-runs", headers=owner_headers)
    assert owner_response.status_code == 200, owner_response.text
    assert owner_response.json()["runs"][0]["run_id"] == session.id

    other_response = client.get(f"/api/v1/chats/{chat_id}/research-runs", headers=other_headers)
    assert other_response.status_code == 404, other_response.text
