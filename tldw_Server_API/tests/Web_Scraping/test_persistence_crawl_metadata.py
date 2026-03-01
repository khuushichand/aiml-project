import json

import pytest

import tldw_Server_API.app.services.enhanced_web_scraping_service as enhanced_svc_mod
from tldw_Server_API.app.services.enhanced_web_scraping_service import WebScrapingService


class _MetricsStub:
    def set_gauge(self, *args, **kwargs):
        return None

    def observe(self, *args, **kwargs):
        return None

    def increment(self, *args, **kwargs):
        return None


class _FakeDB:
    def __init__(self):
        self.calls: list[dict] = []
        self.closed = False

    def add_media_with_keywords(self, **kwargs):
        self.calls.append(kwargs)
        idx = len(self.calls)
        return idx, f"uuid-{idx}", "ok"

    def close_connection(self):
        self.closed = True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_store_persistent_persists_crawl_metadata_when_available(monkeypatch):
    service = WebScrapingService()
    fake_db = _FakeDB()

    monkeypatch.setattr(
        enhanced_svc_mod,
        "get_user_media_db_path",
        lambda _: "/tmp/test-media.db",  # nosec B108
    )
    monkeypatch.setattr(
        enhanced_svc_mod,
        "create_media_database",
        lambda **kwargs: fake_db,
    )
    monkeypatch.setattr(
        enhanced_svc_mod,
        "get_metrics_registry",
        lambda: _MetricsStub(),
    )

    result = {
        "method": "Recursive Scraping",
        "articles": [
            {
                "url": "https://example.com/article",
                "title": "Example",
                "author": "Author",
                "content": "<html><body>content</body></html>",
                "summary": "summary",
                "extraction_successful": True,
                "metadata": {
                    "crawl_depth": "2",
                    "crawl_parent_url": "https://example.com",
                    "crawl_score": "0.75",
                },
            }
        ],
    }

    persisted = await service._store_persistent(
        result=result,
        keywords="k1,k2",
        user_id=7,
    )

    assert persisted["status"] == "persist-ok"
    assert persisted["stored_articles"] == 1
    assert len(fake_db.calls) == 1
    assert fake_db.closed is True

    safe_metadata_raw = fake_db.calls[0]["safe_metadata"]
    safe_metadata = json.loads(safe_metadata_raw)
    assert safe_metadata["crawl_depth"] == 2
    assert safe_metadata["crawl_parent_url"] == "https://example.com"
    assert safe_metadata["crawl_score"] == pytest.approx(0.75)
