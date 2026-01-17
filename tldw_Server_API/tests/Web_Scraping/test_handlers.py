import types
import pytest


def test_resolve_handler_fallback():
    from tldw_Server_API.app.core.Web_Scraping import handlers

    handler = handlers.resolve_handler("not-a-module")
    assert handler is handlers.handle_generic_html


def test_resolve_handler_valid_path():
    from tldw_Server_API.app.core.Web_Scraping import handlers

    handler = handlers.resolve_handler(
        "tldw_Server_API.app.core.Web_Scraping.handlers:handle_generic_html"
    )
    assert handler is handlers.handle_generic_html


@pytest.mark.asyncio
async def test_scrape_article_uses_handler(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael
    from tldw_Server_API.app.core.Security import egress as egress_module

    monkeypatch.setattr(
        egress_module,
        "evaluate_url_policy",
        lambda url: types.SimpleNamespace(allowed=True),
    )
    monkeypatch.setattr(ael, "load_and_log_configs", lambda: {})
    async def allow_robots(*args, **kwargs):
        return True

    monkeypatch.setattr(ael, "is_allowed_by_robots_async", allow_robots)
    monkeypatch.setattr(ael, "_js_required", lambda *args, **kwargs: False)

    def fake_http_fetch(*args, **kwargs):
        return {
            "status": 200,
            "text": "<html><body><p>ok</p></body></html>",
            "headers": {},
        }

    def fake_handler(html, url):
        return {
            "url": url,
            "title": "handled",
            "author": "n/a",
            "date": "n/a",
            "content": "handled-content",
            "extraction_successful": True,
        }

    monkeypatch.setattr(ael, "http_fetch", fake_http_fetch)
    monkeypatch.setattr(ael, "resolve_handler", lambda _: fake_handler)

    result = await ael.scrape_article("https://example.com")
    assert result["title"] == "handled"
    assert result["content"] == "handled-content"
