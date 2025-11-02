from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper


def _allow_egress(monkeypatch):
    import tldw_Server_API.app.core.Security.egress as egress
    monkeypatch.setattr(egress, "evaluate_url_policy", lambda url: SimpleNamespace(allowed=True))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fifo_order_when_strategy_default(monkeypatch):
    """When crawl_strategy="default", traversal should be FIFO/BFS instead of best-first.

    We arrange links so that best-first would prefer deeper path first, but FIFO should
    visit in the order discovered.
    """
    _allow_egress(monkeypatch)

    scraper = EnhancedWebScraper(config={})

    base = "http://example.com/a"
    b1 = "http://example.com/b1"
    b2 = "http://example.com/b2"

    # Mock scraping to return success for any requested URL
    async def fake_scrape_multiple(urls, method="trafilatura", **kwargs):
        return [
            {
                "url": u,
                "content": "<html><body>ok</body></html>",
                "extraction_successful": True,
                "method": method,
            }
            for u in urls
        ]

    # Only the base page yields links; the children have none
    async def fake_extract_links(url, content):
        if url == base:
            # Order is b1 then b2 to assert FIFO ordering
            return [b1, b2]
        return []

    monkeypatch.setattr(scraper, "scrape_multiple", fake_scrape_multiple)
    monkeypatch.setattr(scraper, "_extract_links", fake_extract_links)

    # With FIFO, expect: base, then b1, then b2
    res = await scraper.recursive_scrape(
        base_url=base,
        max_pages=3,
        max_depth=2,
        crawl_strategy="default",
    )

    urls = [r.get("url") for r in res]
    assert urls == [base, b1, b2]
