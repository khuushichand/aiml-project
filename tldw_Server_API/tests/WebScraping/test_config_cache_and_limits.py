import asyncio
import types

import pytest

from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as WSA
from tldw_Server_API.app.core.Web_Scraping.enhanced_web_scraping import EnhancedWebScraper


def test_config_cached(monkeypatch):
    calls = {"n": 0}

    def fake_loader():
        calls["n"] += 1
        return {"search_engines": {}, "Web-Scraping": {}}

    # Ensure a cold cache
    WSA.get_loaded_config.cache_clear()
    monkeypatch.setattr(WSA, "load_and_log_configs", fake_loader)

    c1 = WSA.get_loaded_config()
    c2 = WSA.get_loaded_config()
    assert c1 is c2
    assert calls["n"] == 1


def test_enhanced_scraper_concurrency_config_parsing():
    cfg = {
        "max_rps": "3.5",
        "max_rpm": "7",
        "max_rph": "9",
        "connector_limit": "11",
        "connector_limit_per_host": "4",
        "max_concurrent": "6",
    }
    scraper = EnhancedWebScraper(config=cfg)
    assert abs(scraper.rate_limiter.max_rps - 3.5) < 1e-6
    assert scraper.rate_limiter.max_rpm == 7
    assert scraper.rate_limiter.max_rph == 9
    assert scraper.cookie_manager._connector_limit == 11
    assert scraper.cookie_manager._per_host_limit == 4
    assert scraper.job_queue.max_concurrent == 6


@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_skips(monkeypatch):
    # Arrange: force breaker to open after 2 failures
    def fake_cfg():
        return {
            "search_engines": {},
            "Web-Scraping": {
                "llm_cb_fail_threshold": 2,
                "llm_cb_reset_after_s": 60,
                "relevance_llm_timeout_s": 0.1,
                "relevance_scrape_timeout_s": 0.1,
            },
        }

    WSA.get_loaded_config.cache_clear()
    monkeypatch.setattr(WSA, "load_and_log_configs", fake_cfg)

    calls = {"n": 0}

    def fail_call(**kwargs):
        calls["n"] += 1
        raise RuntimeError("rate limited")

    monkeypatch.setattr(WSA, "chat_api_call", fail_call)

    # 5 results; after 2 failures, breaker should open and skip remaining LLM calls
    results = [{"content": "x", "url": f"https://e/{i}"} for i in range(5)]
    out = await WSA.search_result_relevance(
        results,
        original_question="q",
        sub_questions=[],
        api_endpoint="openai",
    )
    assert isinstance(out, dict)
    assert calls["n"] == 2
