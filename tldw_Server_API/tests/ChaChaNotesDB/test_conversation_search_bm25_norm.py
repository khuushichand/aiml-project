import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


pytestmark = pytest.mark.unit


def test_conversation_search_global_bm25_normalization(tmp_path):


     db_path = tmp_path / "chacha.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="user-1")

    conv_ids = []
    conv_ids.append(
        db.add_conversation(
            {
                "id": "c1",
                "root_id": "c1",
                "character_id": 1,
                "title": "alpha alpha alpha",
                "client_id": "user-1",
            }
        )
    )
    conv_ids.append(
        db.add_conversation(
            {
                "id": "c2",
                "root_id": "c2",
                "character_id": 1,
                "title": "alpha beta",
                "client_id": "user-1",
            }
        )
    )
    conv_ids.append(
        db.add_conversation(
            {
                "id": "c3",
                "root_id": "c3",
                "character_id": 1,
                "title": "gamma only",
                "client_id": "user-1",
            }
        )
    )

    full = db.search_conversations_by_title("alpha", limit=3, offset=0)
    assert len(full) >= 2
    assert full[0].get("bm25_norm") is not None
    assert pytest.approx(1.0, rel=1e-6) == full[0].get("bm25_norm")

    page0 = db.search_conversations_by_title("alpha", limit=1, offset=0)
    page1 = db.search_conversations_by_title("alpha", limit=1, offset=1)

    assert page0[0]["id"] == full[0]["id"]
    assert page0[0]["bm25_norm"] == full[0]["bm25_norm"]
    assert page1[0]["id"] == full[1]["id"]
    assert page1[0]["bm25_norm"] == full[1]["bm25_norm"]
    assert page1[0]["bm25_norm"] < 1.0
