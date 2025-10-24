import pytest
from hypothesis import given, strategies as st

from tldw_Server_API.app.core.Character_Chat.modules.character_chat import (
    process_db_messages_to_rich_ui_history,
)
from tldw_Server_API.app.core.Character_Chat.modules.character_utils import (
    USER_SENDER_ALIASES,
    CHAR_SENDER_ALIASES,
    SYSTEM_ALIASES,
    TOOL_ALIASES,
)


def _non_character_aliases():
    # Include prefixed variations used by the pipeline (e.g., "system:notes", "tool:browser")
    base = list(SYSTEM_ALIASES | TOOL_ALIASES)
    prefixed = [
        f"system:{p}" for p in ["meta", "note", "debug"]
    ] + [
        f"tool:{p}" for p in ["search", "browser", "fn"]
    ]
    return base + prefixed


@given(
    char_name=st.text(min_size=1, max_size=12).filter(lambda s: s.strip() != ""),
    user_name=st.text(min_size=1, max_size=12).filter(lambda s: s.strip() != ""),
    greeting=st.text(min_size=3, max_size=120),
)
def test_first_message_prefers_character_when_matches_greeting(char_name, user_name, greeting):
    # Construct DB messages where first message equals char_first_message
    db_messages = [
        {"id": "m1", "sender": char_name, "content": greeting, "timestamp": 1, "version": 1},
        {"id": "m2", "sender": "user", "content": "Hi", "timestamp": 2, "version": 1},
    ]

    rich = process_db_messages_to_rich_ui_history(
        db_messages=db_messages,
        char_name_from_card=char_name,
        user_name_for_placeholders=user_name,
        actual_user_sender_id_in_db="User",
        actual_char_sender_id_in_db=char_name,
        additional_char_sender_ids=None,
        additional_user_sender_ids=None,
        char_first_message=greeting,
    )

    # First turn should contain the character message with the greeting
    assert len(rich) >= 1
    first = rich[0]
    # The first produced role should be a character message (not user, not non_character)
    assert first["character"] is not None
    assert first["character"]["content"]
    # Greeting content (processed) should be present
    assert greeting.strip() in first["character"]["content"]


@given(
    msgs=st.lists(
        st.fixed_dictionaries(
            {
                "id": st.uuids().map(str),
                "sender": st.sampled_from(_non_character_aliases()),
                "content": st.text(min_size=0, max_size=60),
                "timestamp": st.integers(min_value=0, max_value=1_000_000),
                "version": st.integers(min_value=1, max_value=5),
            }
        ),
        min_size=1,
        max_size=12,
    )
)
def test_system_and_tool_senders_map_to_non_character(msgs):
    # Ensure messages with system/tool aliases are always classified under non_character
    # Use a consistent char/user name that won't collide with system/tool aliases
    char_name = "Assistant"
    user_name = "User"

    rich = process_db_messages_to_rich_ui_history(
        db_messages=msgs,
        char_name_from_card=char_name,
        user_name_for_placeholders=user_name,
        actual_user_sender_id_in_db="User",
        actual_char_sender_id_in_db=char_name,
        additional_char_sender_ids=None,
        additional_user_sender_ids=None,
        char_first_message=None,
    )

    non_char_aliases_lower = {a.lower() for a in SYSTEM_ALIASES | TOOL_ALIASES}

    for turn in rich:
        # If a non_character message is present, its raw_sender must be a system/tool alias (or prefixed form)
        nc = turn.get("non_character")
        if not nc:
            continue
        raw = str(nc.get("raw_sender") or "").strip().lower()
        # Allow prefixed (system:..., tool:...)
        if not (raw in non_char_aliases_lower or any(raw.startswith(f"{p}:") for p in non_char_aliases_lower)):
            pytest.fail(f"non_character classification with unexpected raw_sender: {raw}")


@given(
    n=st.integers(min_value=1, max_value=8),
    user_texts=st.lists(st.text(min_size=1, max_size=40), min_size=8, max_size=16),
    char_texts=st.lists(st.text(min_size=1, max_size=40), min_size=8, max_size=16),
)
def test_alternating_user_and_character_produce_paired_turns(n, user_texts, char_texts):
    # Build an alternating sequence: user -> character -> user -> character ...
    char_name = "Assistant"
    user_name = "User"

    db_messages = []
    for i in range(n):
        db_messages.append({
            "id": f"u{i}",
            "sender": "user",
            "content": user_texts[i % len(user_texts)] or "hi",
            "timestamp": i * 2 + 1,
            "version": 1,
        })
        db_messages.append({
            "id": f"a{i}",
            "sender": char_name,
            "content": char_texts[i % len(char_texts)] or "hello",
            "timestamp": i * 2 + 2,
            "version": 1,
        })

    rich = process_db_messages_to_rich_ui_history(
        db_messages=db_messages,
        char_name_from_card=char_name,
        user_name_for_placeholders=user_name,
        actual_user_sender_id_in_db="User",
        actual_char_sender_id_in_db=char_name,
        additional_char_sender_ids=None,
        additional_user_sender_ids=None,
        char_first_message=None,
    )

    # We expect exactly n turns, each with both user and character content
    assert len(rich) == n
    for i, turn in enumerate(rich):
        assert turn["user"] is not None
        assert turn["character"] is not None
        assert isinstance(turn["user"]["content"], str)
        assert isinstance(turn["character"]["content"], str)


def test_overlapping_alias_resolves_with_additional_char_aliases():
    # Use 'player' which is part of USER_SENDER_ALIASES; mark it also as a char alias
    char_alias = "player"
    char_name = "NarrativeAI"
    user_name = "User"

    db_messages = [
        {"id": "m1", "sender": "user", "content": "Hi", "timestamp": 1, "version": 1},
        {"id": "m2", "sender": char_alias, "content": "Welcome", "timestamp": 2, "version": 1},
    ]

    rich = process_db_messages_to_rich_ui_history(
        db_messages=db_messages,
        char_name_from_card=char_name,
        user_name_for_placeholders=user_name,
        actual_user_sender_id_in_db="User",
        actual_char_sender_id_in_db=char_name,
        additional_char_sender_ids=[char_alias],
        additional_user_sender_ids=None,
        char_first_message=None,
    )

    assert len(rich) >= 1
    # Second turn produced due to char message after user
    # Ensure the second turn contains a character message (not misclassified as user)
    found_char = any(t.get("character") and "Welcome" in (t["character"]["content"] or "") for t in rich)
    assert found_char, "Expected 'player' alias to be treated as character via additional_char_sender_ids"


def test_interrupted_by_system_message_produces_non_character_turn():
    char_name = "Assistant"
    user_name = "User"

    db_messages = [
        {"id": "m1", "sender": "user", "content": "Hello", "timestamp": 1, "version": 1},
        {"id": "m2", "sender": "system", "content": "note", "timestamp": 2, "version": 1},
        {"id": "m3", "sender": char_name, "content": "Hi there", "timestamp": 3, "version": 1},
    ]

    rich = process_db_messages_to_rich_ui_history(
        db_messages=db_messages,
        char_name_from_card=char_name,
        user_name_for_placeholders=user_name,
        actual_user_sender_id_in_db="User",
        actual_char_sender_id_in_db=char_name,
        additional_char_sender_ids=None,
        additional_user_sender_ids=None,
        char_first_message=None,
    )

    # Expect at least two turns: first turn includes user + non_character, second includes character
    assert len(rich) >= 2
    assert rich[0]["user"] is not None
    assert rich[0]["non_character"] is not None
    assert rich[1]["character"] is not None
