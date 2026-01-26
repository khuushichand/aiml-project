import os
import tempfile

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB
from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import DEFAULT_CHARACTER_NAME


@pytest.mark.unit
def test_batch_message_counts_and_keywords():
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
            }
        )
        conv_a = db.add_conversation({"character_id": char_id, "title": "Conv A", "client_id": "test_client"})
        conv_b = db.add_conversation({"character_id": char_id, "title": "Conv B", "client_id": "test_client"})

        db.add_message({"conversation_id": conv_a, "sender": "user", "content": "a1", "client_id": "test_client"})
        db.add_message({"conversation_id": conv_a, "sender": "assistant", "content": "a2", "client_id": "test_client"})
        db.add_message({"conversation_id": conv_b, "sender": "user", "content": "b1", "client_id": "test_client"})

        kw_alpha = db.add_keyword("alpha")
        kw_beta = db.add_keyword("beta")
        db.link_conversation_to_keyword(conv_a, kw_alpha)
        db.link_conversation_to_keyword(conv_b, kw_beta)

        counts = db.count_messages_for_conversations([conv_a, conv_b])
        assert counts.get(conv_a) == 2
        assert counts.get(conv_b) == 1

        keyword_map = db.get_keywords_for_conversations([conv_a, conv_b])
        alpha_keywords = [k.get("keyword") for k in keyword_map.get(conv_a, [])]
        beta_keywords = [k.get("keyword") for k in keyword_map.get(conv_b, [])]
        assert "alpha" in alpha_keywords
        assert "beta" in beta_keywords
    finally:
        try:
            os.unlink(db_path)
            if os.path.exists(db_path + "-wal"):
                os.unlink(db_path + "-wal")
            if os.path.exists(db_path + "-shm"):
                os.unlink(db_path + "-shm")
        except Exception:
            pass
