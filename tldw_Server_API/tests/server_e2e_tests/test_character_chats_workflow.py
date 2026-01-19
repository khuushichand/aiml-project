import os
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
def test_character_chat_sessions_messages_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    character_name = f"E2E Character {suffix}"
    create_char_resp = page.request.post(
        "/api/v1/characters/",
        headers=headers,
        json={
            "name": character_name,
            "description": f"Character description {suffix}.",
            "first_message": f"Greetings from {suffix}.",
            "tags": [f"e2e-{suffix}"],
        },
    )
    _require_ok(create_char_resp, "create character")
    character = create_char_resp.json()
    character_id = character["id"]

    search_resp = page.request.get(
        "/api/v1/characters/search/",
        headers=headers,
        params={"query": character_name},
    )
    _require_ok(search_resp, "search characters")
    assert any(item.get("id") == character_id for item in search_resp.json())

    chat_resp = page.request.post(
        "/api/v1/chats/",
        headers=headers,
        json={
            "character_id": character_id,
            "title": f"E2E Chat {suffix}",
            "state": "in-progress",
        },
    )
    _require_ok(chat_resp, "create chat session")
    chat = chat_resp.json()
    chat_id = chat["id"]

    chat_get_resp = page.request.get(f"/api/v1/chats/{chat_id}", headers=headers)
    _require_ok(chat_get_resp, "get chat session")
    assert chat_get_resp.json()["id"] == chat_id

    list_resp = page.request.get(
        "/api/v1/chats",
        headers=headers,
        params={"character_id": character_id, "limit": 50, "offset": 0},
    )
    _require_ok(list_resp, "list chat sessions")
    list_payload = list_resp.json()
    assert any(item.get("id") == chat_id for item in list_payload.get("chats", []))

    context_resp = page.request.get(f"/api/v1/chats/{chat_id}/context", headers=headers)
    _require_ok(context_resp, "get chat context")
    context_payload = context_resp.json()
    assert context_payload.get("character_name") == character_name

    user_message = f"Hello from {suffix}."
    msg_resp = page.request.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
        json={"role": "user", "content": user_message},
    )
    _require_ok(msg_resp, "send user message")
    msg_payload = msg_resp.json()
    message_id = msg_payload["id"]
    message_version = msg_payload["version"]

    assistant_message = f"Acknowledged {suffix}."
    assistant_resp = page.request.post(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
        json={"role": "assistant", "content": assistant_message},
    )
    _require_ok(assistant_resp, "send assistant message")
    assistant_payload = assistant_resp.json()
    assistant_id = assistant_payload["id"]
    assistant_version = assistant_payload["version"]

    formatted_resp = page.request.get(
        f"/api/v1/chats/{chat_id}/messages",
        headers=headers,
        params={
            "format_for_completions": "true",
            "include_character_context": "true",
            "include_message_ids": "true",
        },
    )
    _require_ok(formatted_resp, "get formatted messages")
    formatted_payload = formatted_resp.json()
    assert formatted_payload.get("chat_id") == chat_id
    assert any(item.get("message_id") == message_id for item in formatted_payload.get("messages", []))

    search_resp = page.request.get(
        f"/api/v1/chats/{chat_id}/messages/search",
        headers=headers,
        params={"query": user_message.split()[0]},
    )
    _require_ok(search_resp, "search messages")
    search_payload = search_resp.json()
    assert any(item.get("id") == message_id for item in search_payload.get("messages", []))

    get_msg_resp = page.request.get(f"/api/v1/messages/{message_id}", headers=headers)
    _require_ok(get_msg_resp, "get message")
    assert get_msg_resp.json()["content"] == user_message

    updated_content = f"Updated {suffix} message."
    update_msg_resp = page.request.put(
        f"/api/v1/messages/{message_id}",
        headers=headers,
        params={"expected_version": message_version},
        json={"content": updated_content},
    )
    _require_ok(update_msg_resp, "update message")
    updated_payload = update_msg_resp.json()
    updated_version = updated_payload["version"]
    assert updated_payload["content"] == updated_content
    assert updated_version == message_version + 1

    delete_msg_resp = page.request.delete(
        f"/api/v1/messages/{assistant_id}",
        headers=headers,
        params={"expected_version": assistant_version},
    )
    assert delete_msg_resp.status == 204

    refreshed_chat_resp = page.request.get(f"/api/v1/chats/{chat_id}", headers=headers)
    _require_ok(refreshed_chat_resp, "refresh chat session")
    refreshed_chat = refreshed_chat_resp.json()
    chat_version = refreshed_chat["version"]

    update_chat_resp = page.request.put(
        f"/api/v1/chats/{chat_id}",
        headers=headers,
        params={"expected_version": chat_version},
        json={"title": f"E2E Chat Updated {suffix}", "rating": 5, "state": "resolved"},
    )
    _require_ok(update_chat_resp, "update chat session")
    updated_chat = update_chat_resp.json()
    assert updated_chat["title"].startswith("E2E Chat Updated")
    chat_version = updated_chat["version"]

    export_resp = page.request.get(
        f"/api/v1/chats/{chat_id}/export",
        headers=headers,
        params={"format": "json", "include_metadata": "true", "include_character": "true"},
    )
    _require_ok(export_resp, "export chat")
    export_payload = export_resp.json()
    assert export_payload.get("chat_id") == chat_id
    assert any(item.get("content") == updated_content for item in export_payload.get("messages", []))

    delete_chat_resp = page.request.delete(
        f"/api/v1/chats/{chat_id}",
        headers=headers,
        params={"expected_version": chat_version},
    )
    assert delete_chat_resp.status == 204

    character_fresh_resp = page.request.get(f"/api/v1/characters/{character_id}", headers=headers)
    _require_ok(character_fresh_resp, "get character for delete")
    character_version = character_fresh_resp.json()["version"]

    delete_char_resp = page.request.delete(
        f"/api/v1/characters/{character_id}",
        headers=headers,
        params={"expected_version": character_version},
    )
    _require_ok(delete_char_resp, "delete character")
