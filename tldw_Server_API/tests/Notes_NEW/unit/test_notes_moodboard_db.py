import sqlite3

import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
)


@pytest.fixture()
def moodboard_db(tmp_path):
    db_path = tmp_path / "moodboard_management.db"
    db = CharactersRAGDB(str(db_path), client_id="moodboard_unit_test")
    yield db
    try:
        db.close()
    except Exception:
        _ = None


def test_moodboard_schema_tables_exist_after_init(moodboard_db: CharactersRAGDB):
    conn = moodboard_db.get_connection()
    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('moodboards', 'moodboard_notes')"
        ).fetchall()
    }
    assert {"moodboards", "moodboard_notes"}.issubset(tables)

    indexes = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()
    }
    assert "idx_moodboard_notes_board" in indexes
    assert "idx_moodboard_notes_note" in indexes


def test_moodboard_crud_roundtrip(moodboard_db: CharactersRAGDB):
    moodboard_id = moodboard_db.add_moodboard(
        name="Visual Research",
        description="Inspiration board",
        smart_rule={"query": "camera", "keyword_tokens": ["design"]},
    )
    assert moodboard_id is not None

    created = moodboard_db.get_moodboard_by_id(moodboard_id)
    assert created is not None
    assert created["name"] == "Visual Research"
    assert created["smart_rule"]["query"] == "camera"
    assert created["version"] == 1

    listing = moodboard_db.list_moodboards(limit=20, offset=0)
    assert any(int(item["id"]) == int(moodboard_id) for item in listing)

    updated = moodboard_db.update_moodboard(
        moodboard_id=moodboard_id,
        update_data={"name": "Visual Research Updated", "description": "Updated"},
        expected_version=int(created["version"]),
    )
    assert updated is True

    after_update = moodboard_db.get_moodboard_by_id(moodboard_id)
    assert after_update is not None
    assert after_update["name"] == "Visual Research Updated"
    assert int(after_update["version"]) == 2

    deleted = moodboard_db.delete_moodboard(moodboard_id=moodboard_id, expected_version=int(after_update["version"]))
    assert deleted is True
    assert moodboard_db.get_moodboard_by_id(moodboard_id) is None

    deleted_view = moodboard_db.list_moodboards(limit=20, offset=0, include_deleted=True)
    deleted_row = next((row for row in deleted_view if int(row["id"]) == int(moodboard_id)), None)
    assert deleted_row is not None
    assert bool(deleted_row["deleted"]) is True


def test_moodboard_pin_unpin_is_idempotent(moodboard_db: CharactersRAGDB):
    note_id = moodboard_db.add_note(title="Pinned note", content="content")
    moodboard_id = moodboard_db.add_moodboard(name="Pins")
    assert note_id
    assert moodboard_id is not None

    first_pin = moodboard_db.link_note_to_moodboard(moodboard_id=moodboard_id, note_id=note_id)
    second_pin = moodboard_db.link_note_to_moodboard(moodboard_id=moodboard_id, note_id=note_id)
    assert first_pin is True
    assert second_pin is False

    rows = moodboard_db.list_moodboard_notes(moodboard_id=moodboard_id, limit=20, offset=0)
    assert len(rows) == 1
    assert rows[0]["id"] == note_id
    assert rows[0]["membership_source"] == "manual"

    first_unpin = moodboard_db.unlink_note_from_moodboard(moodboard_id=moodboard_id, note_id=note_id)
    second_unpin = moodboard_db.unlink_note_from_moodboard(moodboard_id=moodboard_id, note_id=note_id)
    assert first_unpin is True
    assert second_unpin is False


def test_moodboard_manual_and_smart_union_sources(moodboard_db: CharactersRAGDB):
    note_manual = moodboard_db.add_note(title="Manual only", content="A")
    note_smart = moodboard_db.add_note(title="Smart only", content="B")
    note_both = moodboard_db.add_note(title="Both membership", content="C")
    assert note_manual and note_smart and note_both

    keyword_id = moodboard_db.add_keyword("palette")
    assert keyword_id is not None

    assert moodboard_db.link_note_to_keyword(note_smart, keyword_id) is True
    assert moodboard_db.link_note_to_keyword(note_both, keyword_id) is True

    moodboard_id = moodboard_db.add_moodboard(
        name="Hybrid",
        smart_rule={"keyword_tokens": ["palette"]},
    )
    assert moodboard_id is not None

    assert moodboard_db.link_note_to_moodboard(moodboard_id, note_manual) is True
    assert moodboard_db.link_note_to_moodboard(moodboard_id, note_both) is True

    notes = moodboard_db.list_moodboard_notes(moodboard_id=moodboard_id, limit=50, offset=0)
    by_id = {row["id"]: row for row in notes}

    assert set(by_id.keys()) == {note_manual, note_smart, note_both}
    assert by_id[note_manual]["membership_source"] == "manual"
    assert by_id[note_smart]["membership_source"] == "smart"
    assert by_id[note_both]["membership_source"] == "both"
