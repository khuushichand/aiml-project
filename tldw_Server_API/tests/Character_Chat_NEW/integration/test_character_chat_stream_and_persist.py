"""
Integration tests for streaming stub (offline-sim) and persist endpoint.
"""

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
    assert any(m.get("content") == user_prompt and m.get("sender") == "assistant" for m in msgs)
