import asyncio

import pytest

from tldw_Server_API.app.api.v1.endpoints.chat import _save_message_turn_to_db
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.chat_metrics import get_chat_metrics
from tldw_Server_API.app.core.Chat.chat_service import build_context_and_messages


@pytest.mark.asyncio
async def test_tool_message_persisted_and_rehydrated(populated_chacha_db):
    loop = asyncio.get_running_loop()
    metrics = get_chat_metrics()

    req1 = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "user", "content": "Hi"},
            {"role": "tool", "content": "Tool output", "tool_call_id": "call-123"},
        ],
        save_to_db=True,
    )

    _, _, conv_id, _, _, _ = await build_context_and_messages(
        chat_db=populated_chacha_db,
        request_data=req1,
        loop=loop,
        metrics=metrics,
        default_save_to_db=False,
        final_conversation_id=None,
        save_message_fn=_save_message_turn_to_db,
    )

    req2 = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Next"}],
        conversation_id=conv_id,
        save_to_db=True,
    )

    _, _, _, _, llm_messages2, _ = await build_context_and_messages(
        chat_db=populated_chacha_db,
        request_data=req2,
        loop=loop,
        metrics=metrics,
        default_save_to_db=False,
        final_conversation_id=conv_id,
        save_message_fn=_save_message_turn_to_db,
    )

    tool_msgs = [m for m in llm_messages2 if m.get("role") == "tool"]
    assert tool_msgs
    assert tool_msgs[0].get("tool_call_id") == "call-123"
    assert tool_msgs[0].get("content") == "Tool output"
