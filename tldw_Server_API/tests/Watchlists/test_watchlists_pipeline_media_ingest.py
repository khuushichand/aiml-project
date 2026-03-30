from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Watchlists import pipeline


@pytest.mark.unit
def test_ingest_watchlist_media_uses_media_repository_for_media_db_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _MediaDb:
        backend = object()

    class _FakeRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def add_media_with_keywords(self, **kwargs):
            self.calls.append(kwargs)
            return 23, "watchlist-uuid", "stored"

    fake_repo = _FakeRepo()
    media_db = _MediaDb()

    monkeypatch.setattr(pipeline, "get_media_repository", lambda db: fake_repo, raising=False)

    result = pipeline._ingest_watchlist_media(
        media_db=media_db,
        url="https://example.com/article",
        title="Watchlist Article",
        media_type="article",
        content="Body",
        author="Author",
        keywords=["rss", "flagged"],
        overwrite=False,
    )

    assert result == (23, "watchlist-uuid", "stored")
    assert fake_repo.calls == [
        {
            "url": "https://example.com/article",
            "title": "Watchlist Article",
            "media_type": "article",
            "content": "Body",
            "author": "Author",
            "keywords": ["rss", "flagged"],
            "overwrite": False,
        }
    ]
