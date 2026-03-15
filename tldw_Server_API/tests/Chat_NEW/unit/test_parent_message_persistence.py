import pytest

from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME
from tldw_Server_API.app.api.v1.endpoints.chat import _save_message_turn_to_db


@pytest.mark.asyncio
@pytest.mark.unit
async def test_save_message_turn_persists_parent_message_id(populated_chacha_db) -> None:
    char = populated_chacha_db.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
    assert char
    conv_id = populated_chacha_db.add_conversation(
        {"character_id": char["id"], "title": "parent-link"}
    )

    parent_id = populated_chacha_db.add_message(
        {
            "conversation_id": conv_id,
            "sender": "user",
            "content": "A",
        }
    )

    msg_id = await _save_message_turn_to_db(
        populated_chacha_db,
        conv_id,
        {
            "role": "assistant",
            "content": "B",
            "parent_message_id": parent_id,
        },
        use_transaction=True,
    )

    assert msg_id
    saved = populated_chacha_db.get_message_by_id(msg_id)
    assert saved
    assert saved.get("parent_message_id") == parent_id
