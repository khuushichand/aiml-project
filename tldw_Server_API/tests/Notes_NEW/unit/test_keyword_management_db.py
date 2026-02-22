import pytest

from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import (
    CharactersRAGDB,
    ConflictError,
)


@pytest.fixture()
def keyword_db(tmp_path):
    db_path = tmp_path / "keyword_management.db"
    db = CharactersRAGDB(str(db_path), client_id="keyword_unit_test")
    yield db
    try:
        db.close()
    except Exception:
        _ = None


def test_rename_keyword_updates_text_and_conflicts_on_duplicate(keyword_db: CharactersRAGDB):
    alpha_id = keyword_db.add_keyword("alpha")
    beta_id = keyword_db.add_keyword("beta")
    assert alpha_id is not None
    assert beta_id is not None

    alpha_before = keyword_db.get_keyword_by_id(alpha_id)
    assert alpha_before is not None

    renamed = keyword_db.rename_keyword(
        keyword_id=alpha_id,
        new_keyword_text="alpha-renamed",
        expected_version=int(alpha_before["version"]),
    )
    assert renamed["keyword"] == "alpha-renamed"
    assert int(renamed["version"]) == int(alpha_before["version"]) + 1

    with pytest.raises(ConflictError):
        keyword_db.rename_keyword(
            keyword_id=alpha_id,
            new_keyword_text="beta",
            expected_version=int(renamed["version"]),
        )


def test_merge_keywords_moves_note_links_and_soft_deletes_source(keyword_db: CharactersRAGDB):
    note_1 = keyword_db.add_note(title="N1", content="A")
    note_2 = keyword_db.add_note(title="N2", content="B")
    note_3 = keyword_db.add_note(title="N3", content="C")
    assert note_1 and note_2 and note_3

    source_id = keyword_db.add_keyword("ml")
    target_id = keyword_db.add_keyword("machine-learning")
    assert source_id is not None
    assert target_id is not None

    assert keyword_db.link_note_to_keyword(note_1, source_id)
    assert keyword_db.link_note_to_keyword(note_2, source_id)
    assert keyword_db.link_note_to_keyword(note_2, target_id)
    assert keyword_db.link_note_to_keyword(note_3, target_id)

    source_row = keyword_db.get_keyword_by_id(source_id)
    target_row = keyword_db.get_keyword_by_id(target_id)
    assert source_row is not None
    assert target_row is not None

    merged = keyword_db.merge_keywords(
        source_keyword_id=source_id,
        target_keyword_id=target_id,
        expected_source_version=int(source_row["version"]),
        expected_target_version=int(target_row["version"]),
    )
    assert merged["source_keyword_id"] == source_id
    assert merged["target_keyword_id"] == target_id
    assert int(merged["merged_note_links"]) >= 1

    assert keyword_db.get_keyword_by_id(source_id) is None

    notes_for_target = keyword_db.get_notes_for_keyword(target_id, limit=20, offset=0)
    linked_note_ids = {note["id"] for note in notes_for_target}
    assert note_1 in linked_note_ids
    assert note_2 in linked_note_ids
    assert note_3 in linked_note_ids

    keyword_ids_for_note_1 = {kw["id"] for kw in keyword_db.get_keywords_for_note(note_1)}
    assert source_id not in keyword_ids_for_note_1
    assert target_id in keyword_ids_for_note_1
