import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def collections_db(monkeypatch: pytest.MonkeyPatch) -> CollectionsDatabase:
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_reading_note_links"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        yield CollectionsDatabase.for_user(user_id=780)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def _create_reading_item(collections_db: CollectionsDatabase) -> int:
    row = collections_db.upsert_content_item(
        origin="reading",
        origin_type="manual",
        origin_id=None,
        url="https://example.org/item",
        canonical_url="https://example.org/item",
        domain="example.org",
        title="Item",
        summary="Summary",
        notes="Item notes",
        content_hash="hash-1",
        word_count=10,
        published_at=None,
        status="saved",
        favorite=False,
        metadata={"source": "test"},
        media_id=None,
        job_id=None,
        run_id=None,
        source_id=None,
        read_at=None,
        tags=["alpha"],
    )
    return row.id


def test_note_link_crud_roundtrip(collections_db: CollectionsDatabase) -> None:
    item_id = _create_reading_item(collections_db)

    linked = collections_db.link_note_to_content_item(item_id=item_id, note_id="note-1234")
    assert linked.item_id == item_id
    assert linked.note_id == "note-1234"

    rows = collections_db.list_note_links_for_content_item(item_id)
    assert len(rows) == 1
    assert rows[0].note_id == "note-1234"

    removed = collections_db.unlink_note_from_content_item(item_id=item_id, note_id="note-1234")
    assert removed is True
    assert collections_db.list_note_links_for_content_item(item_id) == []


def test_note_link_requires_existing_item(collections_db: CollectionsDatabase) -> None:
    with pytest.raises(KeyError):
        collections_db.link_note_to_content_item(item_id=9999, note_id="note-1")
