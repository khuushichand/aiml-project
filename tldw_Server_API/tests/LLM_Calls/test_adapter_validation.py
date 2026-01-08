from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
from tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter import OpenAIAdapter
from tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter import OpenRouterAdapter
from tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter import MistralAdapter


def test_openai_adapter_rejects_provider_unsupported_fields(monkeypatch):
    def _fail_factory(*_args, **_kwargs):
        raise AssertionError("http_client_factory should not be called on validation errors")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.openai_adapter.http_client_factory",
        _fail_factory,
    )

    adapter = OpenAIAdapter()
    with pytest.raises(ChatBadRequestError) as exc:
        adapter.chat({"messages": [], "model": "gpt-3.5-turbo", "top_k": 5})
    assert "top_k" in str(exc.value)


def test_openrouter_adapter_normalizes_topk_alias(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": []}

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResp()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.openrouter_adapter.http_client_factory",
        lambda *a, **k: FakeClient(),
    )

    adapter = OpenRouterAdapter()
    adapter.chat(
        {
            "messages": [{"role": "user", "content": "hello"}],
            "model": "openrouter/test-model",
            "topk": 7,
        }
    )

    payload = captured["json"]
    assert payload["top_k"] == 7
    assert "topk" not in payload


def test_mistral_adapter_rejects_min_p(monkeypatch):
    def _fail_factory(*_args, **_kwargs):
        raise AssertionError("http_client_factory should not be called on validation errors")

    monkeypatch.setattr(
        "tldw_Server_API.app.core.LLM_Calls.providers.mistral_adapter.http_client_factory",
        _fail_factory,
    )

    adapter = MistralAdapter()
    with pytest.raises(ChatBadRequestError) as exc:
        adapter.chat({"messages": [], "model": "mistral-small", "min_p": 0.2})
    assert "min_p" in str(exc.value)
