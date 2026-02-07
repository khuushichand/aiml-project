from types import SimpleNamespace

import pytest

import tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping as enhanced_mod
from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper


def _allow_egress(monkeypatch):
    import tldw_Server_API.app.core.Security.egress as egress

    monkeypatch.setattr(
        egress,
        "evaluate_url_policy",
        lambda url: SimpleNamespace(allowed=True),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fifo_observability_uses_stable_skip_labels_and_tracks_path_depth(monkeypatch):
    _allow_egress(monkeypatch)
    scraper = EnhancedWebScraper(config={})

    counters: list[tuple[str, dict[str, str], int]] = []
    gauges: list[tuple[str, float, dict[str, str]]] = []
    histograms: list[tuple[str, float, dict[str, str]]] = []

    def _log_counter(name: str, labels=None, value: int = 1):
        counters.append((name, dict(labels or {}), int(value)))

    def _log_gauge(name: str, value: float, labels=None):
        gauges.append((name, float(value), dict(labels or {})))

    def _log_histogram(name: str, value: float, labels=None):
        histograms.append((name, float(value), dict(labels or {})))

    monkeypatch.setattr(enhanced_mod, "log_counter", _log_counter)
    monkeypatch.setattr(enhanced_mod, "log_gauge", _log_gauge)
    monkeypatch.setattr(enhanced_mod, "log_histogram", _log_histogram)

    base = "http://example.com/docs/v1"
    allowed = "http://example.com/docs/v1/topic"
    deep = "http://example.com/docs/v1/topic/deep"

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

    async def fake_extract_links(url, content):
        if url == base:
            return [allowed, allowed, deep]
        return []

    monkeypatch.setattr(scraper, "scrape_multiple", fake_scrape_multiple)
    monkeypatch.setattr(scraper, "_extract_links", fake_extract_links)

    results = await scraper.recursive_scrape(
        base_url=base,
        max_pages=5,
        max_depth=1,
        crawl_strategy="default",
    )
    assert len(results) == 2

    skipped = [
        labels.get("reason")
        for name, labels, _ in counters
        if name == "webscraping.crawl.urls_skipped"
    ]
    assert "path_depth" in skipped
    assert "duplicate" in skipped
    assert "visited_or_depth" not in skipped
    assert "dup_seen" not in skipped

    assert any(name == "webscraping.crawl.queue_size" for name, _, _ in gauges)
    assert any(name == "webscraping.crawl.depth" for name, _, _ in gauges)
    assert any(
        name == "webscraping.crawl.score" and labels.get("stage") == "visit"
        for name, _, labels in histograms
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recursive_crawl_logs_accept_and_skip_decisions(monkeypatch):
    _allow_egress(monkeypatch)
    scraper = EnhancedWebScraper(config={})

    log_lines: list[str] = []

    def _debug(message, *args, **kwargs):
        try:
            rendered = str(message).format(*args)
        except Exception:
            rendered = str(message)
        log_lines.append(rendered)

    monkeypatch.setattr(enhanced_mod.logger, "debug", _debug)

    base = "http://example.com/docs/v1"
    allowed = "http://example.com/docs/v1/topic"
    deep = "http://example.com/docs/v1/topic/deep"

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

    async def fake_extract_links(url, content):
        if url == base:
            return [allowed, deep]
        return []

    monkeypatch.setattr(scraper, "scrape_multiple", fake_scrape_multiple)
    monkeypatch.setattr(scraper, "_extract_links", fake_extract_links)

    await scraper.recursive_scrape(
        base_url=base,
        max_pages=5,
        max_depth=1,
        crawl_strategy="default",
    )

    assert any("Accept URL [default depth=0]" in line for line in log_lines)
    assert any("Skip URL [default:path_depth" in line for line in log_lines)
