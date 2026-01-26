import os
import tempfile
import asyncio

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME
from tldw_Server_API.app.api.v1.endpoints import chat as chat_endpoint


@pytest.mark.asyncio
async def test_system_message_insert_is_serialized():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    db = CharactersRAGDB(db_path, "test_client")
    try:
        char_id = db.add_character_card(
            {
                "name": DEFAULT_CHARACTER_NAME,
                "description": "Default",
                "personality": "Helpful",
                "scenario": "Testing",
                "system_prompt": "You are helpful",
                "first_message": "Hello",
                "creator_notes": "test",
                "client_id": "test_client",
            }
        )
        conv_id = db.add_conversation(
            {"character_id": char_id, "title": "Conv", "client_id": "test_client"}
        )
        loop = asyncio.get_running_loop()

        async def _attempt():
            return await chat_endpoint._persist_system_message_if_needed(
                db=db,
                conversation_id=conv_id,
                system_message="System prompt",
                save_message_fn=chat_endpoint._save_message_turn_to_db,
                loop=loop,
            )

        await asyncio.gather(_attempt(), _attempt())
        msgs = db.get_messages_for_conversation(conv_id, limit=50, offset=0, order_by_timestamp="ASC")
        system_msgs = [m for m in msgs if m.get("sender") == "system"]
        assert len(system_msgs) == 1
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"):
                os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"):
                os.unlink(db_path + "-shm")
        except Exception:
            pass
