"""Integration tests for llama.cpp chat-completions request extensions."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user
from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint_module


pytestmark = pytest.mark.integration


def _fake_chat_response(content: str = "Mocked response") -> dict:
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": 1,
        "model": "mock-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
    }


def test_chat_completions_resolves_saved_grammar_into_llamacpp_payload(
    test_client,
    auth_headers,
    chacha_db,
    monkeypatch,
):
    grammar_id = chacha_db.insert_chat_grammar(
        {
            "name": "JSON output grammar",
            "grammar_text": 'root ::= "ok"',
        }
    )

    def override_get_db():
        return chacha_db

    captured: dict[str, object] = {}

    def _fake_provider_call(**kwargs):
        captured.update(kwargs)
        return _fake_chat_response(content="Grammar resolved.")

    test_client.app.dependency_overrides[get_chacha_db_for_user] = override_get_db
    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    try:
        response = test_client.post(
            "/api/v1/chat/completions",
            json={
                "model": "llama.cpp/local-model",
                "messages": [{"role": "user", "content": "Reply with ok"}],
                "save_to_db": False,
                "grammar_mode": "library",
                "grammar_id": grammar_id,
            },
            headers=auth_headers,
        )
    finally:
        test_client.app.dependency_overrides.pop(get_chacha_db_for_user, None)

    assert response.status_code == 200
    assert captured["api_endpoint"] == "llama.cpp"
    assert captured["extra_body"] == {"grammar": 'root ::= "ok"'}


def test_chat_completions_rejects_llamacpp_fields_for_resolved_non_llamacpp_provider(
    test_client,
    auth_headers,
):
    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "openai",
            "model": "llama.cpp/local-model",
            "messages": [{"role": "user", "content": "Reply with ok"}],
            "save_to_db": False,
            "grammar_mode": "inline",
            "grammar_inline": 'root ::= "ok"',
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid request."
