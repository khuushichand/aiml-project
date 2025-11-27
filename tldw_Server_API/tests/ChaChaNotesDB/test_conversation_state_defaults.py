import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB, InputError


pytestmark = pytest.mark.unit


def test_add_conversation_defaults_to_in_progress(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")

    conv_id = db.add_conversation(
        {"character_id": 1, "title": "Test chat", "root_id": "root-1", "client_id": "user-1"}
    )
    conv = db.get_conversation_by_id(conv_id)

    assert conv is not None
    assert conv.get("state") == "in-progress"


def test_update_conversation_validates_state(tmp_path):
    db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")

    conv_id = db.add_conversation(
        {"character_id": 1, "title": "Test chat", "root_id": "root-1", "client_id": "user-1"}
    )
    conv = db.get_conversation_by_id(conv_id)
    assert conv is not None

    with pytest.raises(InputError):
        db.update_conversation(conv_id, {"state": ""}, conv.get("version", 1))

    db.update_conversation(conv_id, {"state": "resolved"}, conv.get("version", 1))
    updated = db.get_conversation_by_id(conv_id)
    assert updated is not None
    assert updated.get("state") == "resolved"
