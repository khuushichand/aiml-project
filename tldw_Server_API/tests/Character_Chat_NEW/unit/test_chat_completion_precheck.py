"""
Unit test to ensure completion pre-check uses efficient count instead of bulk-loading messages.
"""

import pytest
from typing import List, Dict, Any


@pytest.mark.unit
def test_completion_precheck_uses_count_not_bulk_get(test_client, auth_headers, character_db):
    # Create a character and a chat with a few messages
    char_resp = test_client.post(
        "/api/v1/characters/",
        json={
            "name": "CountCheck",
            "description": "",
            "personality": "",
            "first_message": "Hi"
        },
        headers=auth_headers,
    )
    assert char_resp.status_code == 201
    char_id = char_resp.json()["id"]

    chat_resp = test_client.post(
        "/api/v1/chats/",
        json={"character_id": char_id, "title": "Count Test"},
        headers=auth_headers,
    )
    assert chat_resp.status_code == 201
    chat_id = chat_resp.json()["id"]

    # Add a few messages
    for i in range(3):
        test_client.post(
            f"/api/v1/chats/{chat_id}/messages",
            json={"role": "user" if i % 2 == 0 else "assistant", "content": f"Msg {i}"},
            headers=auth_headers,
        )

    # Wrap DB methods to record usage
    original_count = character_db.count_messages_for_conversation
    original_get = character_db.get_messages_for_conversation

    calls: Dict[str, Any] = {"count_calls": 0, "get_limits": []}

    def count_wrapper(conversation_id: str) -> int:
        calls["count_calls"] += 1
        return original_count(conversation_id)

    def get_wrapper(conversation_id: str, limit: int = 100, offset: int = 0, **kwargs) -> List[Dict[str, Any]]:
        calls["get_limits"].append(limit)
        return original_get(conversation_id, limit=limit, offset=offset, **kwargs)

    character_db.count_messages_for_conversation = count_wrapper
    character_db.get_messages_for_conversation = get_wrapper

    # Trigger completion pre-check (offline sim path)
    resp = test_client.post(
        f"/api/v1/chats/{chat_id}/complete-v2",
        json={
            "provider": "local-llm",
            "model": "local-test",
            "append_user_message": "Check",
            "stream": False,
            "include_character_context": False,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Verify a count was used at least once and that no huge-limit fetch was used (10000)
    assert calls["count_calls"] >= 1
    assert 10000 not in calls["get_limits"], "Bulk get with 10000 limit should not be used for pre-check"
