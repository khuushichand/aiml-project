import json

import pytest

from tldw_Server_API.app.core.Slides.slides_db import SlidesDatabase, ConflictError


def _sample_slides() -> str:
    slides = [
        {"order": 0, "layout": "title", "title": "Deck", "content": "", "speaker_notes": None, "metadata": {}},
        {"order": 1, "layout": "content", "title": "Intro", "content": "- A\n- B", "speaker_notes": None, "metadata": {}},
    ]
    return json.dumps(slides)


def test_slides_db_create_and_get(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    row = db.create_presentation(
        presentation_id=None,
        title="Deck",
        description=None,
        theme="black",
        marp_theme="gaia",
        settings=None,
        slides=_sample_slides(),
        slides_text="Deck Intro A B",
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=None,
    )
    fetched = db.get_presentation_by_id(row.id)
    assert fetched.id == row.id
    assert fetched.title == "Deck"
    assert fetched.marp_theme == "gaia"
    db.close_connection()


def test_slides_db_update_conflict(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    row = db.create_presentation(
        presentation_id=None,
        title="Deck",
        description=None,
        theme="black",
        marp_theme=None,
        settings=None,
        slides=_sample_slides(),
        slides_text="Deck Intro A B",
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=None,
    )
    updated = db.update_presentation(
        presentation_id=row.id,
        update_fields={"title": "Updated"},
        expected_version=row.version,
    )
    assert updated.version == row.version + 1
    with pytest.raises(ConflictError):
        db.update_presentation(
            presentation_id=row.id,
            update_fields={"title": "Conflict"},
            expected_version=row.version,
        )
    db.close_connection()


def test_slides_db_search(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    _ = db.create_presentation(
        presentation_id=None,
        title="Search Deck",
        description=None,
        theme="black",
        marp_theme=None,
        settings=None,
        slides=_sample_slides(),
        slides_text="alpha beta gamma",
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=None,
    )
    rows, total = db.search_presentations(query="alpha", limit=10, offset=0, include_deleted=False)
    assert total == 1
    assert rows[0].title == "Search Deck"
    db.close_connection()


def test_slides_db_soft_delete_restore(tmp_path):
    db_path = tmp_path / "Slides.db"
    db = SlidesDatabase(db_path=db_path, client_id="tester")
    row = db.create_presentation(
        presentation_id=None,
        title="Deck",
        description=None,
        theme="black",
        marp_theme=None,
        settings=None,
        slides=_sample_slides(),
        slides_text="Deck Intro A B",
        source_type="manual",
        source_ref=None,
        source_query=None,
        custom_css=None,
    )
    deleted = db.soft_delete_presentation(row.id, expected_version=row.version)
    assert deleted.deleted == 1
    rows, total = db.list_presentations(limit=10, offset=0, include_deleted=False, sort_column="created_at", sort_direction="DESC")
    assert total == 0
    restored = db.restore_presentation(row.id, expected_version=deleted.version)
    assert restored.deleted == 0
    db.close_connection()
