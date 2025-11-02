import types

import pytest

from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as AEL


def test_scrape_from_sitemap_uses_blocking(monkeypatch):
    # Prepare fake sitemap XML
    xml = """
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc></url>
      <url><loc>https://example.com/b</loc></url>
    </urlset>
    """.strip()

    class FakeResp:
        status_code = 200
        content = xml.encode("utf-8")
        def raise_for_status(self):
            return None

    calls = []

    def fake_get(url):
        return FakeResp()

    def fake_blocking(url):
        calls.append(url)
        return {"url": url, "title": "ok", "author": "", "date": "", "content": "", "extraction_successful": True}

    monkeypatch.setattr(AEL.requests, "get", fake_get)
    monkeypatch.setattr(AEL, "scrape_article_blocking", fake_blocking)

    results = AEL.scrape_from_sitemap("https://example.com/sitemap.xml")
    assert len(results) == 2
    assert set(calls) == {"https://example.com/a", "https://example.com/b"}


def test_scrape_by_url_level_uses_blocking(monkeypatch):
    urls = {"https://example.com/one", "https://example.com/two/deep"}

    monkeypatch.setattr(AEL, "collect_internal_links", lambda base: urls)

    calls = []
    def fake_blocking(url):
        calls.append(url)
        return {"url": url, "title": "t", "author": "", "date": "", "content": "", "extraction_successful": True}

    monkeypatch.setattr(AEL, "scrape_article_blocking", fake_blocking)

    # Level 1 should include only the first url
    results = AEL.scrape_by_url_level("https://example.com", level=1)
    assert len(results) == 1
    assert calls == ["https://example.com/one"]
