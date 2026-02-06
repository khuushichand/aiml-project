"""Regression coverage for character_cards FTS bootstrap on fresh DBs."""

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.mark.unit
def test_default_assistant_update_does_not_fail_with_malformed_fts(tmp_path):
    """Fresh DB should allow updating the schema-seeded Default Assistant row."""
    db_path = tmp_path / "chacha_fts_bootstrap.db"
    db = CharactersRAGDB(db_path=str(db_path), client_id="test_client")
    try:
        default_character = db.get_character_card_by_name("Default Assistant")
        assert default_character is not None

        expected_version = int(default_character["version"])
        updated = db.update_character_card(
            int(default_character["id"]),
            {"first_message": "fts-bootstrap-regression-check"},
            expected_version=expected_version,
        )
        assert updated is True

        refreshed = db.get_character_card_by_id(int(default_character["id"]))
        assert refreshed is not None
        assert refreshed["first_message"] == "fts-bootstrap-regression-check"
        assert int(refreshed["version"]) == expected_version + 1

        # FTS lookup should include the schema-seeded default row.
        conn = db.get_connection()
        matches = conn.execute(
            "SELECT rowid FROM character_cards_fts WHERE character_cards_fts MATCH ?",
            ("default",),
        ).fetchall()
        assert any(int(row[0]) == int(default_character["id"]) for row in matches)
    finally:
        db.close_all_connections()
