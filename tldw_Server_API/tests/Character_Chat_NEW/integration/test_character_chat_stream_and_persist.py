"""
Integration tests for streaming stub (offline-sim) and persist endpoint.
"""

from datetime import datetime, timezone

import pytest
pytestmark = pytest.mark.integration
from fastapi.testclient import TestClient


def _create_character_and_chat(client: TestClient, headers):
    char_resp = client.post(
        "/api/v1/characters/",
        json={
            "name": "StreamChar",
            "description": "Streaming test",
            "personality": "Calm",
            "first_message": "Hello!"
        },
        headers=headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["id"]
    chat_resp = client.post(
        "/api/v1/chats/",
        json={"character_id": char_id, "title": "Streaming Chat"},
        headers=headers,
    )
    assert chat_resp.status_code == 201
    return char_id, chat_resp.json()["id"]


def test_offline_streaming_and_persist_flow(test_client: TestClient, auth_headers):
    # Ensure offline-sim mode by not enabling any ENABLE_LOCAL_LLM_PROVIDER, etc.
    char_id, chat_id = _create_character_and_chat(test_client, auth_headers)

    # Request a streamed completion with an appended user message
    user_prompt = "This is a streamed test"
    with test_client.stream(
        "POST",
        f"/api/v1/chats/{chat_id}/complete-v2",
        json={
            "provider": "local-llm",
            "model": "local-test",
            "append_user_message": user_prompt,
            "stream": True,
            "include_character_context": False,
        },
        headers=auth_headers,
    ) as resp:
        assert resp.status_code == 200
        # Collect lines; expect at least one data line and a final [DONE]
        body = resp.iter_lines()
        lines = []
        for line in body:
            if not line:
                continue
            try:
                s = line.decode() if isinstance(line, (bytes, bytearray)) else str(line)
            except Exception:
                s = str(line)
            lines.append(s)
            if s.strip().lower() == "data: [done]":
                break

        assert any(l.startswith("data: ") for l in lines), "Expected SSE data lines"
        assert any(l.strip().lower() == "data: [done]" for l in lines), "Expected final [DONE]"
        # Combined payload should contain the user prompt content (echo behavior)
        combined = "\n".join(lines)
        assert user_prompt in combined

    # Persist the assistant content after streaming
    persist_resp = test_client.post(
        f"/api/v1/chats/{chat_id}/completions/persist",
        json={
            "assistant_content": user_prompt,
            "user_message_id": None,
        },
        headers=auth_headers,
    )
    assert persist_resp.status_code == 200
    data = persist_resp.json()
    assert data.get("saved") is True
    assert data.get("assistant_message_id")

    # Verify message was persisted
    messages_resp = test_client.get(
        f"/api/v1/chats/{chat_id}/messages",
        headers=auth_headers,
    )
    assert messages_resp.status_code == 200
    msgs = messages_resp.json().get("messages")
    assert any(m.get("content") == user_prompt and m.get("sender") == "StreamChar" for m in msgs)


def test_persist_streamed_message_preserves_active_speaker_identity(test_client: TestClient, auth_headers):
    """Persist endpoint should allow preserving the directed/active character speaker."""
    # Primary character + chat
    char_resp = test_client.post(
        "/api/v1/characters/",
        json={
            "name": "PrimarySpeaker",
            "description": "Primary character",
            "personality": "Calm",
            "first_message": "Hello!",
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    primary = char_resp.json()
    primary_id = primary["id"]

    # Secondary character participant
    secondary_resp = test_client.post(
        "/api/v1/characters/",
        json={
            "name": "SecondarySpeaker",
            "description": "Secondary character",
            "personality": "Assertive",
            "first_message": "Hi!",
        },
        headers=auth_headers,
    )
    assert secondary_resp.status_code == 201
    secondary = secondary_resp.json()
    secondary_id = secondary["id"]
    secondary_name = secondary["name"]

    chat_resp = test_client.post(
        "/api/v1/chats/",
        json={"character_id": primary_id, "title": "Persist Speaker Identity"},
        headers=auth_headers,
    )
    assert chat_resp.status_code == 201
    chat_id = chat_resp.json()["id"]

    # Enable round-robin participant context
    settings_resp = test_client.put(
        f"/api/v1/chats/{chat_id}/settings",
        json={
            "settings": {
                "schemaVersion": 2,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "turnTakingMode": "round_robin",
                "participantCharacterIds": [secondary_id],
            }
        },
        headers=auth_headers,
    )
    assert settings_resp.status_code == 200

    # Dry-run a directed turn to confirm active speaker resolution points at secondary
    directed_resp = test_client.post(
        f"/api/v1/chats/{chat_id}/complete-v2",
        json={
            "provider": "local-llm",
            "model": "local-test",
            "append_user_message": "direct this to secondary",
            "save_to_db": False,
            "directed_character_id": secondary_id,
        },
        headers=auth_headers,
    )
    assert directed_resp.status_code == 200
    directed_payload = directed_resp.json()
    assert directed_payload.get("speaker_character_id") == secondary_id
    assert directed_payload.get("speaker_character_name") == secondary_name

    # Persist streamed text and request secondary as speaker identity.
    # Current API ignores these speaker fields, causing persistence under primary sender.
    persist_resp = test_client.post(
        f"/api/v1/chats/{chat_id}/completions/persist",
        json={
            "assistant_content": "secondary streamed response",
            "speaker_character_id": secondary_id,
            "speaker_character_name": secondary_name,
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        },
        headers=auth_headers,
    )
    assert persist_resp.status_code == 200
    persisted = persist_resp.json()
    assistant_message_id = persisted.get("assistant_message_id")
    assert assistant_message_id

    # The persisted sender should match the requested active speaker.
    messages_resp = test_client.get(f"/api/v1/chats/{chat_id}/messages", headers=auth_headers)
    assert messages_resp.status_code == 200
    messages = messages_resp.json().get("messages") or []
    persisted_msg = next((m for m in messages if m.get("id") == assistant_message_id), None)
    assert persisted_msg is not None
    assert persisted_msg.get("sender") == secondary_name

    message_resp = test_client.get(
        f"/api/v1/messages/{assistant_message_id}",
        params={"include_metadata": "true"},
        headers=auth_headers,
    )
    assert message_resp.status_code == 200
    metadata_extra = message_resp.json().get("metadata_extra") or {}
    assert metadata_extra.get("speaker_character_id") == secondary_id
    assert metadata_extra.get("speaker_character_name") == secondary_name
    assert metadata_extra.get("turn_taking_mode") == "round_robin"
    assert metadata_extra.get("usage") == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }


def test_persist_streamed_message_requires_request_body(test_client: TestClient, auth_headers):
    """Persist endpoint should return 422 when request body is missing."""
    _, chat_id = _create_character_and_chat(test_client, auth_headers)

    response = test_client.post(
        f"/api/v1/chats/{chat_id}/completions/persist",
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_persist_streamed_message_rejects_empty_assistant_content(test_client: TestClient, auth_headers):
    """Persist endpoint should reject empty assistant_content with 422."""
    _, chat_id = _create_character_and_chat(test_client, auth_headers)

    response = test_client.post(
        f"/api/v1/chats/{chat_id}/completions/persist",
        json={"assistant_content": ""},
        headers=auth_headers,
    )

    assert response.status_code == 422
