import os
import json
import tempfile
import pytest
from typing import Any, Optional, Tuple
from fastapi.testclient import TestClient
from unittest.mock import patch

from fastapi import FastAPI
from tldw_Server_API.app.api.v1.endpoints.chat import router as chat_router
from tldw_Server_API.app.api.v1.endpoints.health import router as health_router
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user, DEFAULT_CHARACTER_NAME


app = FastAPI()
app.include_router(health_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1/chat")


def _make_test_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    db = CharactersRAGDB(db_path, "test_client")
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


class _Policy:
    def __init__(self, categories_enabled: Optional[set] = None):
        self.enabled = True
        self.input_enabled = True
        self.output_enabled = True
        self.input_action = 'block'
        self.output_action = 'redact'
        self.redact_replacement = '[REDACTED]'
        self.block_patterns = []
        self.categories_enabled = categories_enabled


class _Svc:
    def __init__(self, policy: _Policy):
        self._p = policy

    def get_effective_policy(self, user_id: str):
        return self._p

    def evaluate_action(self, text: str, policy: _Policy, phase: str) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        # Simulate a built-in PII email rule tagged {'pii', 'pii_email'}
        if 'user@example.com' in text:
            cats = policy.categories_enabled
            if not cats or ('pii' in cats or 'pii_email' in cats):
                # redact email
                return 'redact', text.replace('user@example.com', '[PII]'), 'email', 'pii_email'
            return 'pass', None, None, None
        return 'pass', None, None, None


@pytest.mark.unit
def test_categories_allow_pii_redaction():
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db
        policy = _Policy(categories_enabled={'pii'})
        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_moderation_service", return_value=_Svc(policy)):
            with TestClient(app) as client:
                resp = client.get("/api/v1/health")
                client.csrf_token = resp.cookies.get("csrf_token", "")
                body = {
                    "api_provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "the email is user@example.com"}],
                    "stream": False
                }
                # Mock provider to echo back user content
                with patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value={
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "created": 123,
                    "model": "gpt-4o-mini",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "the email is user@example.com"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
                }):
                    r = _post_with_csrf(client, "/api/v1/chat/completions", json=body, headers=_auth_headers(client))
                    assert r.status_code == 200
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    assert "[PII]" in content
                    assert "user@example.com" not in content
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)


@pytest.mark.unit
def test_categories_disable_pii_redaction():
    db, db_path = _make_test_db()
    try:
        app.dependency_overrides[get_chacha_db_for_user] = lambda: db
        policy = _Policy(categories_enabled={'confidential'})  # no 'pii'
        with patch("tldw_Server_API.app.api.v1.endpoints.chat.get_moderation_service", return_value=_Svc(policy)):
            with TestClient(app) as client:
                resp = client.get("/api/v1/health")
                client.csrf_token = resp.cookies.get("csrf_token", "")
                body = {
                    "api_provider": "openai",
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "the email is user@example.com"}],
                    "stream": False
                }
                with patch("tldw_Server_API.app.api.v1.endpoints.chat.perform_chat_api_call", return_value={
                    "id": "chatcmpl-1",
                    "object": "chat.completion",
                    "created": 123,
                    "model": "gpt-4o-mini",
                    "choices": [
                        {"index": 0, "message": {"role": "assistant", "content": "the email is user@example.com"}, "finish_reason": "stop"}
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
                }):
                    r = _post_with_csrf(client, "/api/v1/chat/completions", json=body, headers=_auth_headers(client))
                    assert r.status_code == 200
                    data = r.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    # No redaction expected
                    assert "user@example.com" in content
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"): os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"): os.unlink(db_path + "-shm")
        except Exception:
            pass
        app.dependency_overrides.pop(get_chacha_db_for_user, None)
