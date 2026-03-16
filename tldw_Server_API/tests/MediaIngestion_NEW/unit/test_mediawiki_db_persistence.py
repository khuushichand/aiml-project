from __future__ import annotations

from datetime import datetime, timezone

from tldw_Server_API.app.core.Ingestion_Media_Processing.MediaWiki import Media_Wiki


def test_process_single_item_uses_media_repository_for_media_db_sessions(monkeypatch):
    class _MediaDb:
        backend = object()

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 71, "wiki-uuid", "stored"

    media_db = _MediaDb()
    fake_repo = _FakeRepo()

    monkeypatch.setattr(Media_Wiki, "optimized_chunking", lambda content, options: [{"text": content, "metadata": {}}])
    monkeypatch.setattr(Media_Wiki, "create_media_database", lambda client_id="mediawiki_import": media_db)
    monkeypatch.setattr(Media_Wiki, "get_media_repository", lambda db: fake_repo, raising=False)

    result = Media_Wiki.process_single_item(
        content="Wiki body",
        title="Test Page",
        wiki_name="ExampleWiki",
        chunk_options={},
        item={
            "timestamp": datetime(2024, 1, 2, tzinfo=timezone.utc),
            "namespace": 0,
            "page_id": 123,
            "revision_id": 456,
        },
        store_to_db=True,
        store_to_vector_db=False,
    )

    assert result["status"] == "Success"
    assert result["media_id"] == 71
    assert fake_repo.calls == [
        {
            "url": "mediawiki:ExampleWiki:Test%20Page",
            "title": "Test Page",
            "media_type": "mediawiki_page",
            "content": "Wiki body",
            "keywords": ["mediawiki", "ExampleWiki", "page"],
            "prompt": "",
            "analysis_content": "",
            "transcription_model": "N/A",
            "author": "MediaWiki",
            "ingestion_date": "2024-01-02",
        }
    ]
