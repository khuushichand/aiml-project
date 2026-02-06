from datetime import datetime, timezone

import pytest
from fastapi import FastAPI

from tldw_Server_API.app.api.v1.endpoints import character_chat_sessions as sessions


@pytest.mark.unit
def test_merge_conversation_settings_server_wins_on_equal_updated_at():
    server = {
        "schemaVersion": 2,
        "updatedAt": "2026-02-06T00:00:00Z",
        "authorNote": "server-note",
        "memoryScope": "shared",
    }
    incoming = {
        "schemaVersion": 2,
        "updatedAt": "2026-02-06T00:00:00Z",
        "authorNote": "incoming-note",
        "memoryScope": "both",
    }

    merged = sessions._merge_conversation_settings(server, incoming)

    assert merged["authorNote"] == "server-note"
    assert merged["memoryScope"] == "shared"
    assert merged["updatedAt"] == "2026-02-06T00:00:00Z"


@pytest.mark.unit
def test_merge_conversation_settings_incoming_wins_when_newer():
    server = {
        "schemaVersion": 2,
        "updatedAt": "2026-02-06T00:00:00Z",
        "greetingEnabled": True,
    }
    incoming = {
        "updatedAt": "2026-02-06T00:00:01Z",
        "greetingEnabled": False,
    }

    merged = sessions._merge_conversation_settings(server, incoming)

    assert merged["greetingEnabled"] is False
    assert merged["updatedAt"] == "2026-02-06T00:00:01Z"
    assert merged["schemaVersion"] == 2


@pytest.mark.unit
def test_merge_conversation_settings_character_memory_per_entry_timestamp():
    server = {
        "schemaVersion": 2,
        "updatedAt": "2026-02-06T00:00:00Z",
        "characterMemoryById": {
            "1": {"note": "server-primary", "updatedAt": "2026-02-06T00:00:00Z"},
            "2": {"note": "server-secondary", "updatedAt": "2026-02-06T00:00:00Z"},
        },
    }
    incoming = {
        "schemaVersion": 2,
        "updatedAt": "2026-02-06T00:00:00Z",
        "characterMemoryById": {
            "1": {"note": "incoming-primary-older", "updatedAt": "2026-02-05T23:59:59Z"},
            "2": {"note": "incoming-secondary-newer", "updatedAt": "2026-02-06T00:00:01Z"},
            "3": {"note": "incoming-third", "updatedAt": "2026-02-06T00:00:01Z"},
        },
    }

    merged = sessions._merge_conversation_settings(server, incoming)
    memory = merged["characterMemoryById"]

    assert memory["1"]["note"] == "server-primary"
    assert memory["2"]["note"] == "incoming-secondary-newer"
    assert memory["3"]["note"] == "incoming-third"


@pytest.mark.unit
def test_merge_conversation_settings_preserves_unknown_keys():
    server = {
        "schemaVersion": 2,
        "updatedAt": "2026-02-06T00:00:00Z",
        "serverCustomFlag": "keep-me",
    }
    incoming = {
        "updatedAt": "2026-02-06T00:00:10Z",
        "clientCustomBlock": {"a": 1},
    }

    merged = sessions._merge_conversation_settings(server, incoming)

    assert merged["serverCustomFlag"] == "keep-me"
    assert merged["clientCustomBlock"] == {"a": 1}
    assert merged["schemaVersion"] == 2


@pytest.mark.unit
def test_convert_db_conversation_to_response_includes_settings_payload():
    conv = {
        "id": "chat-1",
        "character_id": 7,
        "created_at": datetime.now(timezone.utc),
        "last_modified": datetime.now(timezone.utc),
        "version": 3,
        "message_count": 12,
    }
    settings = {"greetingEnabled": True, "authorNote": "test"}

    response = sessions._convert_db_conversation_to_response(conv, settings=settings)

    assert response.id == "chat-1"
    assert response.settings == settings


@pytest.mark.unit
def test_convert_db_conversation_to_response_defaults_settings_none():
    conv = {
        "id": "chat-2",
        "character_id": 9,
        "created_at": datetime.now(timezone.utc),
        "last_modified": datetime.now(timezone.utc),
        "version": 1,
    }

    response = sessions._convert_db_conversation_to_response(conv)

    assert response.id == "chat-2"
    assert response.settings is None


@pytest.mark.unit
def test_openapi_exposes_include_settings_query_params():
    app = FastAPI()
    app.include_router(sessions.router, prefix="/api/v1/chats")
    schema = app.openapi()

    detail_params = schema["paths"]["/api/v1/chats/{chat_id}"]["get"]["parameters"]
    detail_param_names = {param["name"] for param in detail_params}
    assert "include_settings" in detail_param_names

    list_params = schema["paths"]["/api/v1/chats/"]["get"]["parameters"]
    list_param_names = {param["name"] for param in list_params}
    assert "include_settings" in list_param_names
