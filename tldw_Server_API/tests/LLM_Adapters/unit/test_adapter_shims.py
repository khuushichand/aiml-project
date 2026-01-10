import json
from typing import Any, Dict, List, Iterator

import pytest
from unittest.mock import patch


def _messages() -> List[Dict[str, Any]]:
    return [{"role": "user", "content": "hi"}]


def test_openai_shim_preserves_streaming_none_and_topp_fallback(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openai_chat_handler

    captured: Dict[str, Any] = {}

    def _fake_openai(**kwargs):
        captured.update(kwargs)
        # Return a minimal non-streaming-ish object
        return {"ok": True}

    # Force adapter path
    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_openai",
        _fake_openai,
    ):
        # streaming=None and topp fallback should be forwarded to legacy unchanged
        resp = openai_chat_handler(
            input_data=_messages(),
            model="gpt-4o-mini",
            streaming=None,
            maxp=None,
            api_key="dummy",
            topp=0.77,  # provided via kwargs, used when maxp is None
        )
        assert resp == {"ok": True}
        # streaming=None to preserve config default at legacy handler
        assert "streaming" in captured and captured["streaming"] is None
        # topp fallback maps to legacy's 'maxp' param
        assert captured.get("maxp") == 0.77


def test_openai_shim_streaming_true_single_done(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openai_chat_handler

    def _fake_openai(**kwargs) -> Iterator[str]:
        # Validate streaming intent
        assert kwargs.get("streaming") is True
        yield "data: {\"choices\":[{\"delta\":{\"content\":\"hello\"}}]}\n\n"
        yield "data: [DONE]\n\n"

    # Force adapter path
    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_openai",
        _fake_openai,
    ):
        stream = openai_chat_handler(
            input_data=_messages(),
            model="gpt-4o-mini",
            streaming=True,
            api_key="dummy",
        )
        chunks = list(stream)
        assert any("data:" in c for c in chunks)
        # Ensure exactly one [DONE]
        assert sum(1 for c in chunks if "[DONE]" in c) == 1


def test_anthropic_shim_stop_sequences_mapping(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import anthropic_chat_handler

    captured: Dict[str, Any] = {}

    def _fake_anthropic(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_anthropic",
        _fake_anthropic,
    ):
        resp = anthropic_chat_handler(
            input_data=_messages(),
            model="claude-sonnet-4",
            streaming=False,
            stop_sequences=["\n\n"],
            tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}],
            api_key="dummy",
        )
        assert resp == {"ok": True}
        assert captured.get("stop_sequences") == ["\n\n"]
        assert isinstance(captured.get("tools"), list)


def test_groq_shim_logprobs_toplogprobs_forwarding(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import groq_chat_handler

    captured: Dict[str, Any] = {}

    def _fake_groq(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_groq",
        _fake_groq,
    ):
        resp = groq_chat_handler(
            input_data=_messages(),
            model="llama3-70b",
            logprobs=True,
            top_logprobs=3,
            api_key="dummy",
        )
        assert resp == {"ok": True}
        assert captured.get("logprobs") is True
        assert captured.get("top_logprobs") == 3


def test_openrouter_shim_top_k_min_p_forwarding(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import openrouter_chat_handler

    captured: Dict[str, Any] = {}

    def _fake_openrouter(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_openrouter",
        _fake_openrouter,
    ):
        resp = openrouter_chat_handler(
            input_data=_messages(),
            model="meta-llama/llama-3-8b",
            top_k=50,
            min_p=0.05,
            top_p=0.9,
            api_key="dummy",
        )
        assert resp == {"ok": True}
        assert captured.get("top_k") == 50
        assert captured.get("min_p") == 0.05
        assert captured.get("top_p") == 0.9


def test_google_shim_generation_config_mapping(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import google_chat_handler

    captured: Dict[str, Any] = {}

    def _fake_google(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_google",
        _fake_google,
    ):
        resp = google_chat_handler(
            input_data=_messages(),
            model="gemini-1.5-pro",
            topp=0.9,
            topk=20,
            max_output_tokens=333,
            api_key="dummy",
        )
        assert resp == {"ok": True}
        assert captured.get("topp") == 0.9
        assert captured.get("topk") == 20
        assert captured.get("max_output_tokens") == 333


def test_mistral_shim_random_seed_top_k_safe_prompt(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls.adapter_calls import mistral_chat_handler

    captured: Dict[str, Any] = {}

    def _fake_mistral(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    with patch(
        "tldw_Server_API.app.core.LLM_Calls.chat_calls.chat_with_mistral",
        _fake_mistral,
    ):
        resp = mistral_chat_handler(
            input_data=_messages(),
            model="mistral-large-latest",
            random_seed=123,
            top_k=42,
            safe_prompt=True,
            api_key="dummy",
        )
        assert resp == {"ok": True}
        assert captured.get("random_seed") == 123
        assert captured.get("top_k") == 42
        assert captured.get("safe_prompt") is True


def test_cohere_shim_uses_adapter_registry(monkeypatch):
    from tldw_Server_API.app.core.LLM_Calls import adapter_calls as shims

    expected = {"ok": True, "message": "parity"}

    class DummyAdapter:
        def chat(self, request):
            return expected

    class DummyRegistry:
        def get_adapter(self, name):
            return DummyAdapter()

        def register_adapter(self, name, adapter):
            return None

    monkeypatch.setattr(shims, "get_registry", lambda: DummyRegistry())
    resp = shims.cohere_chat_handler(
        input_data=_messages(),
        model="cohere-test",
        api_key="dummy",
        streaming=False,
    )
    assert resp == expected


@pytest.mark.parametrize(
    "provider_case",
    [
        {
            "name": "moonshot",
            "handler": "moonshot_chat_handler",
            "kwargs": {"input_data": _messages(), "model": "moonshot-test", "api_key": "dummy"},
        },
        {
            "name": "zai",
            "handler": "zai_chat_handler",
            "kwargs": {"input_data": _messages(), "model": "zai-test", "api_key": "dummy"},
        },
        {
            "name": "local-llm",
            "handler": "local_llm_chat_handler",
            "kwargs": {"input_data": _messages(), "model": "local-test"},
        },
    ],
    ids=["moonshot", "zai", "local-llm"],
)
@pytest.mark.parametrize("streaming", [False, True], ids=["non-stream", "stream"])
def test_shim_uses_adapter_moonshot_zai_local(monkeypatch, provider_case, streaming):
    from tldw_Server_API.app.core.LLM_Calls import adapter_calls as shims

    expected = {"ok": True, "provider": provider_case["name"]}
    chunk_payload = json.dumps({"choices": [{"delta": {"content": provider_case["name"]}}]})
    expected_stream = [f"data: {chunk_payload}\n\n", "data: [DONE]\n\n"]

    class DummyAdapter:
        def chat(self, request):
            return expected

        def stream(self, request):
            return iter(expected_stream)

    class DummyRegistry:
        def get_adapter(self, name):
            return DummyAdapter()

        def register_adapter(self, name, adapter):
            return None

    monkeypatch.setattr(shims, "get_registry", lambda: DummyRegistry())
    handler = getattr(shims, provider_case["handler"])
    resp = handler(streaming=streaming, **provider_case["kwargs"])
    resp = list(resp) if streaming else resp
    assert resp == (expected_stream if streaming else expected)
