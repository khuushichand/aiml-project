import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatProviderError
from tldw_Server_API.app.core.Chat.chat_service import (
    execute_non_stream_call,
    execute_streaming_call,
    merge_api_keys_for_provider,
)


class _DummyMetrics:
    def __init__(self):
        self.llm_calls = []
        self.fallback_successes = []

    def track_llm_call(self, provider, model, latency, success, error_type=None):
        self.llm_calls.append((provider, model, success, error_type))

    def track_provider_fallback_success(self, **metadata):
        self.fallback_successes.append(metadata)

    def track_tokens(self, **_kwargs):
        return None


class _DummyProviderManager:
    def __init__(self):
        self.failure_records = []
        self.success_records = []
        self.fallback_requests = []

    def get_available_provider(self, exclude=None):
        self.fallback_requests.append(tuple(exclude or []))
        return "openai"

    def record_failure(self, provider, error):
        self.failure_records.append((provider, type(error).__name__))

    def record_success(self, provider, latency):
        self.success_records.append(provider)


class _DummyModeration:
    class _Policy:
        enabled = False
        output_enabled = False

    def get_effective_policy(self, *_args, **_kwargs):
        return self._Policy()

    def evaluate_action(self, *_args, **_kwargs):
        return None

    def check_text(self, *_args, **_kwargs):
        return (False, None)

    def redact_text(self, text, *_args, **_kwargs):
        return text


@pytest.mark.asyncio
async def test_execute_non_stream_call_refreshes_credentials(monkeypatch):
    captured_kwargs = {}

    async def fake_perform_chat_api_call_async(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "choices": [
                {"message": {"content": "fallback success"}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        }

    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "perform_chat_api_call_async", fake_perform_chat_api_call_async)
    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)

    metrics = _DummyMetrics()
    provider_manager = _DummyProviderManager()

    def failing_llm_call():
        raise ChatProviderError(provider="anthropic", message="primary failed", status_code=502)

    async def save_message_fn(*_args, **_kwargs):
        return None

    def refresh_provider(provider_name: str):
        assert provider_name == "openai"
        return (
            {
                "api_endpoint": "openai",
                "api_key": "fresh-key",
                "messages_payload": [],
                "model": "gpt-4o",
                "streaming": False,
            },
            "gpt-4o",
        )

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/v1/chat/completions"),
        headers={},
        state=SimpleNamespace(user_id=None, api_key_id=None),
    )

    response = await execute_non_stream_call(
        current_loop=asyncio.get_running_loop(),
        cleaned_args={
            "api_endpoint": "anthropic",
            "api_key": "stale-key",
            "messages_payload": [],
            "model": "claude-3",
            "streaming": False,
        },
        selected_provider="anthropic",
        provider="anthropic",
        model="claude-3",
        request_json="{}",
        request=request,
        metrics=metrics,
        provider_manager=provider_manager,
        templated_llm_payload=[],
        should_persist=False,
        final_conversation_id="conv-123",
        character_card_for_context={},
        chat_db=None,
        save_message_fn=save_message_fn,
        audit_service=None,
        audit_context=None,
        client_id="user-123",
        queue_execution_enabled=False,
        enable_provider_fallback=True,
        llm_call_func=failing_llm_call,
        refresh_provider_params=refresh_provider,
        moderation_getter=_DummyModeration,
    )

    assert captured_kwargs["api_endpoint"] == "openai"
    assert captured_kwargs["api_key"] == "fresh-key"
    assert captured_kwargs["model"] == "gpt-4o"
    assert response["tldw_conversation_id"] == "conv-123"
    assert provider_manager.fallback_requests == [("anthropic",)]
    assert provider_manager.success_records == ["openai"]
    assert any(
        entry.get("selected_provider") == "openai" and entry.get("streaming") is False
        for entry in metrics.fallback_successes
    )


@pytest.mark.asyncio
async def test_execute_streaming_call_preserves_http_exception(monkeypatch):
    metrics = _DummyMetrics()
    provider_manager = _DummyProviderManager()

    http_exc = HTTPException(status_code=429, detail="Rate limited")

    def failing_llm_call():
        raise http_exc

    async def save_message_fn(*_args, **_kwargs):
        return None

    monkeypatch.setattr(chat_service, "get_request_queue", lambda: None)

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/v1/chat/completions"),
        headers={},
        state=SimpleNamespace(user_id=None, api_key_id=None),
    )

    with pytest.raises(HTTPException) as exc_info:
        await execute_streaming_call(
            current_loop=asyncio.get_running_loop(),
            cleaned_args={
                "api_endpoint": "openai",
                "messages_payload": [],
                "model": "gpt-test",
                "streaming": True,
            },
            selected_provider="openai",
            provider="openai",
            model="gpt-test",
            request_json="{}",
            request=request,
            metrics=metrics,
            provider_manager=provider_manager,
            templated_llm_payload=[],
            should_persist=False,
            final_conversation_id="conv-test",
            character_card_for_context={"name": "Test"},
            chat_db=None,
            save_message_fn=save_message_fn,
            audit_service=None,
            audit_context=None,
            client_id="client-test",
            queue_execution_enabled=False,
            enable_provider_fallback=False,
            llm_call_func=failing_llm_call,
            refresh_provider_params=lambda _provider: ({}, None),
            moderation_getter=lambda: _DummyModeration(),
        )

    assert exc_info.value is http_exc
    # The last llm call recorded should indicate an HTTPException error type
    assert metrics.llm_calls[-1][3] in ("HTTPException", "HTTPException")


def test_merge_api_keys_prefers_dynamic_over_module():
    module_keys = {"openai": "module-key", "anthropic": "module-anthropic"}
    dynamic_keys = {"openai": "dynamic-key", "anthropic": ""}

    raw_openai, normalized_openai = merge_api_keys_for_provider(
        "openai",
        module_keys,
        dynamic_keys,
        {},
    )
    assert raw_openai == "dynamic-key"
    assert normalized_openai == "dynamic-key"

    raw_anthropic, normalized_anthropic = merge_api_keys_for_provider(
        "anthropic",
        module_keys,
        dynamic_keys,
        {},
    )
    assert raw_anthropic == "module-anthropic"
    assert normalized_anthropic == "module-anthropic"
