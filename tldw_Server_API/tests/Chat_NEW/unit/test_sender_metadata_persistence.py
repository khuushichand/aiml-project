import pytest

from tldw_Server_API.app.api.v1.endpoints.chat import _save_message_turn_to_db
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME


@pytest.mark.asyncio
async def test_sender_role_and_name_metadata_persisted(populated_chacha_db):
    char = populated_chacha_db.get_character_card_by_name(DEFAULT_CHARACTER_NAME)
    assert char
    conv_id = populated_chacha_db.add_conversation({"title": "Meta Conversation", "character_id": char["id"]})

    message = {
        "role": "system",
        "content": "System instruction",
        "name": "system-command",
    }

    msg_id = await _save_message_turn_to_db(
        populated_chacha_db,
        conv_id,
        message,
        use_transaction=False,
    )
    assert msg_id

    meta = populated_chacha_db.get_message_metadata(msg_id)
    assert meta
    extra = meta.get("extra") or {}
    assert extra.get("sender_role") == "system"
    assert extra.get("sender_name") == "system-command"

    msg = populated_chacha_db.get_message_by_id(msg_id)
    assert msg
    assert msg.get("sender") == "system"
