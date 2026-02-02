import asyncio

import pytest

from tldw_Server_API.app.api.v1.endpoints.chat import _save_message_turn_to_db
from tldw_Server_API.app.api.v1.schemas.chat_request_schemas import ChatCompletionRequest
from tldw_Server_API.app.core.Chat.chat_metrics import get_chat_metrics
from tldw_Server_API.app.core.Chat.chat_service import build_context_and_messages


@pytest.mark.asyncio
async def test_history_dedup_when_request_includes_history(populated_chacha_db):
    loop = asyncio.get_running_loop()
    metrics = get_chat_metrics()

    characters = populated_chacha_db.list_character_cards()
    assert characters
    convs = []
    for character in characters:
        convs = populated_chacha_db.get_conversations_for_character(character["id"])
        if convs:
            break
    assert convs
    conv_id = convs[0]["id"]

    before_msgs = populated_chacha_db.get_messages_for_conversation(
        conv_id,
        limit=100,
        order_by_timestamp="ASC",
    )
    assert len(before_msgs) == 2

    req = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        conversation_id=conv_id,
        save_to_db=True,
        messages=[
            {"role": "user", "content": "Hello, how are you?"},
            {
                "role": "assistant",
                "content": "I'm doing well, thank you! How can I help you today?",
            },
            {"role": "user", "content": "What's next?"},
        ],
    )

    _, _, _, _, llm_messages, _ = await build_context_and_messages(
        chat_db=populated_chacha_db,
        request_data=req,
        loop=loop,
        metrics=metrics,
        default_save_to_db=False,
        final_conversation_id=conv_id,
        save_message_fn=_save_message_turn_to_db,
    )

    # Expect history + new message without duplication
    assert len(llm_messages) == 3
    assert llm_messages[-1].get("content") == "What's next?"

    after_msgs = populated_chacha_db.get_messages_for_conversation(
        conv_id,
        limit=100,
        order_by_timestamp="ASC",
    )
    # Only the new message should be persisted
    assert len(after_msgs) == len(before_msgs) + 1


@pytest.mark.asyncio
async def test_history_dedup_user_only_enabled(populated_chacha_db, monkeypatch):
    monkeypatch.setenv("CHAT_TRIM_USER_ONLY_OVERLAP", "1")
    loop = asyncio.get_running_loop()
    metrics = get_chat_metrics()

    characters = populated_chacha_db.list_character_cards()
    assert characters
    convs = []
    for character in characters:
        convs = populated_chacha_db.get_conversations_for_character(character["id"])
        if convs:
            break
    assert convs
    conv_id = convs[0]["id"]

    # Add a trailing user message so the history ends with a user turn
    populated_chacha_db.add_message({
        "conversation_id": conv_id,
        "sender": "user",
        "content": "Tail user",
    })

    before_msgs = populated_chacha_db.get_messages_for_conversation(
        conv_id,
        limit=100,
        order_by_timestamp="ASC",
    )

    req = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        conversation_id=conv_id,
        save_to_db=True,
        history_message_order="asc",
        messages=[
            {"role": "user", "content": "Tail user"},
        ],
    )

    _, _, _, _, llm_messages, _ = await build_context_and_messages(
        chat_db=populated_chacha_db,
        request_data=req,
        loop=loop,
        metrics=metrics,
        default_save_to_db=False,
        final_conversation_id=conv_id,
        save_message_fn=_save_message_turn_to_db,
    )

    # Payload should not include a duplicated current turn
    assert llm_messages
    after_msgs = populated_chacha_db.get_messages_for_conversation(
        conv_id,
        limit=100,
        order_by_timestamp="ASC",
    )
    # No new message should be persisted
    assert len(after_msgs) == len(before_msgs)


@pytest.mark.asyncio
async def test_history_dedup_user_only_disabled(populated_chacha_db, monkeypatch):
    monkeypatch.setenv("CHAT_TRIM_USER_ONLY_OVERLAP", "0")
    loop = asyncio.get_running_loop()
    metrics = get_chat_metrics()

    characters = populated_chacha_db.list_character_cards()
    assert characters
    convs = []
    for character in characters:
        convs = populated_chacha_db.get_conversations_for_character(character["id"])
        if convs:
            break
    assert convs
    conv_id = convs[0]["id"]

    # Add a trailing user message so the history ends with a user turn
    populated_chacha_db.add_message({
        "conversation_id": conv_id,
        "sender": "user",
        "content": "Tail user",
    })

    before_msgs = populated_chacha_db.get_messages_for_conversation(
        conv_id,
        limit=100,
        order_by_timestamp="ASC",
    )

    req = ChatCompletionRequest(
        model="gpt-3.5-turbo",
        conversation_id=conv_id,
        save_to_db=True,
        history_message_order="asc",
        messages=[
            {"role": "user", "content": "Tail user"},
        ],
    )

    _, _, _, _, llm_messages, _ = await build_context_and_messages(
        chat_db=populated_chacha_db,
        request_data=req,
        loop=loop,
        metrics=metrics,
        default_save_to_db=False,
        final_conversation_id=conv_id,
        save_message_fn=_save_message_turn_to_db,
    )

    assert llm_messages
    after_msgs = populated_chacha_db.get_messages_for_conversation(
        conv_id,
        limit=100,
        order_by_timestamp="ASC",
    )
    # Duplicate user message is persisted when trimming is disabled
    assert len(after_msgs) == len(before_msgs) + 1
