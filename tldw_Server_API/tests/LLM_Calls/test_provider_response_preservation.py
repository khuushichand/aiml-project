from __future__ import annotations

from typing import Any, Dict

from tldw_Server_API.app.core.LLM_Calls.providers.anthropic_adapter import AnthropicAdapter
from tldw_Server_API.app.core.LLM_Calls.providers.google_adapter import GoogleAdapter
from tldw_Server_API.app.core.LLM_Calls.providers.cohere_adapter import _cohere_request
import tldw_Server_API.app.core.LLM_Calls.chat_calls as chat_calls


def test_anthropic_preserves_provider_response():
    payload: Dict[str, Any] = {
        "type": "message",
        "id": "msg-1",
        "model": "claude-3-5-sonnet-latest",
        "content": [{"type": "text", "text": "hi"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 2},
        "extra_field": {"ok": True},
    }
    normalized = AnthropicAdapter._normalize_to_openai_shape(payload)
    assert normalized["provider_response"]["extra_field"]["ok"] is True


def test_google_preserves_provider_response():
    payload: Dict[str, Any] = {
        "responseId": "resp-1",
        "candidates": [
            {
                "content": {"parts": [{"text": "hello"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 2, "totalTokenCount": 3},
        "extra_field": {"source": "google"},
    }
    normalized = GoogleAdapter._normalize_to_openai_shape(payload)
    assert normalized["provider_response"]["extra_field"]["source"] == "google"


def test_google_stream_preserves_provider_response():
    event = {
        "candidates": [
            {
                "content": {"parts": [{"text": "hello"}]},
                "finishReason": "STOP",
            }
        ],
        "extra_field": {"source": "google"},
    }
    chunks = list(GoogleAdapter._stream_event_deltas(event))
    assert chunks
    payload = chunks[0].split("data:", 1)[1].strip()
    assert "\"provider_response\"" in payload


def test_cohere_preserves_provider_response(monkeypatch):
    response_payload = {
        "generation_id": "cohere-1",
        "text": "hello",
        "meta": {"billed_units": {"input_tokens": 1, "output_tokens": 2}},
        "extra_field": {"source": "cohere"},
    }

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return response_payload

    class FakeSession:
        def post(self, *args, **kwargs):
            return FakeResponse()

        def close(self):
            return None

    def fake_create_session_with_retries(*args, **kwargs):
        return FakeSession()

    monkeypatch.setattr(chat_calls, "create_session_with_retries", fake_create_session_with_retries)

    result = _cohere_request(
        input_data=[{"role": "user", "content": "hi"}],
        model="command-r",
        api_key="test-key",
        app_config={"cohere_api": {"api_key": "test-key"}},
    )

    assert result["provider_response"]["extra_field"]["source"] == "cohere"
