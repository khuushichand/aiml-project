from __future__ import annotations

import importlib
import importlib.util
from types import SimpleNamespace

import pytest


pytestmark = pytest.mark.unit


def _load_entrypoint_ops_module():
    module_name = "tldw_Server_API.app.core.DB_Management.media_db.runtime.media_entrypoint_ops"
    assert importlib.util.find_spec(module_name) is not None
    return importlib.import_module(module_name)


def test_run_search_media_db_forwards_to_package_api(monkeypatch: pytest.MonkeyPatch) -> None:
    media_entrypoint_ops_module = _load_entrypoint_ops_module()

    calls: list[tuple[object, str | None, dict[str, object]]] = []
    db = SimpleNamespace()
    expected_result = ([{"id": 7, "title": "Delegated"}], 1)

    def _fake_search_media(_db, search_query, **kwargs):
        calls.append((_db, search_query, kwargs))
        return expected_result

    monkeypatch.setattr(
        media_entrypoint_ops_module.media_db_api,
        "search_media",
        _fake_search_media,
    )

    result = media_entrypoint_ops_module.run_search_media_db(
        db,
        search_query="hello",
        search_fields=["title", "content"],
        media_types=["pdf"],
        date_range={"start_date": "2026-01-01", "end_date": "2026-12-31"},
        must_have_keywords=["alpha"],
        must_not_have_keywords=["beta"],
        sort_by="relevance",
        boost_fields={"title": 2.0},
        media_ids_filter=[1, "uuid-2"],
        page=3,
        results_per_page=15,
        include_trash=True,
        include_deleted=True,
    )

    assert calls == [
        (
            db,
            "hello",
            {
                "search_fields": ["title", "content"],
                "media_types": ["pdf"],
                "date_range": {"start_date": "2026-01-01", "end_date": "2026-12-31"},
                "must_have_keywords": ["alpha"],
                "must_not_have_keywords": ["beta"],
                "sort_by": "relevance",
                "boost_fields": {"title": 2.0},
                "media_ids_filter": [1, "uuid-2"],
                "page": 3,
                "results_per_page": 15,
                "include_trash": True,
                "include_deleted": True,
            },
        )
    ]
    assert result == expected_result


def test_run_add_media_with_keywords_forwards_to_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    media_entrypoint_ops_module = _load_entrypoint_ops_module()

    calls: list[dict[str, object]] = []
    repo_factory_calls: list[object] = []
    db = SimpleNamespace()
    expected_result = (42, "media-uuid", "stored")

    class _FakeRepo:
        def add_media_with_keywords(self, **kwargs):
            calls.append(kwargs)
            return expected_result

    monkeypatch.setattr(
        media_entrypoint_ops_module.MediaRepository,
        "from_legacy_db",
        classmethod(
            lambda cls, _db: (
                repo_factory_calls.append(_db),
                _FakeRepo(),
            )[1]
        ),
    )

    result = media_entrypoint_ops_module.run_add_media_with_keywords(
        db,
        url="https://example.com/doc",
        title="Doc",
        media_type="text",
        content="body",
        keywords=["alpha", "beta"],
        prompt="Summarize",
        analysis_content="analysis",
        safe_metadata='{"kind":"doc"}',
        source_hash="abc123",
        transcription_model="test-model",
        author="Author",
        ingestion_date="2026-03-21T00:00:00Z",
        overwrite=True,
        chunk_options={"chunk_size": 256},
        chunks=[{"text": "body"}],
        visibility="team",
        owner_user_id=9,
    )

    assert calls == [
        {
            "url": "https://example.com/doc",
            "title": "Doc",
            "media_type": "text",
            "content": "body",
            "keywords": ["alpha", "beta"],
            "prompt": "Summarize",
            "analysis_content": "analysis",
            "safe_metadata": '{"kind":"doc"}',
            "source_hash": "abc123",
            "transcription_model": "test-model",
            "author": "Author",
            "ingestion_date": "2026-03-21T00:00:00Z",
            "overwrite": True,
            "chunk_options": {"chunk_size": 256},
            "chunks": [{"text": "body"}],
            "visibility": "team",
            "owner_user_id": 9,
        }
    ]
    assert repo_factory_calls == [db]
    assert result == expected_result
