from __future__ import annotations

from contextlib import contextmanager

import pytest

from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael


@pytest.mark.unit
@pytest.mark.asyncio
async def test_async_scrape_and_no_summarize_then_ingest_uses_managed_media_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeDb:
        def __init__(self) -> None:
            self.closed = False

        def close_connection(self) -> None:
            self.closed = True

    fake_db = _FakeDb()
    managed_calls: list[dict[str, object]] = []
    ingest_calls: list[dict[str, object]] = []

    @contextmanager
    def _fake_managed_media_database(client_id, *, initialize=True, **kwargs):
        managed_calls.append(
            {
                "client_id": client_id,
                "initialize": initialize,
                "kwargs": kwargs,
            }
        )
        try:
            yield fake_db
        finally:
            fake_db.close_connection()

    async def _fake_scrape_article(url):
        return {
            "title": "Scraped Title",
            "author": "Author Name",
            "content": "Article body",
        }

    def _fake_ingest_article_to_db(**kwargs):
        ingest_calls.append(kwargs)
        return True

    monkeypatch.setattr(ael, "scrape_article", _fake_scrape_article, raising=True)
    monkeypatch.setattr(
        ael,
        "managed_media_database",
        _fake_managed_media_database,
        raising=False,
    )
    monkeypatch.setattr(
        ael,
        "ingest_article_to_db",
        _fake_ingest_article_to_db,
        raising=True,
    )

    result = await ael.async_scrape_and_no_summarize_then_ingest(
        "https://example.com/article",
        "news,analysis",
        "Custom Title",
    )

    assert "Ingestion Result: True" in result
    assert "Title: Custom Title" in result
    assert fake_db.closed is True
    assert managed_calls == [
        {
            "client_id": "article_extractor",
            "initialize": False,
            "kwargs": {},
        }
    ]
    assert len(ingest_calls) == 1
    assert ingest_calls[0]["db_instance"] is fake_db
    assert ingest_calls[0]["url"] == "https://example.com/article"
    assert ingest_calls[0]["title"] == "Custom Title"
    assert ingest_calls[0]["author"] == "Author Name"
    assert ingest_calls[0]["content"] == "Article body"
    assert ingest_calls[0]["keywords"] == ["news", "analysis"]
    assert ingest_calls[0]["custom_prompt"] is None
    assert ingest_calls[0]["summary"] is None
