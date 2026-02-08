"""Integration tests for persona exemplar integration in /chat/completions."""

from __future__ import annotations

import json

import pytest

from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint_module

pytestmark = pytest.mark.integration


def _create_character(test_client, auth_headers, name: str) -> int:
    response = test_client.post(
        "/api/v1/characters/",
        json={
            "name": name,
            "description": "Persona integration test character",
            "personality": "Confident and concise",
            "first_message": "Hello there.",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def _create_exemplar(test_client, auth_headers, character_id: int, text: str) -> str:
    response = test_client.post(
        f"/api/v1/characters/{character_id}/exemplars",
        json={
            "text": text,
            "labels": {
                "emotion": "neutral",
                "scenario": "press_challenge",
                "rhetorical": ["opener", "emphasis"],
            },
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _fake_chat_response(content: str = "Mock persona reply") -> dict:
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
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def test_chat_completion_injects_persona_exemplar_guidance_and_debug_meta(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character")
    exemplar_id = _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "When pressed by reporters, stay calm, answer directly, and pivot to constructive facts.",
    )

    observed: dict[str, str | None] = {"system_message": None}

    def _fake_provider_call(**kwargs):
        observed["system_message"] = kwargs.get("system_message")
        return _fake_chat_response()

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [
                {"role": "user", "content": "How should I answer this reporter question?"}
            ],
            "persona_exemplar_budget_tokens": 120,
            "persona_exemplar_strategy": "default",
            "persona_debug": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    system_message = str(observed["system_message"] or "")
    assert "[Persona Exemplars]" in system_message
    assert "stay calm" in system_message

    persona_meta = ((payload.get("meta") or {}).get("persona") or {})
    assert persona_meta.get("enabled") is True
    assert persona_meta.get("applied") is True
    assert persona_meta.get("strategy") == "default"
    assert persona_meta.get("debug_id")
    selection = persona_meta.get("selection") or {}
    assert selection.get("selected_count", 0) >= 1
    assert exemplar_id in (selection.get("selected_exemplar_ids") or [])
    telemetry = persona_meta.get("telemetry") or {}
    assert set(["ioo", "ior", "lcs", "safety_flags"]).issubset(set(telemetry.keys()))
    assert 0.0 <= float(telemetry.get("ioo", -1.0)) <= 1.0
    assert 0.0 <= float(telemetry.get("ior", -1.0)) <= 1.0
    assert 0.0 <= float(telemetry.get("lcs", -1.0)) <= 1.0
    assert isinstance(telemetry.get("safety_flags"), list)


def test_chat_completion_persona_strategy_off_skips_exemplar_injection(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Off")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "This exemplar should not be injected when persona strategy is off.",
    )

    observed: dict[str, str | None] = {"system_message": None}

    def _fake_provider_call(**kwargs):
        observed["system_message"] = kwargs.get("system_message")
        return _fake_chat_response()

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "Give me a response."}],
            "persona_exemplar_strategy": "off",
            "persona_debug": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    system_message = str(observed["system_message"] or "")
    assert "[Persona Exemplars]" not in system_message

    persona_meta = ((payload.get("meta") or {}).get("persona") or {})
    assert persona_meta.get("enabled") is True
    assert persona_meta.get("applied") is False
    assert persona_meta.get("reason") == "disabled_by_strategy"
    telemetry = persona_meta.get("telemetry") or {}
    assert set(["ioo", "ior", "lcs", "safety_flags"]).issubset(set(telemetry.keys()))


def test_streaming_chat_persona_debug_exposes_debug_id_header(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Stream")

    def _fake_stream_call(**kwargs):
        if not kwargs.get("streaming"):
            return _fake_chat_response(content="Non-stream fallback")

        def _stream():
            data_chunk = {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "Streaming persona response"},
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(data_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return _stream()

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_stream_call)

    with test_client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "Stream a response"}],
            "stream": True,
            "persona_debug": True,
        },
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers.get("X-TLDW-Persona-Debug-ID")
        chunks = list(response.iter_text())
        assert any("data:" in chunk for chunk in chunks)
