from types import SimpleNamespace

import pytest

from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper


def _allow_egress(monkeypatch):
    import tldw_Server_API.app.core.Security.egress as egress
    monkeypatch.setattr(egress, "evaluate_url_policy", lambda url: SimpleNamespace(allowed=True))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_priority_crawl_order(monkeypatch):
    _allow_egress(monkeypatch)
    scraper = EnhancedWebScraper(config={})

    base = "http://example.com"
    links = ["/a", "/a/b", "/a/b/c"]  # depth 1,2,3

    # Return success for whatever URLs we are asked
    async def fake_scrape_multiple(urls, method="trafilatura", **kwargs):
        outs = []
        for u in urls:
            outs.append({
                "url": u,
                "content": "<html><body>ok</body></html>",
                "extraction_successful": True,
                "method": method,
            })
        return outs

    async def fake_extract_links(url, content):
        # Only the base page yields links; children do not
        return links if url == base else []

    monkeypatch.setattr(scraper, "scrape_multiple", fake_scrape_multiple)
    monkeypatch.setattr(scraper, "_extract_links", fake_extract_links)

    res = await scraper.recursive_scrape(base_url=base, max_pages=4, max_depth=2)

    # Expect base, then depth-2 before depth-1 because of best-first by score (depth 2 closer to optimal 3 than depth 1)
    urls = [r.get("url") for r in res]
    assert urls[0] == base
    assert urls[1] == "http://example.com/a/b"
    assert urls[2] == "http://example.com/a"
    # Metadata present
    assert isinstance(res[1].get("metadata", {}).get("depth"), int)
    assert "parent_url" in res[1].get("metadata", {})
    assert "score" in res[1].get("metadata", {})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_max_pages_and_visited(monkeypatch):
    _allow_egress(monkeypatch)
    scraper = EnhancedWebScraper(config={})
    base = "http://example.com"

    # Provide duplicates that normalize to the same URL
    base_links = [
        "/x",
        "/x#frag",
        "/x?utm_source=zzz",
    ]

    async def fake_scrape_multiple(urls, method="trafilatura", **kwargs):
        return [{
            "url": u,
            "content": "<html><body>ok</body></html>",
            "extraction_successful": True,
            "method": method,
        } for u in urls]

    async def fake_extract_links(url, content):
        return base_links if url == base else []

    monkeypatch.setattr(scraper, "scrape_multiple", fake_scrape_multiple)
    monkeypatch.setattr(scraper, "_extract_links", fake_extract_links)

    # Limit to 2 pages => base + one child
    res = await scraper.recursive_scrape(base_url=base, max_pages=2, max_depth=2)
    urls = [r.get("url") for r in res]
    assert len(res) == 2
    assert urls[0] == base
    # The second URL should be the canonical child
    assert urls[1].startswith("http://example.com/x")
