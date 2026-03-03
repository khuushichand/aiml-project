import shutil
from pathlib import Path

import pytest

from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def collections_db(monkeypatch: pytest.MonkeyPatch) -> CollectionsDatabase:
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_reading_saved_searches"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    try:
        yield CollectionsDatabase.for_user(user_id=779)
    finally:
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


def test_saved_search_crud_roundtrip(collections_db: CollectionsDatabase) -> None:
    created = collections_db.create_saved_search(
        name="Morning",
        query_json='{"q":"ai"}',
        sort="updated_desc",
    )
    assert created.id > 0
    assert created.name == "Morning"
    assert created.query_json == '{"q":"ai"}'
    assert created.sort == "updated_desc"

    rows, total = collections_db.list_saved_searches(limit=10, offset=0)
    assert total == 1
    assert rows[0].id == created.id

    updated = collections_db.update_saved_search(
        created.id,
        {"query_json": '{"q":"ml"}', "sort": "created_desc"},
    )
    assert updated.query_json == '{"q":"ml"}'
    assert updated.sort == "created_desc"

    deleted = collections_db.delete_saved_search(created.id)
    assert deleted is True
    rows_after, total_after = collections_db.list_saved_searches(limit=10, offset=0)
    assert total_after == 0
    assert rows_after == []
