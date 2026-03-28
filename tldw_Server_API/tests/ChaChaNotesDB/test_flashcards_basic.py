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


def test_deck_workspace_id_persists_and_can_move_between_scopes():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "ChaChaNotes.db")
        db = CharactersRAGDB(db_path, client_id="test")
        db.upsert_workspace("ws-1", "Workspace One")

        deck_id = db.add_deck("Scoped Deck", "desc", workspace_id="ws-1")
        deck = db.get_deck(deck_id)
        assert deck is not None
        assert deck["workspace_id"] == "ws-1"

        default_items = db.list_decks(limit=20, offset=0)
        assert all(item["id"] != deck_id for item in default_items)

        workspace_items = db.list_decks(workspace_id="ws-1", limit=20, offset=0)
        assert [item["id"] for item in workspace_items] == [deck_id]

        all_items = db.list_decks(include_workspace_items=True, limit=20, offset=0)
        assert any(item["id"] == deck_id for item in all_items)

        assert db.update_deck(deck_id, workspace_id=None, expected_version=deck["version"]) is True
        moved_to_general = db.get_deck(deck_id)
        assert moved_to_general is not None
        assert moved_to_general["workspace_id"] is None

        general_items = db.list_decks(limit=20, offset=0)
        assert any(item["id"] == deck_id for item in general_items)

        assert db.update_deck(deck_id, workspace_id="ws-1", expected_version=moved_to_general["version"]) is True
        moved_back = db.get_deck(deck_id)
        assert moved_back is not None
        assert moved_back["workspace_id"] == "ws-1"
