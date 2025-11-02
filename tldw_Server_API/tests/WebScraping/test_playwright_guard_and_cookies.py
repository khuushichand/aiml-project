import asyncio
import pytest

from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import (
    CookieManager,
    EnhancedWebScraper,
)


pytestmark = pytest.mark.asyncio


async def test_playwright_guard_fallback(monkeypatch):
    scraper = EnhancedWebScraper()

    async def fake_traf(url, custom_cookies=None, user_agent=None, custom_headers=None):
        return {"url": url, "title": "t", "author": "a", "date": "", "content": "c", "extraction_successful": True, "method": "trafilatura"}

    # Ensure browser is None and trafilatura path is used
    scraper._browser = None
    monkeypatch.setattr(scraper, "_scrape_with_trafilatura", fake_traf)

    result = await scraper.scrape_article("https://example.com/x", method="playwright")
    assert result["extraction_successful"] is True
    assert result.get("method") == "trafilatura"


async def test_cookie_manager_accepts_name_value(tmp_path):
    manager = CookieManager(storage_path=tmp_path / "cookies.json")
    try:
        manager.add_cookies("example.com", [{"name": "foo", "value": "bar"}])
        session = await manager.get_session("https://example.com")
        jar = session.cookie_jar.filter_cookies("https://example.com")
        # yarl URL-based filtering returns SimpleCookie
        assert "foo" in jar
        assert jar["foo"].value == "bar"
    finally:
        await manager.close_all()
