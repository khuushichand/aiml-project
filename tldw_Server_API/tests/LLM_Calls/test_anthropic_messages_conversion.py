import pytest

from tldw_Server_API.app.core.LLM_Calls.anthropic_messages import (
    anthropic_messages_to_openai,
    anthropic_tool_choice_to_openai,
    openai_response_to_anthropic,
    openai_stream_to_anthropic,
)


def test_anthropic_messages_to_openai_tool_handling():
    messages = [
        {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tool_1", "name": "search", "input": {"q": "x"}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tool_1", "content": [{"type": "text", "text": "ok"}]},
            ],
        },
    ]

    openai_messages, system_message = anthropic_messages_to_openai(messages, None)

    assert system_message is None
    assert openai_messages[0]["role"] == "user"
    assert openai_messages[1]["role"] == "assistant"
    assert "tool_calls" in openai_messages[1]
    assert openai_messages[2]["role"] == "tool"
    assert openai_messages[2]["tool_call_id"] == "tool_1"


def test_openai_response_to_anthropic_maps_tool_calls():
    response = {
        "id": "chatcmpl-1",
        "model": "gpt-4",
        "choices": [
            {
                "message": {
                    "content": "hello",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {"name": "search", "arguments": "{\"q\": \"x\"}"},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1},
    }

    payload = openai_response_to_anthropic(response, model="gpt-4")

    assert payload["type"] == "message"
    assert payload["role"] == "assistant"
    assert any(block["type"] == "tool_use" for block in payload["content"])
    assert payload["usage"]["input_tokens"] == 2
    assert payload["usage"]["output_tokens"] == 1


def test_anthropic_tool_choice_any_maps_to_required():
    assert anthropic_tool_choice_to_openai("any") == "required"
    assert anthropic_tool_choice_to_openai({"type": "any"}) == "required"


@pytest.mark.asyncio
async def test_openai_stream_to_anthropic_emits_events():
    async def _stream():
        yield 'data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": null}]}\n\n'
        yield 'data: {"choices": [{"delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}\n\n'

    chunks = [chunk async for chunk in openai_stream_to_anthropic(_stream(), model="gpt-4")]

    assert any("event: message_start" in chunk for chunk in chunks)
    assert any("event: content_block_delta" in chunk for chunk in chunks)
    assert any("event: message_stop" in chunk for chunk in chunks)


@pytest.mark.asyncio
async def test_openai_stream_to_anthropic_closes_stream():
    class _ClosableStream:
        def __init__(self, items):
            self._items = list(items)
            self.closed = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

        async def aclose(self):
            self.closed = True

    stream = _ClosableStream(
        [
            'data: {"choices": [{"delta": {"content": "Hello"}, "finish_reason": null}]}\n\n',
            'data: {"choices": [{"delta": {}, "finish_reason": "stop"}]}\n\n',
            'data: {"choices": [{"delta": {"content": "ignored"}, "finish_reason": null}]}\n\n',
        ]
    )

    chunks = [chunk async for chunk in openai_stream_to_anthropic(stream, model="gpt-4")]

    assert any("event: message_stop" in chunk for chunk in chunks)
    assert stream.closed is True
