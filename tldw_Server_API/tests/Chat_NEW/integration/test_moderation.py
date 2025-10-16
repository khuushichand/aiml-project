import os
import json
import re
import tempfile
import pytest
from typing import Any
from fastapi.testclient import TestClient
from unittest.mock import patch

from fastapi import FastAPI
from tldw_Server_API.app.api.v1.endpoints.chat import router as chat_router
from tldw_Server_API.app.api.v1.endpoints.health import router as health_router
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user, DEFAULT_CHARACTER_NAME


# Minimal app with only health and chat routers to avoid unrelated imports
app = FastAPI()
app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1/chat")

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


def _post_with_csrf(client: TestClient, url: str, **kwargs):
    headers = kwargs.pop("headers", {}) or {}
    csrf = getattr(client, "csrf_token", "")
    return client.post(url, headers={"X-CSRF-Token": csrf, **headers}, **kwargs)


def _auth_headers(client):
    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    settings = get_settings()
    api_key = settings.SINGLE_USER_API_KEY or os.getenv("API_BEARER", "test-api-key-12345")
    return {"X-API-KEY": api_key, "X-CSRF-Token": getattr(client, 'csrf_token', '')}


class _StubPolicy:
    def __init__(self, enabled=True, input_action='block', output_action='redact', redact='[REDACTED]', patterns=None):
        self.enabled = enabled
        self.input_enabled = True
        self.output_enabled = True
        self.input_action = input_action
        self.output_action = output_action
        self.redact_replacement = redact
        self.block_patterns = patterns or [re.compile(r"secret", re.IGNORECASE)]


class _StubModerationService:
    def __init__(self, policy: _StubPolicy):
        self._policy = policy

    def get_effective_policy(self, user_id: str):
        return self._policy

    def check_text(self, text: str, policy: _StubPolicy):
        for pat in policy.block_patterns:
            if pat.search(text or ""):
                return True, pat.pattern
        return False, None

    def redact_text(self, text: str, policy: _StubPolicy):
        red = text
        for pat in policy.block_patterns:
            red = pat.sub(policy.redact_replacement, red)
        return red


@pytest.mark.unit
def test_input_block_returns_400(monkeypatch):
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db
        policy = _StubPolicy(enabled=True, input_action='block', output_action='redact')

        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_moderation_service", return_value=_StubModerationService(policy)):
            with TestClient(app) as client:
                resp = client.get("/api/v1/health")
                client.csrf_token = resp.cookies.get("csrf_token", "")
                body = {
                    "api_provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "please say secret"}],
                    "stream": False
                }
                # No need to patch provider; should block before provider call
                r = _post_with_csrf(client, "/api/v1/chat/completions", json=body, headers=_auth_headers(client))
                assert r.status_code == 400
                assert "violates" in r.json().get("detail", "").lower()
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.unit
def test_output_redaction_non_streaming(monkeypatch):
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db
        policy = _StubPolicy(enabled=True, input_action='warn', output_action='redact', redact='[REDACTED]')

        # Mock provider to return a fixed non-streaming response
        reply = {
            "id": "chatcmpl-1",
            "object": "chat.completion",
            "created": 123,
            "model": "gpt-4o-mini",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "this has secret token"}, "finish_reason": "stop"}
            ]
        }

        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_moderation_service", return_value=_StubModerationService(policy)), \
             patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value=reply):
            with TestClient(app) as client:
                resp = client.get("/api/v1/health")
                client.csrf_token = resp.cookies.get("csrf_token", "")
                body = {
                    "api_provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": False
                }
                r = _post_with_csrf(client, "/api/v1/chat/completions", json=body, headers=_auth_headers(client))
                assert r.status_code == 200
                data = r.json()
                got = data.get("choices", [{}])[0].get("message", {}).get("content")
                assert got == "this has [REDACTED] token"
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.unit
def test_streaming_redaction_applied():
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db
        policy = _StubPolicy(enabled=True, input_action='warn', output_action='redact', redact='[REDACTED]')

        def upstream_stream():
            chunk1 = {"choices": [{"delta": {"content": "leak: secret"}}]}
            chunk2 = {"choices": [{"delta": {"content": " appears"}}]}
            yield f"data: {json.dumps(chunk1)}\n\n"
            yield f"data: {json.dumps(chunk2)}\n\n"
            yield "data: [DONE]\n\n"

        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_moderation_service", return_value=_StubModerationService(policy)), \
             patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value=upstream_stream()):
            with TestClient(app) as client:
                resp = client.get("/api/v1/health")
                client.csrf_token = resp.cookies.get("csrf_token", "")
                body = {
                    "api_provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True
                }
                r = _post_with_csrf(client, "/api/v1/chat/completions", json=body, headers=_auth_headers(client))
                assert r.status_code == 200
                content = r.text.splitlines()
                chunks = []
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
                            chunks.append(text)
                full = "".join(chunks)
                assert "secret" not in full
                assert "[REDACTED]" in full
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.unit
def test_streaming_block_emits_sse_error_and_finishes():
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db
        # Block on output
        policy = _StubPolicy(enabled=True, input_action='warn', output_action='block', redact='[REDACTED]')

        def upstream_stream():
            chunk1 = {"choices": [{"delta": {"content": "this contains secret"}}]}
            chunk2 = {"choices": [{"delta": {"content": " should be blocked"}}]}
            yield f"data: {json.dumps(chunk1)}\n\n"
            yield f"data: {json.dumps(chunk2)}\n\n"
            yield "data: [DONE]\n\n"

        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_moderation_service", return_value=_StubModerationService(policy)), \
             patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value=upstream_stream()):
            with TestClient(app) as client:
                resp = client.get("/api/v1/health")
                client.csrf_token = resp.cookies.get("csrf_token", "")
                body = {
                    "api_provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": True
                }
                r = _post_with_csrf(client, "/api/v1/chat/completions", json=body, headers=_auth_headers(client))
                assert r.status_code == 200
                lines = r.text.splitlines()
                saw_error = any((ln.startswith("data:") and '"error":' in ln) for ln in lines)
                saw_done = any((ln.strip() == 'data: [DONE]') for ln in lines)
                assert saw_error, f"Expected SSE error in stream, got: {r.text[:200]}"
                assert saw_done, "Expected [DONE] marker for graceful finish"
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)
