from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import (
    DEFAULT_CHARACTER_NAME,
    get_chacha_db_for_user,
)
from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.Chat.prompt_template_manager import DEFAULT_RAW_PASSTHROUGH_TEMPLATE
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


pytestmark = pytest.mark.integration


@pytest.fixture
def persona_chat_db(tmp_path, monkeypatch) -> CharactersRAGDB:
    user_db_root = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(user_db_root))

    db_path = DatabasePaths.get_chacha_db_path(1)
    db = CharactersRAGDB(str(db_path), client_id="1")
    db.add_character_card(
        {
            "name": DEFAULT_CHARACTER_NAME,
            "description": "Default assistant for tests",
            "personality": "Helpful",
            "scenario": "Testing",
            "system_prompt": "You are a helpful AI assistant.",
            "first_message": "Hello",
            "creator_notes": "Default test character",
        }
    )
    db.add_character_card(
        {
            "name": "Source Character",
            "description": "Source persona character",
            "personality": "Specific",
            "scenario": "Testing",
            "system_prompt": "You are the source character.",
            "first_message": "Source hello",
            "creator_notes": "Source test character",
        }
    )
    yield db
    db.close_connection()


@pytest.fixture
def persona_chat_client(persona_chat_db):
    test_user = User(id=1, username="test_user", email="test@example.com", is_active=True)

    async def mock_get_request_user(api_key=None, token=None):
        return test_user

    auth_headers: dict[str, str] | None = None
    mock_response = {
        "id": "chatcmpl-persona",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Persona reply from test"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with (
        patch.dict("tldw_Server_API.app.api.v1.endpoints.chat.API_KEYS", {"openai": "sk-test-key"}),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call",
            return_value=mock_response,
        ) as perform_chat_api_call,
        patch(
            "tldw_Server_API.app.core.Chat.chat_service.load_template",
            return_value=DEFAULT_RAW_PASSTHROUGH_TEMPLATE,
        ),
        patch(
            "tldw_Server_API.app.api.v1.endpoints.chat.is_authentication_required",
            return_value=False,
        ),
    ):
        app.dependency_overrides[get_chacha_db_for_user] = lambda: persona_chat_db
        app.dependency_overrides[get_media_db_for_user] = lambda: object()
        app.dependency_overrides[get_request_user] = mock_get_request_user
        with TestClient(app) as client:
            response = client.get("/api/v1/health")
            csrf_token = response.cookies.get("csrf_token", "")
            auth_headers = {"X-API-KEY": "test-api-key-12345", "X-CSRF-Token": csrf_token}
            yield client, auth_headers, perform_chat_api_call

    app.dependency_overrides.pop(get_chacha_db_for_user, None)
    app.dependency_overrides.pop(get_media_db_for_user, None)
    app.dependency_overrides.pop(get_request_user, None)


def _enable_persona_memory(*, user_id: str) -> None:
    personalization_path = DatabasePaths.get_personalization_db_path(int(user_id))
    db = PersonalizationDB(str(personalization_path))
    db.update_profile(user_id, enabled=1)


def _create_persona_conversation(
    db: CharactersRAGDB,
    *,
    persona_id: str,
    persona_name: str = "Garden Helper",
    system_prompt: str = "You are Garden Helper.",
    persona_memory_mode: str = "read_only",
) -> tuple[str, int]:
    source_character = db.get_character_card_by_name("Source Character")
    assert source_character is not None
    source_character_id = int(source_character["id"])
    db.create_persona_profile(
        {
            "id": persona_id,
            "user_id": "1",
            "name": persona_name,
            "character_card_id": source_character_id,
            "mode": "session_scoped",
            "system_prompt": system_prompt,
            "is_active": True,
        }
    )
    conversation_id = db.add_conversation(
        {
            "assistant_kind": "persona",
            "assistant_id": persona_id,
            "persona_memory_mode": persona_memory_mode,
            "title": f"{persona_name} chat",
            "client_id": "1",
        }
    )
    assert conversation_id is not None
    return conversation_id, source_character_id


def _chat_completion_body(conversation_id: str) -> dict[str, object]:
    return {
        "model": "gpt-4",
        "api_provider": "openai",
        "conversation_id": conversation_id,
        "save_to_db": True,
        "messages": [{"role": "user", "content": "Remember this and reply."}],
    }


def test_persona_backed_chat_uses_persona_identity_when_loading_prompt(
    persona_chat_client,
    persona_chat_db,
):
    client, auth_headers, perform_chat_api_call = persona_chat_client
    conversation_id, _ = _create_persona_conversation(
        persona_chat_db,
        persona_id="garden-helper",
        system_prompt="You are the Persona Garden assistant.",
    )

    response = client.post(
        "/api/v1/chat/completions",
        json=_chat_completion_body(conversation_id),
        headers=auth_headers,
    )

    assert response.status_code == 200
    called_kwargs = perform_chat_api_call.call_args.kwargs
    assert called_kwargs["system_message"] == "You are the Persona Garden assistant."
    assert called_kwargs["messages_payload"][-1]["role"] == "user"


def test_persona_memory_mode_read_only_does_not_write_memory(
    persona_chat_client,
    persona_chat_db,
    monkeypatch,
):
    from tldw_Server_API.app.core.Persona import memory_integration as mem

    client, auth_headers, _ = persona_chat_client
    monkeypatch.setattr(mem, "_get_persona_memory_write_mode", lambda: "chacha_only")
    _enable_persona_memory(user_id="1")
    conversation_id, _ = _create_persona_conversation(
        persona_chat_db,
        persona_id="garden-read-only",
        persona_memory_mode="read_only",
    )

    response = client.post(
        "/api/v1/chat/completions",
        json=_chat_completion_body(conversation_id),
        headers=auth_headers,
    )

    assert response.status_code == 200
    memories = persona_chat_db.list_persona_memory_entries(
        user_id="1",
        persona_id="garden-read-only",
        include_archived=True,
        include_deleted=True,
        limit=50,
        offset=0,
    )
    assert memories == []


def test_persona_memory_mode_read_write_allows_memory_write(
    persona_chat_client,
    persona_chat_db,
    monkeypatch,
):
    from tldw_Server_API.app.core.Persona import memory_integration as mem

    client, auth_headers, _ = persona_chat_client
    monkeypatch.setattr(mem, "_get_persona_memory_write_mode", lambda: "chacha_only")
    _enable_persona_memory(user_id="1")
    conversation_id, _ = _create_persona_conversation(
        persona_chat_db,
        persona_id="garden-read-write",
        persona_memory_mode="read_write",
    )

    response = client.post(
        "/api/v1/chat/completions",
        json=_chat_completion_body(conversation_id),
        headers=auth_headers,
    )

    assert response.status_code == 200
    memories = persona_chat_db.list_persona_memory_entries(
        user_id="1",
        persona_id="garden-read-write",
        include_archived=True,
        include_deleted=True,
        limit=50,
        offset=0,
    )
    summary_entries = [entry for entry in memories if entry.get("memory_type") == "summary"]
    usage_entries = [entry for entry in memories if entry.get("memory_type") == "usage_event"]
    assert len(summary_entries) == 1
    assert summary_entries[0]["content"] == "Persona reply from test"
    assert len(usage_entries) == 1


def test_persona_backed_chat_uses_projection_fallbacks_without_source_character_dependency(
    persona_chat_client,
    persona_chat_db,
):
    client, auth_headers, perform_chat_api_call = persona_chat_client
    conversation_id, source_character_id = _create_persona_conversation(
        persona_chat_db,
        persona_id="garden-independent",
        persona_name="Independent Persona",
        system_prompt="You are independent now.",
    )
    source_character = persona_chat_db.get_character_card_by_id(source_character_id)
    assert source_character is not None
    deleted = persona_chat_db.soft_delete_character_card(
        source_character_id,
        expected_version=int(source_character["version"]),
    )
    assert deleted is True

    response = client.post(
        "/api/v1/chat/completions",
        json=_chat_completion_body(conversation_id),
        headers=auth_headers,
    )

    assert response.status_code == 200
    called_kwargs = perform_chat_api_call.call_args.kwargs
    assert called_kwargs["system_message"] == "You are independent now."
    assert response.json()["choices"][0]["message"]["name"] == "Independent_Persona"
