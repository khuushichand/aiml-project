import asyncio
from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Chat.chat_service import execute_non_stream_call


class _DummyMetrics:
    def track_llm_call(self, *_args, **_kwargs):
        return None

    def track_provider_fallback_success(self, *_args, **_kwargs):
        return None

    def track_tokens(self, *_args, **_kwargs):
        return None

    def track_moderation_output(self, *_args, **_kwargs):
        return None


class _RedactingModeration:
    class _Policy:
        enabled = True
        output_enabled = True
        output_action = "redact"

    def get_effective_policy(self, *_args, **_kwargs):
        return self._Policy()

    def evaluate_action_with_match(self, *_args, **_kwargs):
        return ("redact", None, None, None, None)

    def check_text(self, *_args, **_kwargs):
        return (False, None)

    def redact_text(self, text, *_args, **_kwargs):
        return f"REDACTED:{text}"


@pytest.mark.asyncio
async def test_execute_non_stream_call_redacts_list_content(monkeypatch):
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)

    def llm_call_func():
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "secret"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64,AAA"},
                            },
                        ],
                    },
                    "finish_reason": "stop",
                }
            ]
        }

    async def save_message_fn(*_args, **_kwargs):
        return None

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/v1/chat/completions"),
        headers={},
        state=SimpleNamespace(user_id=None, api_key_id=None),
    )

    response = await execute_non_stream_call(
        current_loop=asyncio.get_running_loop(),
        cleaned_args={
            "api_endpoint": "openai",
            "api_key": "test-key",
            "messages_payload": [{"role": "user", "content": "hi"}],
            "model": "gpt-4o-mini",
            "streaming": False,
        },
        selected_provider="openai",
        provider="openai",
        model="gpt-4o-mini",
        request_json="{}",
        request=request,
        metrics=_DummyMetrics(),
        provider_manager=None,
        templated_llm_payload=[{"role": "user", "content": "hi"}],
        should_persist=False,
        final_conversation_id="conv-123",
        character_card_for_context={"name": "Test"},
        chat_db=None,
        save_message_fn=save_message_fn,
        audit_service=None,
        audit_context=None,
        client_id="client",
        queue_execution_enabled=False,
        enable_provider_fallback=False,
        llm_call_func=llm_call_func,
        refresh_provider_params=lambda *_args, **_kwargs: None,
        moderation_getter=lambda: _RedactingModeration(),
    )

    content = response["choices"][0]["message"]["content"]
    assert isinstance(content, list)
    assert content[0]["text"].startswith("REDACTED:")
    assert content[1]["type"] == "image_url"
