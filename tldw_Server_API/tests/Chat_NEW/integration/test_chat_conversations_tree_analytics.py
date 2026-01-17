from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import status

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.mark.integration
def test_conversation_tree_pagination_and_truncation(
    test_client,
    chacha_db: CharactersRAGDB,
    auth_headers,
):
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    character_id = chacha_db.add_character_card(
        {
            "name": "Tree Character",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "1",
        }
    )
    conversation_id = chacha_db.add_conversation(
        {
            "character_id": character_id,
            "title": "Tree Conversation",
            "client_id": "1",
        }
    )

    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    root_1 = chacha_db.add_message(
        {
            "conversation_id": conversation_id,
            "sender": "user",
            "content": "Root 1",
            "client_id": "1",
            "timestamp": base_time.isoformat(),
        }
    )
    child_1 = chacha_db.add_message(
        {
            "conversation_id": conversation_id,
            "parent_message_id": root_1,
            "sender": "assistant",
            "content": "Child 1",
            "client_id": "1",
            "timestamp": (base_time + timedelta(minutes=1)).isoformat(),
        }
    )
    chacha_db.add_message(
        {
            "conversation_id": conversation_id,
            "parent_message_id": child_1,
            "sender": "user",
            "content": "Grandchild",
            "client_id": "1",
            "timestamp": (base_time + timedelta(minutes=2)).isoformat(),
        }
    )
    root_2 = chacha_db.add_message(
        {
            "conversation_id": conversation_id,
            "sender": "user",
            "content": "Root 2",
            "client_id": "1",
            "timestamp": (base_time + timedelta(hours=1)).isoformat(),
        }
    )
    assert root_1 and root_2

    def override_get_db():
        return chacha_db

    test_client.app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    try:
        resp = test_client.get(
            f"/api/v1/chat/conversations/{conversation_id}/tree",
            params={"limit": 1, "offset": 0, "max_depth": 1},
            headers=auth_headers,
        )

        assert resp.status_code == status.HTTP_200_OK, resp.text
        data = resp.json()
        assert data["pagination"]["total_root_threads"] == 2
        assert data["pagination"]["has_more"] is True
        assert data["depth_cap"] == 1
        assert len(data["root_threads"]) == 1
        root = data["root_threads"][0]
        assert root["id"] == root_1
        assert root["truncated"] is True
        assert root["children"] == []
    finally:
        test_client.app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.integration
def test_chat_analytics_pagination_edges(
    test_client,
    chacha_db: CharactersRAGDB,
    auth_headers,
):
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    character_id = chacha_db.add_character_card(
        {
            "name": "Analytics Character",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "1",
        }
    )
    conv_a = chacha_db.add_conversation(
        {
            "character_id": character_id,
            "title": "Analytics A",
            "state": "in-progress",
            "client_id": "1",
        }
    )
    conv_b = chacha_db.add_conversation(
        {
            "character_id": character_id,
            "title": "Analytics B",
            "state": "in-progress",
            "client_id": "1",
        }
    )

    day_one = datetime.now(timezone.utc) - timedelta(days=2)
    day_two = datetime.now(timezone.utc) - timedelta(days=1)
    chacha_db.execute_query(
        "UPDATE conversations SET last_modified = ? WHERE id = ?",
        (day_one.isoformat(), conv_a),
        commit=True,
    )
    chacha_db.execute_query(
        "UPDATE conversations SET last_modified = ? WHERE id = ?",
        (day_two.isoformat(), conv_b),
        commit=True,
    )

    def override_get_db():
        return chacha_db

    test_client.app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    try:
        start_date = (day_one - timedelta(days=1)).date().isoformat()
        end_date = (day_two + timedelta(days=1)).date().isoformat()
        params = {
            "start_date": start_date,
            "end_date": end_date,
            "bucket_granularity": "day",
            "limit": 1,
            "offset": 0,
        }
        resp = test_client.get("/api/v1/chat/analytics", params=params, headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK, resp.text
        data = resp.json()
        assert data["pagination"]["total"] >= 2
        assert data["pagination"]["has_more"] is True

        params["offset"] = 1
        resp_page_2 = test_client.get("/api/v1/chat/analytics", params=params, headers=auth_headers)
        assert resp_page_2.status_code == status.HTTP_200_OK, resp_page_2.text
        data_page_2 = resp_page_2.json()
        assert data_page_2["pagination"]["offset"] == 1
    finally:
        test_client.app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.integration
def test_conversation_tree_respects_message_cap(
    test_client,
    chacha_db: CharactersRAGDB,
    auth_headers,
    monkeypatch,
):
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
    from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint

    monkeypatch.setattr(chat_endpoint, "TREE_MESSAGE_CAP_DEFAULT", 3)
    monkeypatch.setattr(chat_endpoint, "TREE_MESSAGE_CAP_MAX", 3)

    character_id = chacha_db.add_character_card(
        {
            "name": "Cap Character",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "1",
        }
    )
    conversation_id = chacha_db.add_conversation(
        {
            "character_id": character_id,
            "title": "Cap Conversation",
            "client_id": "1",
        }
    )

    root_id = chacha_db.add_message(
        {
            "conversation_id": conversation_id,
            "sender": "user",
            "content": "Root",
            "client_id": "1",
        }
    )
    for idx in range(5):
        chacha_db.add_message(
            {
                "conversation_id": conversation_id,
                "parent_message_id": root_id,
                "sender": "assistant",
                "content": f"Child {idx}",
                "client_id": "1",
            }
        )

    def override_get_db():
        return chacha_db

    test_client.app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    try:
        resp = test_client.get(
            f"/api/v1/chat/conversations/{conversation_id}/tree",
            params={"limit": 1, "offset": 0, "max_depth": 10},
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_200_OK, resp.text
        data = resp.json()
        assert len(data["root_threads"]) == 1
        root = data["root_threads"][0]
        assert root["truncated"] is True
        assert len(root["children"]) <= 2
    finally:
        test_client.app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.integration
def test_chat_analytics_range_limit(
    test_client,
    chacha_db: CharactersRAGDB,
    auth_headers,
):
    from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user

    character_id = chacha_db.add_character_card(
        {
            "name": "Range Character",
            "description": "desc",
            "personality": "helpful",
            "system_prompt": "You are helpful.",
            "client_id": "1",
        }
    )
    chacha_db.add_conversation(
        {
            "character_id": character_id,
            "title": "Range Conversation",
            "state": "in-progress",
            "client_id": "1",
        }
    )

    def override_get_db():
        return chacha_db

    test_client.app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    try:
        start_date = (datetime.now(timezone.utc) - timedelta(days=190)).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()
        resp = test_client.get(
            "/api/v1/chat/analytics",
            params={"start_date": start_date, "end_date": end_date, "bucket_granularity": "day"},
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.text
    finally:
        test_client.app.dependency_overrides.pop(get_chacha_db_for_user, None)
