import pytest

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase


def test_add_media_with_keywords_requires_db_instance():
    with pytest.raises(ValueError) as excinfo:
        # Intentionally omit db_instance to ensure the wrapper enforces it
        DB_Manager.add_media_with_keywords(url="https://example.com", title="T", media_type="text")
    assert "requires 'db_instance'" in str(excinfo.value)


def test_get_paginated_files_requires_db_instance():
    with pytest.raises(ValueError) as excinfo:
        # Intentionally omit db_instance to ensure the wrapper enforces it
        DB_Manager.get_paginated_files(page=1, results_per_page=10)
    assert "requires 'db_instance'" in str(excinfo.value)


def test_update_keywords_for_media_requires_db_instance():
    with pytest.raises(ValueError) as excinfo:
        DB_Manager.update_keywords_for_media(media_id=1, keywords=["x", "y"])  # no db_instance
    assert "requires 'db_instance'" in str(excinfo.value)


def test_rollback_to_version_requires_db_instance():
    with pytest.raises(ValueError) as excinfo:
        DB_Manager.rollback_to_version(media_id=1, target_version_number=2)  # no db_instance
    assert "requires 'db_instance'" in str(excinfo.value)


def test_delete_document_version_requires_db_instance():
    with pytest.raises(ValueError) as excinfo:
        DB_Manager.delete_document_version(version_uuid="deadbeef")  # no db_instance
    assert "requires 'db_instance'" in str(excinfo.value)


def _make_memory_db(client_id: str = "unit-db-manager") -> MediaDatabase:
    return MediaDatabase(db_path=":memory:", client_id=client_id)


def test_add_media_and_paginated_files_success():
    db = _make_memory_db()
    mid, muuid, msg = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc A",
        media_type="text",
        content="alpha content",
        keywords=["tag1"],
        prompt="p1",
        analysis_content="a1",
    )
    assert isinstance(mid, int) and muuid and isinstance(muuid, str)
    rows, total_pages, page, total_items = DB_Manager.get_paginated_files(
        db_instance=db, page=1, results_per_page=10
    )
    assert total_items >= 1
    assert page == 1
    assert isinstance(rows, list)


def test_update_keywords_for_media_success():
    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc B",
        media_type="text",
        content="bravo content",
        keywords=["old"],
    )
    DB_Manager.update_keywords_for_media(
        db_instance=db, media_id=mid, keywords=["x", "y"]
    )
    kws = DB_Manager.fetch_keywords_for_media(media_id=mid, db_instance=db)
    assert set(kws) == {"x", "y"}


def test_rollback_to_version_success_and_delete_version_success():
    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc C",
        media_type="text",
        content="v1 content",
    )
    v2 = DB_Manager.create_document_version(
        db_instance=db,
        media_id=mid,
        content="v2 content",
        prompt="p2",
        analysis_content="a2",
    )
    assert v2 and v2.get("version_number") == 2

    rb = DB_Manager.rollback_to_version(
        db_instance=db, media_id=mid, target_version_number=1
    )
    assert isinstance(rb, dict) and "success" in rb

    latest = DB_Manager.get_document_version(
        db_instance=db, media_id=mid, version_number=None, include_content=True
    )
    assert latest and latest.get("version_number") == 3
    assert latest.get("content") == "v1 content"

    # delete v2 should succeed (not last active)
    v2_info = DB_Manager.get_document_version(
        db_instance=db, media_id=mid, version_number=2, include_content=False
    )
    assert v2_info and v2_info.get("uuid")
    ok = DB_Manager.delete_document_version(
        db_instance=db, version_uuid=v2_info["uuid"]
    )
    assert ok is True
