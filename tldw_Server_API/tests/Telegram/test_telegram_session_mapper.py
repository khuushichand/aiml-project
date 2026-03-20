from __future__ import annotations

import uuid

from tldw_Server_API.app.core.Telegram.session_mapper import (
    build_telegram_session_key,
    derive_telegram_assistant_conversation_id,
    derive_telegram_character_conversation_id,
    derive_telegram_persona_session_id,
)


def test_build_telegram_session_key_for_dm():
    key = build_telegram_session_key(tenant_id="tenant-a", telegram_user_id=200)

    assert key == "tenant-a:dm:200"


def test_build_telegram_session_key_for_group_topic():
    key = build_telegram_session_key(
        tenant_id="tenant-a",
        telegram_chat_id=100,
        topic_or_thread_id=300,
        telegram_user_id=200,
    )

    assert key == "tenant-a:group:100:topic:300:user:200"


def test_assistant_conversation_id_is_stable_for_same_session_key():
    key = build_telegram_session_key(tenant_id="tenant-a", telegram_user_id=200)

    first = derive_telegram_assistant_conversation_id(key)
    second = derive_telegram_assistant_conversation_id(key)

    assert first == second
    assert uuid.UUID(first)


def test_persona_session_ids_differ_for_different_persona_ids():
    key = build_telegram_session_key(tenant_id="tenant-a", telegram_user_id=200)

    first = derive_telegram_persona_session_id(key, persona_id="persona-a")
    second = derive_telegram_persona_session_id(key, persona_id="persona-b")

    assert first != second
    assert uuid.UUID(first)
    assert uuid.UUID(second)


def test_character_conversation_ids_differ_for_different_character_ids():
    key = build_telegram_session_key(
        tenant_id="tenant-a",
        telegram_chat_id=100,
        topic_or_thread_id=300,
        telegram_user_id=200,
    )

    first = derive_telegram_character_conversation_id(key, character_id="character-a")
    second = derive_telegram_character_conversation_id(key, character_id="character-b")

    assert first != second
    assert uuid.UUID(first)
    assert uuid.UUID(second)


def test_conversation_backed_ids_are_uuid_safe():
    key = build_telegram_session_key(tenant_id="tenant-a", telegram_user_id=200)

    assistant_conversation_id = derive_telegram_assistant_conversation_id(key)
    persona_session_id = derive_telegram_persona_session_id(key, persona_id="persona-a")
    character_conversation_id = derive_telegram_character_conversation_id(key, character_id="character-a")

    assert uuid.UUID(assistant_conversation_id)
    assert uuid.UUID(persona_session_id)
    assert uuid.UUID(character_conversation_id)
