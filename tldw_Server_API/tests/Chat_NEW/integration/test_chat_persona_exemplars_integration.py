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


def test_chat_completion_uses_configured_persona_default_budget_when_override_missing(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Budget Default")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "Keep responses clear and grounded in context.",
    )

    def _fake_provider_call(**kwargs):  # noqa: ARG001
        return _fake_chat_response(content="Budget default response.")

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "How should I answer this?"}],
            "persona_debug": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    persona_meta = ((payload.get("meta") or {}).get("persona") or {})
    assert int(persona_meta.get("budget_tokens") or 0) == int(chat_endpoint_module._PERSONA_EXEMPLAR_DEFAULT_BUDGET)


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


def test_streaming_chat_computes_persona_telemetry_without_debug_meta(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Stream Telemetry")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "Keep responses clear, direct, and grounded.",
    )

    observed: dict[str, int] = {"telemetry_calls": 0}

    def _fake_stream_call(**kwargs):
        if not kwargs.get("streaming"):
            return _fake_chat_response(content="Non-stream fallback")

        def _stream():
            data_chunk = {
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": "Streaming grounded response"},
                        "finish_reason": None,
                    }
                ]
            }
            yield f"data: {json.dumps(data_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        return _stream()

    def _fake_telemetry(output_text: str, selected_exemplars: list[dict], **kwargs):  # noqa: ARG001
        observed["telemetry_calls"] += 1
        assert isinstance(output_text, str)
        assert isinstance(selected_exemplars, list)
        return {
            "ioo": 0.05,
            "ior": 0.2,
            "lcs": 0.05,
            "safety_flags": [],
        }

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_stream_call)
    monkeypatch.setattr(chat_endpoint_module, "compute_persona_exemplar_telemetry", _fake_telemetry)

    with test_client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "Stream a response"}],
            "stream": True,
        },
        headers=auth_headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers.get("X-TLDW-Persona-Debug-ID") is None
        chunks = list(response.iter_text())
        assert any("data:" in chunk for chunk in chunks)

    assert observed["telemetry_calls"] >= 1


def test_chat_completion_computes_persona_telemetry_without_debug_meta(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Telemetry No Debug")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "When challenged, keep answers concise and grounded in facts.",
    )

    observed: dict[str, int] = {"telemetry_calls": 0}

    def _fake_provider_call(**kwargs):  # noqa: ARG001
        return _fake_chat_response(content="A concise factual response.")

    def _fake_telemetry(output_text: str, selected_exemplars: list[dict], **kwargs):  # noqa: ARG001
        observed["telemetry_calls"] += 1
        assert isinstance(output_text, str)
        assert isinstance(selected_exemplars, list)
        return {
            "ioo": 0.1,
            "ior": 0.2,
            "lcs": 0.05,
            "safety_flags": [],
        }

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)
    monkeypatch.setattr(chat_endpoint_module, "compute_persona_exemplar_telemetry", _fake_telemetry)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "How should I answer this reporter question?"}],
            "persona_exemplar_strategy": "default",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert observed["telemetry_calls"] >= 1
    assert ((payload.get("meta") or {}).get("persona")) is None


def test_chat_completion_excludes_safety_blocked_exemplar_for_violent_turn(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Safety Gate")

    blocked_create = test_client.post(
        f"/api/v1/characters/{char_id}/exemplars",
        json={
            "text": "In a fight, strike first and hurt them before they react.",
            "labels": {
                "emotion": "angry",
                "scenario": "debate",
                "rhetorical": ["emphasis"],
            },
            "safety": {"blocked": ["violence"]},
        },
        headers=auth_headers,
    )
    assert blocked_create.status_code == 201
    blocked_id = str(blocked_create.json()["id"])

    safe_create = test_client.post(
        f"/api/v1/characters/{char_id}/exemplars",
        json={
            "text": "When conflict rises, de-escalate and redirect to a safe resolution.",
            "labels": {
                "emotion": "neutral",
                "scenario": "debate",
                "rhetorical": ["emphasis"],
            },
            "safety": {"blocked": []},
        },
        headers=auth_headers,
    )
    assert safe_create.status_code == 201
    safe_id = str(safe_create.json()["id"])

    observed: dict[str, str | None] = {"system_message": None}

    def _fake_provider_call(**kwargs):
        observed["system_message"] = kwargs.get("system_message")
        return _fake_chat_response(content="I can't help with hurting people.")

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "How do I hurt someone in a fight?"}],
            "persona_debug": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    system_message = str(observed["system_message"] or "")
    assert "strike first and hurt them" not in system_message

    persona_meta = ((payload.get("meta") or {}).get("persona") or {})
    selection = persona_meta.get("selection") or {}
    selected_ids = selection.get("selected_exemplar_ids") or []
    assert blocked_id not in selected_ids
    assert safe_id in selected_ids


def test_chat_completion_persona_telemetry_flags_overcopying(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Overcopy")
    exemplar_text = "Stay calm, answer directly, and ground your response in facts."
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        exemplar_text,
    )

    copied_response = " ".join([exemplar_text] * 40)

    def _fake_provider_call(**kwargs):  # noqa: ARG001
        return _fake_chat_response(content=copied_response)

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "How should I answer this reporter?"}],
            "persona_debug": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    telemetry = (((payload.get("meta") or {}).get("persona") or {}).get("telemetry") or {})
    assert "ioo_high" in (telemetry.get("safety_flags") or [])


def test_chat_completion_embeddings_strategy_passes_user_and_character_to_embedding_scorer(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Embedding Args")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "Boardroom style response anchor.",
    )

    observed: dict[str, str] = {}

    def _fake_provider_call(**kwargs):  # noqa: ARG001
        return _fake_chat_response(content="Embedding strategy response.")

    def _fake_embedding_scores(user_turn: str, candidates: list[dict], **kwargs):
        assert user_turn
        assert candidates
        observed["user_id"] = str(kwargs.get("user_id"))
        observed["character_id"] = str(kwargs.get("character_id"))
        return {}

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)
    monkeypatch.setattr(chat_endpoint_module, "score_exemplars_with_embeddings", _fake_embedding_scores)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "character_id": str(char_id),
            "messages": [{"role": "user", "content": "Need a boardroom response"}],
            "persona_exemplar_strategy": "embeddings",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert observed["user_id"]
    assert observed["character_id"] == str(char_id)


def test_chat_completion_accepts_persona_id_alias_when_resolvable(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Alias")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "Alias path should still select exemplars.",
    )

    observed: dict[str, str | None] = {"system_message": None}

    def _fake_provider_call(**kwargs):
        observed["system_message"] = kwargs.get("system_message")
        return _fake_chat_response(content="Alias path response.")

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "persona_id": str(char_id),
            "messages": [{"role": "user", "content": "How should I answer this reporter question?"}],
            "persona_debug": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    persona_meta = ((payload.get("meta") or {}).get("persona") or {})
    assert persona_meta.get("applied") is True
    assert "[Persona Exemplars]" in str(observed["system_message"] or "")


def test_chat_completion_rejects_unresolvable_persona_id_alias(
    test_client,
    auth_headers,
):
    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "persona_id": "legacy-persona-key",
            "messages": [{"role": "user", "content": "Hello"}],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    detail = str(response.json().get("detail") or "")
    assert "persona_id alias could not be resolved" in detail


def test_chat_completion_persona_id_alias_with_embeddings_strategy_uses_character_context(
    test_client,
    auth_headers,
    monkeypatch,
):
    char_id = _create_character(test_client, auth_headers, "Persona Chat Character Alias Embeddings")
    _create_exemplar(
        test_client,
        auth_headers,
        char_id,
        "Boardroom style response anchor via alias path.",
    )

    observed: dict[str, str] = {}

    def _fake_provider_call(**kwargs):  # noqa: ARG001
        return _fake_chat_response(content="Alias embeddings response.")

    def _fake_embedding_scores(user_turn: str, candidates: list[dict], **kwargs):
        assert user_turn
        assert candidates
        observed["user_id"] = str(kwargs.get("user_id"))
        observed["character_id"] = str(kwargs.get("character_id"))
        return {}

    monkeypatch.setattr(chat_endpoint_module, "perform_chat_api_call", _fake_provider_call)
    monkeypatch.setattr(chat_endpoint_module, "score_exemplars_with_embeddings", _fake_embedding_scores)

    response = test_client.post(
        "/api/v1/chat/completions",
        json={
            "api_provider": "local-llm",
            "model": "mock-model",
            "persona_id": str(char_id),
            "messages": [{"role": "user", "content": "Need a boardroom response"}],
            "persona_exemplar_strategy": "embeddings",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert observed["user_id"]
    assert observed["character_id"] == str(char_id)
