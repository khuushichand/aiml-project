import asyncio

import types

from tldw_Server_API.app.core.Web_Scraping import Article_Extractor_Lib as AEL


class DummyResp:
    def __init__(self, text: str):
        self.data = {"status": 200, "text": text, "url": "https://example.com", "headers": {}, "backend": "httpx"}
    def __getitem__(self, k):
        return self.data[k]


class DummyAsyncPlaywright:
    async def __aenter__(self):
        # Raise so we don't actually try to launch browsers in tests
        raise RuntimeError("playwright disabled in test")
    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_js_required_emits_fallback_metric(monkeypatch):
    # stub robots allow
    monkeypatch.setattr(AEL, "is_allowed_by_robots_async", lambda *a, **k: asyncio.Future())
    f = asyncio.Future(); f.set_result(True)
    monkeypatch.setattr(AEL, "is_allowed_by_robots_async", lambda *a, **k: f)

    # stub http fetch to return JS-required HTML
    monkeypatch.setattr(AEL, "http_fetch", lambda *a, **k: DummyResp("Please enable JavaScript to continue"))

    # stub async_playwright to avoid launching
    monkeypatch.setattr(AEL, "async_playwright", lambda: DummyAsyncPlaywright())

    # capture metrics
    calls = []
    def _log_counter(name, labels=None):
        calls.append((name, dict(labels or {})))
    monkeypatch.setattr(AEL, "log_counter", _log_counter)

    # run
    res = asyncio.get_event_loop().run_until_complete(AEL.scrape_article("https://example.com"))
    assert res["extraction_successful"] is False
    # Ensure js_required metric was emitted at least once
    js_fallbacks = [c for c in calls if c[0] == "scrape_playwright_fallback_total" and c[1].get("reason") == "js_required"]
    assert js_fallbacks, f"expected js_required fallback metric, got: {calls}"
