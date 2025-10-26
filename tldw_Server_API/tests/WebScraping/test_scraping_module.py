import types
import pytest


@pytest.mark.asyncio
async def test_egress_denied_scrape_article(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael

    # Deny egress
    from tldw_Server_API.app.core.Security import egress as eg
    pol = types.SimpleNamespace(allowed=False, reason="deny_test")
    monkeypatch.setattr(eg, 'evaluate_url_policy', lambda url: pol)

    result = await ael.scrape_article("https://example.com")
    assert result["extraction_successful"] is False
    assert "Egress denied" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_egress_denied_enhanced_scraper(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper
    from tldw_Server_API.app.core.Security import egress as eg

    pol = types.SimpleNamespace(allowed=False, reason="deny_test")
    monkeypatch.setattr(eg, 'evaluate_url_policy', lambda url: pol)

    scraper = EnhancedWebScraper()
    result = await scraper.scrape_article("https://example.com")
    assert result["extraction_successful"] is False
    assert "Egress denied" in (result.get("error") or "")


@pytest.mark.asyncio
async def test_extract_links_text_vs_html(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper

    scraper = EnhancedWebScraper()

    # Dummy session and response to avoid real network
    class DummyResp:
        async def text(self):
            return "<html><body><a href='/a'>A</a></body></html>"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummySession:
        def get(self, url):
            return DummyResp()

    # Monkeypatch cookie manager to return dummy session (awaitable)
    async def fake_get_session(url, **kw):
        return DummySession()

    monkeypatch.setattr(scraper.cookie_manager, 'get_session', fake_get_session)

    # Case 1: plain text content should trigger a fetch and return links
    links_text = await scraper._extract_links("https://example.com", "plain text no html")
    assert "/a" in links_text

    # Case 2: HTML content provided should be parsed directly
    links_html = await scraper._extract_links("https://example.com", "<a href='https://example.com/b'>B</a>")
    assert "https://example.com/b" in links_html


def test_provider_missing_keys_google(monkeypatch):
    # Ensure Google provider raises ValueError when API key/engine id missing
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws

    def fake_cfg():
        return {"search_engines": {
            "google_search_api_key": "",
            "google_search_engine_id": "",
            "google_search_api_url": "https://customsearch.googleapis.com/customsearch/v1",
            "google_simp_trad_chinese": "1",
            "limit_google_search_to_country": False,
        }}

    monkeypatch.setattr(ws, 'get_loaded_config', fake_cfg)

    with pytest.raises(ValueError):
        ws.search_web_google("query")


def test_provider_missing_keys_kagi(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws

    def fake_cfg():
        return {"search_engines": {"kagi_search_api_key": ""}}

    monkeypatch.setattr(ws, 'get_loaded_config', fake_cfg)

    with pytest.raises(ValueError):
        ws.search_web_kagi("query", 5)
