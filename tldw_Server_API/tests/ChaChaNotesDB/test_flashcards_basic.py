import os
import tempfile
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


def test_flashcards_basic_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ChaChaNotes.db")
        db = CharactersRAGDB(db_path, client_id="test")

        # Schema version should be 5
        conn = db.get_connection()
        ver = conn.execute("SELECT version FROM db_schema_version WHERE schema_name='rag_char_chat_schema'").fetchone()
        assert ver and ver[0] >= 5

        # Create deck
        deck_id = db.add_deck("Test Deck", "desc")
        assert isinstance(deck_id, int)

        # Create card
        card_uuid = db.add_flashcard({
            "deck_id": deck_id,
            "front": "What is 2+2?",
            "back": "4",
            "tags_json": "[\"math\"]",
        })
        assert isinstance(card_uuid, str)

        # List and find it
        items = db.list_flashcards(deck_id=deck_id, limit=10)
        assert any(i["uuid"] == card_uuid for i in items)

        # Review with rating 4
        updated = db.review_flashcard(card_uuid, rating=4)
        assert updated["interval_days"] >= 1
        assert updated["due_at"] is not None

        # Export contains content
        data = db.export_flashcards_csv(deck_id=deck_id)
        text = data.decode("utf-8")
        assert "What is 2+2?" in text
