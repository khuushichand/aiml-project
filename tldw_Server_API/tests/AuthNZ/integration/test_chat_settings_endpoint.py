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


def _create_character_and_chat(client, headers: dict[str, str]) -> str:
    create_character = client.post(
        "/api/v1/characters/",
        json={
            "name": "Settings Owner Character",
            "description": "For chat settings ownership tests",
            "personality": "Helpful",
            "first_message": "Hello!",
        },
        headers=headers,
    )
    assert create_character.status_code == 201, create_character.text
    character_id = create_character.json()["id"]

    create_chat = client.post(
        "/api/v1/chats/",
        json={"character_id": character_id, "title": "Owner settings chat"},
        headers=headers,
    )
    assert create_chat.status_code == 201, create_chat.text
    return create_chat.json()["id"]


def _valid_attachment() -> dict:
    return {
        "run_id": "run_123",
        "query": "Owner-scoped attachment",
        "question": "Owner-scoped attachment",
        "outline": [{"title": "Summary"}],
        "key_claims": [{"text": "Claim A"}],
        "unresolved_questions": ["What remains unclear?"],
        "verification_summary": {"unsupported_claim_count": 1},
        "source_trust_summary": {"high_trust_count": 1},
        "research_url": "/research?run=run_123",
        "attached_at": "2026-03-08T19:55:00Z",
        "updatedAt": "2026-03-08T20:00:00Z",
    }


def test_chat_settings_endpoint_enforces_chat_ownership(isolated_test_environment):
    client, _db_name = isolated_test_environment
    owner_headers = _register_and_login(
        client,
        username="settings_owner",
        email="settings_owner@example.com",
        password="Owner@Pass#2024!",
    )
    other_headers = _register_and_login(
        client,
        username="settings_other",
        email="settings_other@example.com",
        password="Other@Pass#2024!",
    )

    chat_id = _create_character_and_chat(client, owner_headers)

    owner_put = client.put(
        f"/api/v1/chats/{chat_id}/settings",
        headers=owner_headers,
        json={
            "settings": {
                "schemaVersion": 2,
                "updatedAt": "2026-03-08T20:00:00Z",
                "deepResearchAttachment": _valid_attachment(),
            }
        },
    )
    assert owner_put.status_code == 200, owner_put.text

    owner_get = client.get(f"/api/v1/chats/{chat_id}/settings", headers=owner_headers)
    assert owner_get.status_code == 200, owner_get.text

    other_get = client.get(f"/api/v1/chats/{chat_id}/settings", headers=other_headers)
    assert other_get.status_code == 404, other_get.text

    other_put = client.put(
        f"/api/v1/chats/{chat_id}/settings",
        headers=other_headers,
        json={
            "settings": {
                "schemaVersion": 2,
                "updatedAt": "2026-03-08T20:05:00Z",
                "deepResearchAttachment": _valid_attachment(),
            }
        },
    )
    assert other_put.status_code == 404, other_put.text
