import pytest

from tldw_Server_API.app.core.DB_Management import DB_Manager
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType


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
    rows, total_pages, page, total_items = DB_Manager.get_paginated_files(db_instance=db, page=1, results_per_page=10)
    assert total_items >= 1
    assert page == 1
    assert isinstance(rows, list)


def test_add_media_with_keywords_uses_media_repository_for_media_db_sessions(monkeypatch):

    class _MediaDb:
        backend = object()

    class _FakeRepo:
        def __init__(self):
            self.calls = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 33, "repo-uuid", "stored"

    fake_repo = _FakeRepo()
    media_db = _MediaDb()

    monkeypatch.setattr(DB_Manager, "get_media_repository", lambda db: fake_repo, raising=False)
    def _fake_require_db_instance(args, kwargs, func_name):
        kwargs.pop("db_instance", None)
        return media_db

    monkeypatch.setattr(DB_Manager, "_require_db_instance", _fake_require_db_instance, raising=False)

    result = DB_Manager.add_media_with_keywords(
        db_instance=media_db,
        title="Repo Routed",
        media_type="text",
        content="body",
        keywords=["k1"],
    )

    assert result == (33, "repo-uuid", "stored")
    assert fake_repo.calls == [
        {
            "title": "Repo Routed",
            "media_type": "text",
            "content": "body",
            "keywords": ["k1"],
        }
    ]


def test_create_media_database_delegates_to_runtime_factory(monkeypatch):
    captured = {}

    def _fake_runtime_create_media_database(client_id, **kwargs):
        captured["client_id"] = client_id
        captured.update(kwargs)
        return "db-instance"

    monkeypatch.setattr(
        DB_Manager,
        "runtime_create_media_database",
        _fake_runtime_create_media_database,
        raising=False,
    )
    monkeypatch.setattr(
        DB_Manager,
        "_POSTGRES_CONTENT_MODE",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        DB_Manager,
        "_ensure_content_backend_loaded",
        lambda: "backend-sentinel",
        raising=False,
    )
    monkeypatch.setattr(
        DB_Manager,
        "single_user_db_path",
        "/tmp/default-media.db",
        raising=False,
    )

    result = DB_Manager.create_media_database(
        "client-9",
        config=DB_Manager.single_user_config,
    )

    assert result == "db-instance"
    assert captured["client_id"] == "client-9"
    assert captured["runtime"].default_db_path == "/tmp/default-media.db"
    assert captured["runtime"].postgres_content_mode is True
    assert captured["config"] is DB_Manager.single_user_config


def test_update_keywords_for_media_success():

    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc B",
        media_type="text",
        content="bravo content",
        keywords=["old"],
    )
    DB_Manager.update_keywords_for_media(db_instance=db, media_id=mid, keywords=["x", "y"])
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

    rb = DB_Manager.rollback_to_version(db_instance=db, media_id=mid, target_version_number=1)
    assert isinstance(rb, dict) and "success" in rb

    latest = DB_Manager.get_document_version(db_instance=db, media_id=mid, version_number=None, include_content=True)
    assert latest and latest.get("version_number") == 3
    assert latest.get("content") == "v1 content"

    # delete v2 should succeed (not last active)
    v2_info = DB_Manager.get_document_version(db_instance=db, media_id=mid, version_number=2, include_content=False)
    assert v2_info and v2_info.get("uuid")
    ok = DB_Manager.delete_document_version(db_instance=db, version_uuid=v2_info["uuid"])
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


def test_full_media_detail_wrappers_return_expected_shapes():

    db = _make_memory_db()
    mid, _, _ = DB_Manager.add_media_with_keywords(
        db_instance=db,
        title="Doc Detail",
        media_type="text",
        content="detail content",
        keywords=["alpha", "beta"],
        prompt="detail-prompt",
        analysis_content="detail-analysis",
    )

    details = DB_Manager.get_full_media_details(
        db_instance=db,
        media_id=mid,
        include_content=True,
    )
    assert details is not None
    assert details["media"]["id"] == mid
    assert details["latest_version"]["content"] == "detail content"
    assert set(details["keywords"]) == {"alpha", "beta"}

    rich = DB_Manager.get_full_media_details_rich(
        db_instance=db,
        media_id=mid,
        include_content=True,
        include_versions=True,
    )
    assert rich is not None
    assert rich["media_id"] == mid
    assert rich["content"]["text"] == "detail content"
    assert set(rich["keywords"]) == {"alpha", "beta"}
    assert rich["processing"]["prompt"] == "detail-prompt"
    assert rich["processing"]["analysis"] == "detail-analysis"
    assert rich["versions"]


def test_validate_postgres_content_backend_delegates_to_runtime_factory(monkeypatch):
    captured = {}

    class StubBackend:
        backend_type = BackendType.POSTGRESQL

    def _fake_runtime_validate_postgres_content_backend(
        *,
        get_content_backend_instance,
        runtime,
    ):
        captured["backend"] = get_content_backend_instance()
        captured["runtime"] = runtime

    stub_backend = StubBackend()
    monkeypatch.setattr(DB_Manager, "_CONTENT_DB_BACKEND", stub_backend, raising=False)
    monkeypatch.setattr(DB_Manager, "_POSTGRES_CONTENT_MODE", True, raising=False)
    monkeypatch.setattr(
        DB_Manager,
        "runtime_validate_postgres_content_backend",
        _fake_runtime_validate_postgres_content_backend,
        raising=False,
    )

    DB_Manager.validate_postgres_content_backend()

    assert captured["backend"] is stub_backend
    assert captured["runtime"].default_db_path == str(DB_Manager.single_user_db_path)
    assert captured["runtime"].default_config is DB_Manager.single_user_config
    assert captured["runtime"].postgres_content_mode is True
