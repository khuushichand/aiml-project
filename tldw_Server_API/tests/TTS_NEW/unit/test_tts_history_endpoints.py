import pytest
from fastapi import Depends, Request, status

from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.TTS.utils import compute_tts_history_text_hash
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.main import app


pytestmark = [pytest.mark.unit]


def _override_media_db(db: MediaDatabase):
    async def _override(request: Request, current_user: User = Depends(get_request_user)):
        yield db
    return _override


def test_history_list_favorite_delete(test_client, auth_headers):
    db = MediaDatabase(db_path=":memory:", client_id="tts_history_test")
    entry_one = db.create_tts_history_entry(
        user_id="1",
        text_hash="hash_one",
        text="Hello world",
        text_length=11,
        provider="openai",
        model="tts-1",
        voice_name="alloy",
        format="mp3",
        status="success",
        favorite=False,
    )
    entry_two = db.create_tts_history_entry(
        user_id="1",
        text_hash="hash_two",
        text="Another entry",
        text_length=13,
        provider="openai",
        model="tts-1",
        voice_name="alloy",
        format="mp3",
        status="success",
        favorite=True,
    )

    app.dependency_overrides[get_media_db_for_user] = _override_media_db(db)
    try:
        resp = test_client.get("/api/v1/audio/history?favorite=true", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert len(payload["items"]) == 1
        assert payload["items"][0]["id"] == entry_two

        resp = test_client.patch(
            f"/api/v1/audio/history/{entry_one}",
            json={"favorite": True},
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_200_OK

        resp = test_client.get("/api/v1/audio/history?favorite=true", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        ids = {item["id"] for item in payload["items"]}
        assert entry_one in ids
        assert entry_two in ids

        resp = test_client.delete(f"/api/v1/audio/history/{entry_two}", headers=auth_headers)
        assert resp.status_code == status.HTTP_204_NO_CONTENT

        resp = test_client.get("/api/v1/audio/history", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        ids = {item["id"] for item in payload["items"]}
        assert entry_two not in ids
    finally:
        app.dependency_overrides.pop(get_media_db_for_user, None)
        db.close_connection()


def test_history_q_rejected_when_text_disabled(test_client, auth_headers, monkeypatch):
    db = MediaDatabase(db_path=":memory:", client_id="tts_history_q")
    app.dependency_overrides[get_media_db_for_user] = _override_media_db(db)
    monkeypatch.setattr(settings, "TTS_HISTORY_STORE_TEXT", False, raising=False)
    try:
        resp = test_client.get("/api/v1/audio/history?q=hello", headers=auth_headers)
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
    finally:
        app.dependency_overrides.pop(get_media_db_for_user, None)
        db.close_connection()


def test_history_text_exact_search(test_client, auth_headers, monkeypatch):
    db = MediaDatabase(db_path=":memory:", client_id="tts_history_text_exact")
    monkeypatch.setattr(settings, "TTS_HISTORY_STORE_TEXT", False, raising=False)
    monkeypatch.setattr(settings, "TTS_HISTORY_HASH_KEY", "test-history-key", raising=False)

    text_value = "Exact Match"
    text_hash = compute_tts_history_text_hash(text_value, "test-history-key")
    db.create_tts_history_entry(
        user_id="1",
        text_hash=text_hash,
        text=None,
        text_length=len(text_value),
        status="success",
    )

    app.dependency_overrides[get_media_db_for_user] = _override_media_db(db)
    try:
        resp = test_client.get(f"/api/v1/audio/history?text_exact={text_value}", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert len(payload["items"]) == 1
        assert payload["items"][0]["has_text"] is False
    finally:
        app.dependency_overrides.pop(get_media_db_for_user, None)
        db.close_connection()


def test_history_voice_id_and_voice_name_filters(test_client, auth_headers):
    db = MediaDatabase(db_path=":memory:", client_id="tts_history_voice_filters")
    first_id = db.create_tts_history_entry(
        user_id="1",
        text_hash="voice_hash_1",
        text="OpenAI Alloy",
        text_length=12,
        provider="openai",
        model="tts-1",
        voice_id="alloy",
        voice_name="Alloy",
        status="success",
    )
    second_id = db.create_tts_history_entry(
        user_id="1",
        text_hash="voice_hash_2",
        text="ElevenLabs Rachel",
        text_length=17,
        provider="elevenlabs",
        model="eleven_multilingual_v2",
        voice_id="rachel_v2",
        voice_name="Rachel",
        status="success",
    )
    db.create_tts_history_entry(
        user_id="1",
        text_hash="voice_hash_3",
        text="Custom voice",
        text_length=12,
        provider="openai",
        model="tts-1",
        voice_id="custom_demo",
        voice_name="Demo Voice",
        status="success",
    )

    app.dependency_overrides[get_media_db_for_user] = _override_media_db(db)
    try:
        resp = test_client.get("/api/v1/audio/history?voice_id=rachel_v2", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert [item["id"] for item in payload["items"]] == [second_id]

        resp = test_client.get("/api/v1/audio/history?voice_name=Alloy", headers=auth_headers)
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert [item["id"] for item in payload["items"]] == [first_id]

        resp = test_client.get(
            "/api/v1/audio/history?voice_id=alloy&voice_name=Alloy",
            headers=auth_headers,
        )
        assert resp.status_code == status.HTTP_200_OK
        payload = resp.json()
        assert [item["id"] for item in payload["items"]] == [first_id]
    finally:
        app.dependency_overrides.pop(get_media_db_for_user, None)
        db.close_connection()
