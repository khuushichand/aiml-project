from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Chat.chat_service import execute_non_stream_call
from tldw_Server_API.app.core.Chat.tool_auto_exec import (
    ToolExecutionBatchResult,
    ToolExecutionRecord,
)


class _DummyMetrics:
    def track_llm_call(self, *_args, **_kwargs):
        return None

    def track_provider_fallback_success(self, *_args, **_kwargs):
        return None

    def track_tokens(self, *_args, **_kwargs):
        return None

    def track_moderation_output(self, *_args, **_kwargs):
        return None


class _NoModeration:
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


def _build_llm_response_with_tool_calls() -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Calling tool",
                    "tool_calls": [
                        {
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "notes.search", "arguments": "{}"},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
    }


async def _run_execute_non_stream_call(
    *,
    llm_call_func,
    save_message_fn,
) -> dict[str, Any]:
    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/v1/chat/completions"),
        headers={},
        state=SimpleNamespace(user_id=11, api_key_id=None),
    )
    return await execute_non_stream_call(
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
        should_persist=True,
        final_conversation_id="conv-123",
        character_card_for_context={"name": "Test"},
        chat_db=SimpleNamespace(),
        save_message_fn=save_message_fn,
        audit_service=None,
        audit_context=None,
        client_id="client-1",
        queue_execution_enabled=False,
        enable_provider_fallback=False,
        llm_call_func=llm_call_func,
        refresh_provider_params=lambda *_args, **_kwargs: None,
        moderation_getter=lambda: _NoModeration(),
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_non_stream_autoexec_disabled_keeps_existing_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: False)

    called = {"autoexec": 0}

    async def fake_autoexec(**_kwargs):
        called["autoexec"] += 1
        return ToolExecutionBatchResult(0, 0, 0, 0, False, [])

    monkeypatch.setattr(chat_service, "execute_assistant_tool_calls", fake_autoexec)

    saved_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        saved_payloads.append(payload)
        return f"m-{len(saved_payloads)}"

    response = await _run_execute_non_stream_call(
        llm_call_func=_build_llm_response_with_tool_calls,
        save_message_fn=save_message_fn,
    )

    assert called["autoexec"] == 0
    assert len(saved_payloads) == 1
    assert saved_payloads[0]["role"] == "assistant"
    assert "tldw_tool_results" not in response


@pytest.mark.asyncio
@pytest.mark.unit
async def test_non_stream_autoexec_enabled_persists_tool_messages_and_response_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: True)
    monkeypatch.setattr(chat_service, "get_chat_max_tool_calls", lambda: 2)
    monkeypatch.setattr(chat_service, "get_chat_tool_timeout_ms", lambda: 3210)
    monkeypatch.setattr(chat_service, "get_chat_tool_allow_catalog", lambda: ["notes.*"])
    monkeypatch.setattr(chat_service, "should_attach_tool_idempotency", lambda: True)

    captured_kwargs: dict[str, Any] = {}

    async def fake_autoexec(**kwargs):
        captured_kwargs.update(kwargs)
        rec = ToolExecutionRecord(
            tool_call_id="c1",
            tool_name="notes.search",
            ok=True,
            result={"echo": {"q": "hello"}},
            module="notes",
            content='{"ok":true}',
        )
        return ToolExecutionBatchResult(
            requested_calls=1,
            processed_calls=1,
            execution_attempts=1,
            executed_calls=1,
            truncated=False,
            results=[rec],
        )

    monkeypatch.setattr(chat_service, "execute_assistant_tool_calls", fake_autoexec)

    saved_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        saved_payloads.append(payload)
        return f"m-{len(saved_payloads)}"

    response = await _run_execute_non_stream_call(
        llm_call_func=_build_llm_response_with_tool_calls,
        save_message_fn=save_message_fn,
    )

    assert captured_kwargs["max_tool_calls"] == 2
    assert captured_kwargs["timeout_ms"] == 3210
    assert captured_kwargs["allow_catalog"] == ["notes.*"]
    assert captured_kwargs["attach_idempotency"] is True
    assert len(saved_payloads) == 2
    assert saved_payloads[0]["role"] == "assistant"
    assert saved_payloads[1]["role"] == "tool"
    assert saved_payloads[1]["tool_call_id"] == "c1"
    assert response["tldw_tool_results"][0]["ok"] is True
    assert response["tldw_tool_results"][0]["tool_call_id"] == "c1"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_non_stream_autoexec_enabled_handles_mixed_results(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: True)
    monkeypatch.setattr(chat_service, "get_chat_max_tool_calls", lambda: 3)
    monkeypatch.setattr(chat_service, "get_chat_tool_timeout_ms", lambda: 5000)
    monkeypatch.setattr(chat_service, "get_chat_tool_allow_catalog", lambda: ["*"])
    monkeypatch.setattr(chat_service, "should_attach_tool_idempotency", lambda: False)

    async def fake_autoexec(**_kwargs):
        rec_ok = ToolExecutionRecord(
            tool_call_id="c1",
            tool_name="notes.search",
            ok=True,
            result={"ok": 1},
            module="notes",
            content='{"ok":true}',
        )
        rec_fail = ToolExecutionRecord(
            tool_call_id="c2",
            tool_name="notes.forbidden",
            ok=False,
            error="Permission denied",
            content='{"ok":false}',
        )
        return ToolExecutionBatchResult(
            requested_calls=2,
            processed_calls=2,
            execution_attempts=2,
            executed_calls=1,
            truncated=False,
            results=[rec_ok, rec_fail],
        )

    monkeypatch.setattr(chat_service, "execute_assistant_tool_calls", fake_autoexec)

    saved_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        saved_payloads.append(payload)
        return f"m-{len(saved_payloads)}"

    response = await _run_execute_non_stream_call(
        llm_call_func=_build_llm_response_with_tool_calls,
        save_message_fn=save_message_fn,
    )

    assert len(saved_payloads) == 3
    assert [p["role"] for p in saved_payloads] == ["assistant", "tool", "tool"]
    assert len(response["tldw_tool_results"]) == 2
    assert response["tldw_tool_results"][0]["ok"] is True
    assert response["tldw_tool_results"][1]["ok"] is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_non_stream_autoexec_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: True)
    monkeypatch.setattr(chat_service, "get_chat_max_tool_calls", lambda: 3)
    monkeypatch.setattr(chat_service, "get_chat_tool_timeout_ms", lambda: 5000)
    monkeypatch.setattr(chat_service, "get_chat_tool_allow_catalog", lambda: ["*"])
    monkeypatch.setattr(chat_service, "should_attach_tool_idempotency", lambda: False)

    async def fake_autoexec(**_kwargs):
        raise RuntimeError("autoexec failed")

    monkeypatch.setattr(chat_service, "execute_assistant_tool_calls", fake_autoexec)

    saved_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        saved_payloads.append(payload)
        return f"m-{len(saved_payloads)}"

    response = await _run_execute_non_stream_call(
        llm_call_func=_build_llm_response_with_tool_calls,
        save_message_fn=save_message_fn,
    )

    assert len(saved_payloads) == 1
    assert saved_payloads[0]["role"] == "assistant"
    assert "tldw_tool_results" not in response


@pytest.mark.asyncio
@pytest.mark.unit
async def test_non_stream_auto_continue_runs_once_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: True)
    monkeypatch.setattr(chat_service, "get_chat_max_tool_calls", lambda: 2)
    monkeypatch.setattr(chat_service, "get_chat_tool_timeout_ms", lambda: 3500)
    monkeypatch.setattr(chat_service, "get_chat_tool_allow_catalog", lambda: ["notes.*"])
    monkeypatch.setattr(chat_service, "should_attach_tool_idempotency", lambda: True)
    monkeypatch.setattr(chat_service, "should_auto_continue_tools_once", lambda: True)

    autoexec_called = {"count": 0}

    async def fake_autoexec(**_kwargs):
        autoexec_called["count"] += 1
        rec = ToolExecutionRecord(
            tool_call_id="c1",
            tool_name="notes.search",
            ok=True,
            result={"ok": 1},
            module="notes",
            content='{"ok":true}',
        )
        return ToolExecutionBatchResult(
            requested_calls=1,
            processed_calls=1,
            execution_attempts=1,
            executed_calls=1,
            truncated=False,
            results=[rec],
        )

    monkeypatch.setattr(chat_service, "execute_assistant_tool_calls", fake_autoexec)

    continuation_calls: list[dict[str, Any]] = []

    async def fake_followup_call(**kwargs):
        continuation_calls.append(kwargs)
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Final answer from continuation",
                        "tool_calls": [
                            {
                                "id": "c2",
                                "type": "function",
                                "function": {"name": "notes.other", "arguments": "{}"},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }

    monkeypatch.setattr(chat_service, "perform_chat_api_call_async", fake_followup_call)

    saved_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        saved_payloads.append(payload)
        return f"m-{len(saved_payloads)}"

    response = await _run_execute_non_stream_call(
        llm_call_func=_build_llm_response_with_tool_calls,
        save_message_fn=save_message_fn,
    )

    assert autoexec_called["count"] == 1
    assert len(continuation_calls) == 1
    continuation_messages = continuation_calls[0]["messages_payload"]
    assert continuation_messages[-2]["role"] == "assistant"
    assert continuation_messages[-2]["tool_calls"][0]["id"] == "c1"
    assert continuation_messages[-1]["role"] == "tool"
    assert continuation_messages[-1]["tool_call_id"] == "c1"

    assert [p["role"] for p in saved_payloads] == ["assistant", "tool", "assistant"]
    assert response["choices"][0]["message"]["content"] == "Final answer from continuation"
    assert response["tldw_tool_results"][0]["tool_call_id"] == "c1"
    assert response["tldw_tool_auto_continue"] == {"attempted": True, "succeeded": True}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_non_stream_auto_continue_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: True)
    monkeypatch.setattr(chat_service, "get_chat_max_tool_calls", lambda: 2)
    monkeypatch.setattr(chat_service, "get_chat_tool_timeout_ms", lambda: 3500)
    monkeypatch.setattr(chat_service, "get_chat_tool_allow_catalog", lambda: ["notes.*"])
    monkeypatch.setattr(chat_service, "should_attach_tool_idempotency", lambda: True)
    monkeypatch.setattr(chat_service, "should_auto_continue_tools_once", lambda: True)

    async def fake_autoexec(**_kwargs):
        rec = ToolExecutionRecord(
            tool_call_id="c1",
            tool_name="notes.search",
            ok=True,
            result={"ok": 1},
            module="notes",
            content='{"ok":true}',
        )
        return ToolExecutionBatchResult(
            requested_calls=1,
            processed_calls=1,
            execution_attempts=1,
            executed_calls=1,
            truncated=False,
            results=[rec],
        )

    monkeypatch.setattr(chat_service, "execute_assistant_tool_calls", fake_autoexec)

    async def fake_followup_call(**_kwargs):
        raise RuntimeError("continuation failed")

    monkeypatch.setattr(chat_service, "perform_chat_api_call_async", fake_followup_call)

    saved_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        saved_payloads.append(payload)
        return f"m-{len(saved_payloads)}"

    response = await _run_execute_non_stream_call(
        llm_call_func=_build_llm_response_with_tool_calls,
        save_message_fn=save_message_fn,
    )

    assert [p["role"] for p in saved_payloads] == ["assistant", "tool"]
    assert response["choices"][0]["message"]["content"] == "Calling tool"
    assert response["tldw_tool_auto_continue"] == {"attempted": True, "succeeded": False}
