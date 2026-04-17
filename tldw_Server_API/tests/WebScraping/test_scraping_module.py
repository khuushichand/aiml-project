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
async def test_article_scrape_blocks_on_shared_policy_before_network(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael
    from tldw_Server_API.app.core.Web_Scraping.outbound_policy import (
        WebOutboundPolicyDecision,
    )

    monkeypatch.setattr(ael, "load_and_log_configs", lambda: {"web_scraper": {}})
    async def fake_policy(*args, **kwargs):
        return WebOutboundPolicyDecision(
            allowed=False,
            mode="strict",
            reason="robots_unreachable",
            stage="pre_fetch",
            source="article_extract",
        )

    monkeypatch.setattr(
        ael,
        "decide_web_outbound_policy",
        fake_policy,
        raising=False,
    )

    def fail_http_fetch(*args, **kwargs):
        raise AssertionError("network fetch should not run when outbound policy blocks")

    monkeypatch.setattr(ael, "http_fetch", fail_http_fetch)
    monkeypatch.setattr(ael, "_fetch_with_curl", fail_http_fetch)

    result = await ael.scrape_article("https://example.com/blocked")

    assert result["extraction_successful"] is False
    assert result["error"] == "Blocked by outbound policy"
    assert result["policy_reason"] == "robots_unreachable"


@pytest.mark.asyncio
async def test_extract_links_text_vs_html(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper

    scraper = EnhancedWebScraper()

    # Dummy response to avoid real network
    class DummyResp:
        text = "<html><body><a href='/a'>A</a></body></html>"

        async def aclose(self):
            return None

    async def fake_afetch(*args, **kwargs):  # noqa: ANN001, ARG001
        return DummyResp()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping.afetch",
        fake_afetch,
    )

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
        return {
            "search_engines": {
                "google_search_api_key": "",
                "google_search_engine_id": "",
                "google_search_api_url": "https://customsearch.googleapis.com/customsearch/v1",
                "google_simp_trad_chinese": "1",
                "limit_google_search_to_country": False,
            },
        }

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


def test_preflight_advice_prefers_playwright_for_js():
    from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper

    analysis = {"results": {"js": {"status": "success", "js_required": True}}}
    backend, method, notes = EnhancedWebScraper._apply_preflight_advice(
        analysis, "httpx", "auto", "auto"
    )
    assert method == "playwright"
    assert "js_required" in notes


def test_preflight_advice_prefers_curl_for_tls_when_auto():
    from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper

    analysis = {"results": {"tls": {"status": "active"}}}
    backend, method, notes = EnhancedWebScraper._apply_preflight_advice(
        analysis, "httpx", "auto", "auto"
    )
    assert backend == "curl"
    assert "tls_active" in notes


def test_preflight_advice_respects_explicit_backend():
    from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper

    analysis = {"results": {"tls": {"status": "active"}}}
    backend, method, notes = EnhancedWebScraper._apply_preflight_advice(
        analysis, "httpx", "auto", "httpx"
    )
    assert backend == "httpx"
    assert "tls_active" not in notes


def test_scoring_includes_fingerprint_and_integrity():
    from tldw_Server_API.app.core.Web_Scraping.scraper_analyzers.scoring.scoring_engine import (
        calculate_difficulty_score,
    )

    results = {
        "fingerprint": {
            "status": "success",
            "detected_services": ["DataDome"],
            "canvas_fingerprinting_signal": True,
            "behavioral_listeners_detected": ["mousemove"],
        },
        "integrity": {
            "status": "success",
            "modified_functions": {"HTMLCanvasElement.prototype.toDataURL": "patched"},
        },
    }

    score = calculate_difficulty_score(results)
    assert score["score"] >= 4


def test_recommendations_include_fingerprint_and_integrity_guidance():
    from tldw_Server_API.app.core.Web_Scraping.scraper_analyzers.recommendations.recommender import (
        generate_recommendations,
    )

    results = {
        "fingerprint": {
            "status": "success",
            "detected_services": ["DataDome"],
            "canvas_fingerprinting_signal": True,
            "behavioral_listeners_detected": ["mousemove"],
        },
        "integrity": {
            "status": "success",
            "modified_functions": {"Date.now": "patched"},
        },
    }

    recs = generate_recommendations(results)
    strategy = " ".join(recs.get("strategy", []))
    tools = " ".join(recs.get("tools", []))

    assert "bot detection" in strategy.lower()
    assert "canvas" in strategy.lower()
    assert "timing" in strategy.lower()
    assert "undetected" in tools.lower() or "playwright-stealth" in tools.lower()


@pytest.mark.asyncio
async def test_article_preflight_prefers_playwright_for_js(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael
    from tldw_Server_API.app.core.Web_Scraping import scraper_analyzers as sa
    from tldw_Server_API.app.core.Security import egress as eg

    monkeypatch.setattr(eg, "evaluate_url_policy", lambda url: types.SimpleNamespace(allowed=True))

    def fake_cfg():
        return {
            "web_scraper": {
                "web_scraper_preflight_analyzers": True,
                "web_scraper_preflight_scan_depth": "default",
                "web_scraper_preflight_timeout_s": 0,
                "web_scraper_default_backend": "auto",
                "web_scraper_respect_robots": True,
            }
        }

    monkeypatch.setattr(ael, "load_and_log_configs", fake_cfg)
    async def fake_allowed(*args, **kwargs):
        return True

    monkeypatch.setattr(ael, "is_allowed_by_robots_async", fake_allowed)
    monkeypatch.setattr(
        sa,
        "run_analysis",
        lambda *args, **kwargs: {"results": {"js": {"status": "success", "js_required": True}}},
    )

    playwright_used = {"used": False}

    class FakePage:
        async def goto(self, *args, **kwargs):
            return None

        async def wait_for_load_state(self, *args, **kwargs):
            return None

        async def content(self):
            return "<html><body><article>hello</article></body></html>"

    class FakeContext:
        async def add_cookies(self, *args, **kwargs):
            return None

        async def new_page(self):
            return FakePage()

        async def close(self):
            return None

    class FakeBrowser:
        async def new_context(self, *args, **kwargs):
            return FakeContext()

        async def close(self):
            return None

    class FakeChromium:
        async def launch(self, *args, **kwargs):
            return FakeBrowser()

    class FakePlaywright:
        def __init__(self):
            self.chromium = FakeChromium()

    class FakePlaywrightContext:
        async def __aenter__(self):
            playwright_used["used"] = True
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    def fake_async_playwright():
        return FakePlaywrightContext()

    def fake_extract(*args, **kwargs):
        return {"extraction_successful": True, "content": "ok", "title": "t"}

    monkeypatch.setattr(ael, "async_playwright", fake_async_playwright)
    monkeypatch.setattr(ael, "extract_article_with_pipeline", fake_extract)
    monkeypatch.setattr(ael, "_fetch_with_curl", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(ael, "http_fetch", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))

    result = await ael.scrape_article("https://example.com")
    assert result.get("extraction_successful") is True
    assert playwright_used["used"] is True


@pytest.mark.asyncio
async def test_article_preflight_prefers_curl_for_tls(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as ael
    from tldw_Server_API.app.core.Web_Scraping import scraper_analyzers as sa
    from tldw_Server_API.app.core.Security import egress as eg

    monkeypatch.setattr(eg, "evaluate_url_policy", lambda url: types.SimpleNamespace(allowed=True))

    def fake_cfg():
        return {
            "web_scraper": {
                "web_scraper_preflight_analyzers": True,
                "web_scraper_preflight_scan_depth": "default",
                "web_scraper_preflight_timeout_s": 0,
                "web_scraper_default_backend": "auto",
                "web_scraper_respect_robots": True,
            }
        }

    monkeypatch.setattr(ael, "load_and_log_configs", fake_cfg)
    async def fake_allowed(*args, **kwargs):
        return True

    monkeypatch.setattr(ael, "is_allowed_by_robots_async", fake_allowed)
    monkeypatch.setattr(
        sa,
        "run_analysis",
        lambda *args, **kwargs: {"results": {"tls": {"status": "active"}}},
    )

    curl_used = {"used": False}

    def fake_fetch_with_curl(*args, **kwargs):
        curl_used["used"] = True
        return {"status": 200, "text": "<html><body>ok</body></html>", "backend": "curl"}

    def fake_extract(*args, **kwargs):
        return {"extraction_successful": True, "content": "ok", "title": "t"}

    monkeypatch.setattr(ael, "_fetch_with_curl", fake_fetch_with_curl)
    monkeypatch.setattr(ael, "extract_article_with_pipeline", fake_extract)
    monkeypatch.setattr(ael, "http_fetch", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))

    result = await ael.scrape_article("https://example.com")
    assert result.get("extraction_successful") is True
    assert curl_used["used"] is True
