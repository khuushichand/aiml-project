from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.services import web_scraping_service as ws_service


def _base_kwargs(**overrides):
    payload = {
        "scrape_method": "Recursive Scraping",
        "url_input": "https://example.com",
        "url_level": None,
        "max_pages": 5,
        "max_depth": 2,
        "summarize_checkbox": False,
        "custom_prompt": None,
        "api_name": None,
        "api_key": None,
        "keywords": "",
        "custom_titles": None,
        "system_prompt": None,
        "temperature": 0.7,
        "custom_cookies": None,
        "mode": "ephemeral",
        "user_id": 1,
        "user_agent": None,
        "custom_headers": None,
        "crawl_strategy": None,
        "include_external": None,
        "score_threshold": None,
    }
    payload.update(overrides)
    return payload


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_web_scraping_accepts_default_strategy(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeService:
        async def process_web_scraping_task(self, **kwargs):
            captured.update(kwargs)
            return {"status": "ok", "articles": []}

    monkeypatch.setattr(ws_service, "get_web_scraping_service", lambda: _FakeService())

    result = await ws_service.process_web_scraping_task(
        **_base_kwargs(crawl_strategy="default")
    )

    assert result["status"] == "ok"
    assert captured.get("crawl_strategy") == "default"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_web_scraping_canonicalizes_bestfirst_aliases(monkeypatch):
    captured: dict[str, object] = {}

    class _FakeService:
        async def process_web_scraping_task(self, **kwargs):
            captured.update(kwargs)
            return {"status": "ok", "articles": []}

    monkeypatch.setattr(ws_service, "get_web_scraping_service", lambda: _FakeService())

    await ws_service.process_web_scraping_task(
        **_base_kwargs(crawl_strategy="bestfirst")
    )

    assert captured.get("crawl_strategy") == "best_first"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_web_scraping_rejects_invalid_strategy():
    with pytest.raises(HTTPException) as exc_info:
        await ws_service.process_web_scraping_task(
            **_base_kwargs(crawl_strategy="fifo")
        )

    assert exc_info.value.status_code == 400
    assert "Invalid crawl_strategy" in str(exc_info.value.detail)
    assert "default" in str(exc_info.value.detail)
    assert "best_first" in str(exc_info.value.detail)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_web_scraping_rejects_invalid_score_threshold():
    with pytest.raises(HTTPException) as exc_info:
        await ws_service.process_web_scraping_task(
            **_base_kwargs(score_threshold=1.5)
        )

    assert exc_info.value.status_code == 400
    assert "score_threshold must be between 0.0 and 1.0 inclusive" in str(
        exc_info.value.detail
    )


@pytest.mark.unit
def test_process_web_scraping_endpoint_returns_400_for_invalid_strategy(client_user_only):
    payload = {
        "scrape_method": "Recursive Scraping",
        "url_input": "https://example.com",
        "mode": "ephemeral",
        "max_pages": 5,
        "max_depth": 2,
        "crawl_strategy": "fifo",
    }

    response = client_user_only.post("/api/v1/media/process-web-scraping", json=payload)
    assert response.status_code == 400
    body = response.json()
    assert "Invalid crawl_strategy" in body.get("detail", "")
