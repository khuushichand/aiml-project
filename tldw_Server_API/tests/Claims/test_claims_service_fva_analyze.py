from __future__ import annotations

from tldw_Server_API.app.core.Claims_Extraction import claims_service


def test_fva_analyze_passes_response_format_and_returns_choice_content(monkeypatch):
    captured = {}

    def _fake_chat_call(**kwargs):
        captured.update(kwargs)
        return {"choices": [{"message": {"content": '{"label":"supported"}'}}]}

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.chat_service.perform_chat_api_call",
        _fake_chat_call,
    )

    out = claims_service._fva_claims_analyze_call(
        "openai",
        "ignored input",
        "Use this prompt",
        None,
        "System message",
        0.12,
        False,
        False,
        False,
        None,
        model_override="gpt-test",
        response_format={"type": "json_object"},
    )

    assert out == '{"label":"supported"}'
    assert captured["api_endpoint"] == "openai"
    assert captured["model"] == "gpt-test"
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["messages_payload"][0]["content"] == "Use this prompt"


def test_fva_analyze_uses_input_data_when_prompt_missing(monkeypatch):
    def _fake_chat_call(**kwargs):
        return {"response": "ok-from-input"}

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.chat_service.perform_chat_api_call",
        _fake_chat_call,
    )

    out = claims_service._fva_claims_analyze_call(
        "openai",
        "input fallback text",
        None,
        None,
        None,
        0.2,
    )

    assert out == "ok-from-input"


def test_fva_analyze_returns_empty_on_provider_error(monkeypatch):
    def _fake_chat_call(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Chat.chat_service.perform_chat_api_call",
        _fake_chat_call,
    )

    out = claims_service._fva_claims_analyze_call(
        "openai",
        "input",
        "prompt",
        None,
        None,
        0.2,
    )

    assert out == ""
