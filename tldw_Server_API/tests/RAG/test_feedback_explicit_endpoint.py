from __future__ import annotations

import json

import pytest
from fastapi import status

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


def _row_to_dict(row, cursor):
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        columns = [col[0] for col in cursor.description] if cursor.description else []
        return {columns[idx]: row[idx] for idx in range(len(columns))}


@pytest.fixture()
def feedback_setup(tmp_path, client_user_only):
    db = CharactersRAGDB(
        db_path=str(tmp_path / "feedback_chacha.db"),
        client_id="1",
    )
    character_id = db.add_character_card(
        {
            "name": "Feedback Assistant",
            "description": "Test assistant",
            "personality": "Helpful",
            "system_prompt": "Be helpful.",
            "client_id": "1",
        }
    )
    conversation_id = db.add_conversation(
        {
            "character_id": character_id,
            "title": "Feedback Conversation",
            "client_id": "1",
        }
    )
    message_id = db.add_message(
        {
            "conversation_id": conversation_id,
            "sender": "assistant",
            "content": "Derived from message content",
            "client_id": "1",
        }
    )

    client_user_only.app.dependency_overrides[get_chacha_db_for_user] = lambda: db
    client_user_only.app.dependency_overrides[check_rate_limit] = lambda: None

    try:
        yield client_user_only, db, conversation_id, message_id
    finally:
        client_user_only.app.dependency_overrides.pop(get_chacha_db_for_user, None)
        client_user_only.app.dependency_overrides.pop(check_rate_limit, None)


@pytest.mark.integration
def test_explicit_feedback_derives_query_from_message(feedback_setup):
    client, db, conversation_id, message_id = feedback_setup

    payload = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "feedback_type": "helpful",
        "helpful": True,
    }

    resp = client.post("/api/v1/feedback/explicit", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["ok"] is True
    assert data["feedback_id"]

    cursor = db.execute_query(
        "SELECT query FROM conversation_feedback WHERE id = ?",
        (data["feedback_id"],),
    )
    row = cursor.fetchone()
    assert row is not None
    record = _row_to_dict(row, cursor)
    assert record["query"] == "Derived from message content"


@pytest.mark.integration
def test_explicit_feedback_idempotent_merge_updates_issues_and_notes(feedback_setup):
    client, db, conversation_id, message_id = feedback_setup

    payload = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "feedback_type": "helpful",
        "helpful": False,
        "issues": ["missing_details"],
        "user_notes": "Initial notes",
    }

    resp = client.post("/api/v1/feedback/explicit", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    feedback_id = resp.json()["feedback_id"]

    payload_update = {
        "conversation_id": conversation_id,
        "message_id": message_id,
        "feedback_type": "helpful",
        "helpful": False,
        "issues": ["incorrect_information"],
        "user_notes": "Updated notes",
    }

    resp_update = client.post("/api/v1/feedback/explicit", json=payload_update)
    assert resp_update.status_code == status.HTTP_200_OK
    assert resp_update.json()["feedback_id"] == feedback_id

    cursor = db.execute_query(
        "SELECT issues, user_notes FROM conversation_feedback WHERE id = ?",
        (feedback_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    record = _row_to_dict(row, cursor)
    issues = json.loads(record["issues"]) if record.get("issues") else []
    assert set(issues) == {"missing_details", "incorrect_information"}
    assert record["user_notes"] == "Updated notes"

    cursor = db.execute_query(
        "SELECT COUNT(*) AS count FROM conversation_feedback WHERE conversation_id = ?",
        (conversation_id,),
    )
    count_row = cursor.fetchone()
    assert count_row is not None
    count_record = _row_to_dict(count_row, cursor)
    assert count_record["count"] == 1


@pytest.mark.integration
def test_explicit_feedback_rag_only_accepts_query(feedback_setup):
    client, db, _conversation_id, _message_id = feedback_setup

    payload = {
        "feedback_type": "relevance",
        "relevance_score": 4,
        "query": "How do I reset auth?",
    }

    resp = client.post("/api/v1/feedback/explicit", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["ok"] is True
    assert data["feedback_id"] is None
