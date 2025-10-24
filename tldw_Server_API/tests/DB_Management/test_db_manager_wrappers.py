from contextlib import contextmanager

import pytest

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, QueryResult


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


@pytest.fixture
def force_postgres(monkeypatch):
    monkeypatch.setattr(DB_Manager, "db_type", "postgres", raising=False)
    yield


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


def test_fetch_keywords_for_media_postgres_mode(force_postgres):
    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc PG",
        media_type="text",
        content="pg content",
        keywords=["initial"],
    )
    DB_Manager.update_keywords_for_media(
        db_instance=db,
        media_id=mid,
        keywords=["pg", "sql"],
    )
    tags = DB_Manager.fetch_keywords_for_media(media_id=mid, db_instance=db)
    assert set(tags) == {"pg", "sql"}


def test_empty_trash_postgres_mode(force_postgres):
    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Trash Me",
        media_type="text",
        content="trashed content",
    )
    DB_Manager.mark_as_trash(db_instance=db, media_id=mid)
    processed, remaining = DB_Manager.empty_trash(db_instance=db)
    assert processed == 1
    assert remaining == 0


def test_document_version_wrappers_postgres_mode(force_postgres):
    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc Versions",
        media_type="text",
        content="v1 content",
    )
    created = DB_Manager.create_document_version(
        db_instance=db,
        media_id=mid,
        content="v2 content",
        prompt="prompt",
    )
    assert created and created.get("version_number") == 2
    latest = DB_Manager.get_document_version(
        db_instance=db,
        media_id=mid,
        version_number=None,
        include_content=True,
    )
    assert latest and latest.get("version_number") == 2
    assert latest.get("content") == "v2 content"


def test_validate_postgres_content_backend_uses_queryresult_first(monkeypatch):
    expected_version = MediaDatabase._CURRENT_SCHEMA_VERSION

    class StubBackend:
        backend_type = BackendType.POSTGRESQL

        def __init__(self):
            self.queries = []

        @contextmanager
        def transaction(self):
            yield object()

        def execute(self, query, params=None, connection=None):
            self.queries.append(query)
            if "schema_version" in query:
                return QueryResult(rows=[{"version": expected_version}], rowcount=1)
            return QueryResult(rows=[{"ok": 1}], rowcount=1)

    class StubMediaDatabase:
        _CURRENT_SCHEMA_VERSION = expected_version
        instances = []

        def __init__(self, *args, **kwargs):
            self.backend = kwargs.get("backend")
            self.checked_policies = []
            self.__class__.instances.append(self)

        def _postgres_policy_exists(self, conn, table, policy):
            self.checked_policies.append((table, policy))
            return True

        def close_connection(self):
            pass

    stub_backend = StubBackend()
    monkeypatch.setattr(DB_Manager, "_CONTENT_DB_BACKEND", stub_backend, raising=False)
    monkeypatch.setattr(DB_Manager, "_POSTGRES_CONTENT_MODE", True, raising=False)
    monkeypatch.setattr(DB_Manager, "MediaDatabase", StubMediaDatabase, raising=False)

    DB_Manager.validate_postgres_content_backend()

    assert any("schema_version" in q for q in stub_backend.queries)
    assert StubMediaDatabase.instances
    assert StubMediaDatabase.instances[-1].checked_policies
