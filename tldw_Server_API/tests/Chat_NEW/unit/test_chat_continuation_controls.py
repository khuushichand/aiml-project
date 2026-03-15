import asyncio
from typing import Any

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME
from tldw_Server_API.app.api.v1.endpoints.chat import _save_message_turn_to_db
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.chat_metrics import get_chat_metrics
from tldw_Server_API.app.core.Chat.chat_service import build_context_and_messages


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n".join(part for part in text_parts if part).strip()
    return ""


@pytest.mark.asyncio
@pytest.mark.unit
async def test_continuation_branch_uses_anchor_chain(populated_chacha_db) -> None:
    char = populated_chacha_db.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
    assert char
    conv_id = populated_chacha_db.add_conversation(
        {"character_id": char["id"], "title": "Continuation Branch Conversation"}
    )

    root_id = populated_chacha_db.add_message(
        {"conversation_id": conv_id, "sender": "user", "content": "root-msg"}
    )
    anchor_id = populated_chacha_db.add_message(
        {
            "conversation_id": conv_id,
            "sender": "assistant",
            "content": "anchor-msg",
            "parent_message_id": root_id,
        }
    )
    populated_chacha_db.add_message(
        {
            "conversation_id": conv_id,
            "sender": "user",
            "content": "tip-msg",
            "parent_message_id": anchor_id,
        }
    )
    populated_chacha_db.add_message(
        {
            "conversation_id": conv_id,
            "sender": "assistant",
            "content": "sibling-msg",
            "parent_message_id": root_id,
        }
    )

    request_data = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        conversation_id=conv_id,
        history_message_limit=100,
        history_message_order="asc",
        save_to_db=False,
        messages=[{"role": "user", "content": "continue-from-anchor"}],
        tldw_continuation={
            "from_message_id": anchor_id,
            "mode": "branch",
        },
    )

    loop = asyncio.get_running_loop()
    metrics = get_chat_metrics()
    _, _, _, _, llm_payload_messages, _ = await build_context_and_messages(
        chat_db=populated_chacha_db,
        request_data=request_data,
        loop=loop,
        metrics=metrics,
        default_save_to_db=False,
        final_conversation_id=conv_id,
        save_message_fn=_save_message_turn_to_db,
    )

    text_messages = [_message_text(msg) for msg in llm_payload_messages]
    assert "root-msg" in text_messages
    assert "anchor-msg" in text_messages
    assert "tip-msg" not in text_messages
    assert "sibling-msg" not in text_messages


@pytest.mark.asyncio
@pytest.mark.unit
async def test_continuation_append_requires_tip(populated_chacha_db) -> None:
    char = populated_chacha_db.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
    assert char
    conv_id = populated_chacha_db.add_conversation(
        {"character_id": char["id"], "title": "Continuation Append Conversation"}
    )

    root_id = populated_chacha_db.add_message(
        {"conversation_id": conv_id, "sender": "user", "content": "append-root"}
    )
    anchor_id = populated_chacha_db.add_message(
        {
            "conversation_id": conv_id,
            "sender": "assistant",
            "content": "append-anchor",
            "parent_message_id": root_id,
        }
    )
    populated_chacha_db.add_message(
        {
            "conversation_id": conv_id,
            "sender": "assistant",
            "content": "append-latest",
            "parent_message_id": root_id,
        }
    )

    request_data = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        conversation_id=conv_id,
        history_message_limit=100,
        history_message_order="asc",
        save_to_db=False,
        messages=[{"role": "user", "content": "append-request"}],
        tldw_continuation={
            "from_message_id": anchor_id,
            "mode": "append",
        },
    )

    loop = asyncio.get_running_loop()
    metrics = get_chat_metrics()
    with pytest.raises(HTTPException) as exc_info:
        await build_context_and_messages(
            chat_db=populated_chacha_db,
            request_data=request_data,
            loop=loop,
            metrics=metrics,
            default_save_to_db=False,
            final_conversation_id=conv_id,
            save_message_fn=_save_message_turn_to_db,
        )

    assert exc_info.value.status_code == 409
