from __future__ import annotations

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from starlette.responses import StreamingResponse

from tldw_Server_API.app.core.Chat import chat_service
from tldw_Server_API.app.core.Chat.chat_service import execute_streaming_call
from tldw_Server_API.app.core.Chat.tool_auto_exec import (
    ToolExecutionBatchResult,
    ToolExecutionRecord,
)


class _DummyStreamTracker:
    def add_heartbeat(self):
        return None

    def add_chunk(self):
        return None


class _DummyMetrics:
    def track_llm_call(self, *_args, **_kwargs):
        return None

    def track_provider_fallback_success(self, *_args, **_kwargs):
        return None

    def track_rate_limit(self, *_args, **_kwargs):
        return None

    def track_moderation_output(self, *_args, **_kwargs):
        return None

    def track_moderation_stream_block(self, *_args, **_kwargs):
        return None

    @asynccontextmanager
    async def track_streaming(self, *_args, **_kwargs):
        yield _DummyStreamTracker()


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


def _tool_call_stream() -> Any:
    def _stream() -> Any:
        tool_delta = {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "notes.search",
                                    "arguments": "{}",
                                },
                            }
                        ]
                    }
                }
            ]
        }
        yield f"data: {json.dumps(tool_delta)}\n\n"
        yield "data: [DONE]\n\n"

    return _stream()


async def _collect_sse_chunks(response: StreamingResponse) -> list[str]:
    chunks: list[str] = []
    agen = response.body_iterator
    try:
        async for chunk in agen:
            if isinstance(chunk, (bytes, bytearray)):
                chunks.append(chunk.decode("utf-8", errors="replace"))
            else:
                chunks.append(str(chunk))
    finally:
        with contextlib.suppress(Exception):
            await agen.aclose()
    return chunks


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_autoexec_enabled_persists_tool_messages_and_emits_tool_results_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_log_llm_usage(**_kwargs):
        return None

    monkeypatch.setattr(chat_service, "log_llm_usage", fake_log_llm_usage)
    monkeypatch.setattr(chat_service, "get_topic_monitoring_service", lambda: None)
    monkeypatch.setattr(chat_service, "should_auto_execute_tools", lambda: True)
    monkeypatch.setattr(chat_service, "get_chat_max_tool_calls", lambda: 2)
    monkeypatch.setattr(chat_service, "get_chat_tool_timeout_ms", lambda: 4321)
    monkeypatch.setattr(chat_service, "get_chat_tool_allow_catalog", lambda: ["notes.*"])
    monkeypatch.setattr(chat_service, "should_attach_tool_idempotency", lambda: True)

    captured_kwargs: dict[str, Any] = {}

    async def fake_autoexec(**kwargs):
        captured_kwargs.update(kwargs)
        rec = ToolExecutionRecord(
            tool_call_id="c1",
            tool_name="notes.search",
            ok=True,
            result={"ok": True},
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

    save_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        save_payloads.append(payload)
        return f"m-{len(save_payloads)}"

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/v1/chat/completions"),
        headers={},
        state=SimpleNamespace(user_id=7, api_key_id=None, team_ids=None, org_ids=None),
    )

    response = await execute_streaming_call(
        current_loop=asyncio.get_running_loop(),
        cleaned_args={
            "api_endpoint": "openai",
            "api_key": "test-key",
            "messages_payload": [{"role": "user", "content": "hi"}],
            "model": "gpt-4o-mini",
            "streaming": True,
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
        final_conversation_id="conv-stream-1",
        character_card_for_context={"name": "Test"},
        chat_db=SimpleNamespace(),
        save_message_fn=save_message_fn,
        audit_service=None,
        audit_context=None,
        client_id="client-1",
        queue_execution_enabled=False,
        enable_provider_fallback=False,
        llm_call_func=_tool_call_stream,
        refresh_provider_params=lambda *_args, **_kwargs: ({}, None),
        moderation_getter=lambda: _NoModeration(),
        assistant_parent_message_id="anchor-stream-1",
        continuation_metadata={
            "applied": True,
            "mode": "branch",
            "from_message_id": "anchor-stream-1",
        },
    )

    assert isinstance(response, StreamingResponse)
    chunks = await _collect_sse_chunks(response)

    assert captured_kwargs["max_tool_calls"] == 2
    assert captured_kwargs["timeout_ms"] == 4321
    assert captured_kwargs["allow_catalog"] == ["notes.*"]
    assert captured_kwargs["attach_idempotency"] is True
    assert len(save_payloads) == 2
    assert save_payloads[0]["role"] == "assistant"
    assert save_payloads[0]["parent_message_id"] == "anchor-stream-1"
    assert save_payloads[1]["role"] == "tool"
    assert save_payloads[1]["tool_call_id"] == "c1"

    tool_event_idx = next(i for i, msg in enumerate(chunks) if msg.startswith("event: tool_results"))
    finish_idx = next(i for i, msg in enumerate(chunks) if '"finish_reason": "stop"' in msg)
    end_idx = next(i for i, msg in enumerate(chunks) if msg.startswith("event: stream_end"))
    done_idx = next(i for i, msg in enumerate(chunks) if "data: [DONE]" in msg)
    assert tool_event_idx < finish_idx < end_idx < done_idx

    tool_data_line = next(line for line in chunks[tool_event_idx].splitlines() if line.startswith("data: "))
    payload = json.loads(tool_data_line[6:])
    assert payload["tool_results"][0]["tool_call_id"] == "c1"
    assert payload["tldw_conversation_id"] == "conv-stream-1"
    assert payload["tldw_message_id"] == "m-1"
    assert payload["tldw_continuation"]["mode"] == "branch"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_streaming_autoexec_disabled_does_not_emit_tool_results_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    save_payloads: list[dict[str, Any]] = []

    async def save_message_fn(_db, _conv_id, payload, use_transaction=True):
        save_payloads.append(payload)
        return f"m-{len(save_payloads)}"

    request = SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path="/api/v1/chat/completions"),
        headers={},
        state=SimpleNamespace(user_id=8, api_key_id=None, team_ids=None, org_ids=None),
    )

    response = await execute_streaming_call(
        current_loop=asyncio.get_running_loop(),
        cleaned_args={
            "api_endpoint": "openai",
            "api_key": "test-key",
            "messages_payload": [{"role": "user", "content": "hi"}],
            "model": "gpt-4o-mini",
            "streaming": True,
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
        final_conversation_id="conv-stream-2",
        character_card_for_context={"name": "Test"},
        chat_db=SimpleNamespace(),
        save_message_fn=save_message_fn,
        audit_service=None,
        audit_context=None,
        client_id="client-2",
        queue_execution_enabled=False,
        enable_provider_fallback=False,
        llm_call_func=_tool_call_stream,
        refresh_provider_params=lambda *_args, **_kwargs: ({}, None),
        moderation_getter=lambda: _NoModeration(),
    )

    assert isinstance(response, StreamingResponse)
    chunks = await _collect_sse_chunks(response)

    assert called["autoexec"] == 0
    assert len(save_payloads) == 1
    assert save_payloads[0]["role"] == "assistant"
    assert not any(msg.startswith("event: tool_results") for msg in chunks)
