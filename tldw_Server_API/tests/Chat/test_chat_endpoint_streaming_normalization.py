import os
import json
import tempfile
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user, DEFAULT_CHARACTER_NAME


def _make_test_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    db = CharactersRAGDB(db_path, "test_client")
    # Minimal default character required by endpoint
    db.add_character_card({
        "name": DEFAULT_CHARACTER_NAME,
        "description": "Default",
        "personality": "Helpful",
        "scenario": "Testing",
        "system_prompt": "You are helpful",
        "first_message": "Hello",
        "creator_notes": "test"
    })
    return db, db_path


def _make_test_client(db):
    client = TestClient(app)
    # CSRF token for POST
    resp = client.get("/api/v1/health")
    csrf = resp.cookies.get("csrf_token", "")
    client.csrf_token = csrf
    client.post_with_csrf = lambda url, **kwargs: client.post(url, headers={"X-CSRF-Token": csrf, **kwargs.pop("headers", {})}, **kwargs)
    return client


def _auth_headers(client):
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    settings = get_settings()
    api_key = settings.SINGLE_USER_API_KEY or os.getenv("API_BEARER", "default-secret-key-for-single-user")
    return {"X-API-KEY": api_key, "X-CSRF-Token": getattr(client, 'csrf_token', '')}


@pytest.mark.unit
def test_endpoint_streaming_normalizes_openai_sse_frames():
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db

        client = _make_test_client(db)

        # Upstream SSE frames (OpenAI-like)
        chunk1 = {"choices": [{"delta": {"content": "Hello"}}]}
        chunk2 = {"choices": [{"delta": {"content": " world"}}]}

        def upstream_stream():
            yield f"data: {json.dumps(chunk1)}\n\n"
            yield f"data: {json.dumps(chunk2)}\n\n"
            yield "data: [DONE]\n\n"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False), \
             patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value=upstream_stream()):
            body = {
                "api_provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True
            }
            r = client.post_with_csrf("/api/v1/chat/completions", json=body, headers=_auth_headers(client))
            assert r.status_code == 200
            assert 'text/event-stream' in r.headers.get('content-type', '').lower()

            # TestClient buffers entire SSE; parse normalized lines
            content = r.text.splitlines()
            normalized_chunks = []
            for line in content:
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("choices"):
                    delta = obj["choices"][0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        normalized_chunks.append(text)
            assert normalized_chunks == ["Hello", " world"]

    finally:
        # cleanup db files
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.unit
def test_endpoint_streaming_normalizes_multiline_event_and_data_frames():
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db

        client = _make_test_client(db)

        part_a = {"choices": [{"delta": {"content": "Part"}}]}
        part_b = {"choices": [{"delta": {"content": " A"}}]}
        multiline = (
            "event: chunk\n"
            f"data: {json.dumps(part_a)}\n"
            f"data: {json.dumps(part_b)}\n"
            "data: [DONE]\n\n"
        )

        def upstream_stream():
            # A single upstream chunk containing multiple frames
            yield multiline

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False), \
             patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value=upstream_stream()):
            body = {
                "api_provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True
            }
            r = client.post_with_csrf("/api/v1/chat/completions", json=body, headers=_auth_headers(client))
            assert r.status_code == 200
            assert 'text/event-stream' in r.headers.get('content-type', '').lower()

            content = r.text.splitlines()
            normalized_chunks = []
            for line in content:
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("choices"):
                    delta = obj["choices"][0].get("delta", {})
                    text = delta.get("content")
                    if text:
                        normalized_chunks.append(text)
            assert normalized_chunks == ["Part", " A"]

    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)
