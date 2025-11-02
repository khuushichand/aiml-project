import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app


@pytest.fixture()
def client_with_token(client_user_only):
    """Provide a client with a minimal header expected by the endpoint."""
    # The ingest endpoint declares a required header parameter named 'token'
    class _Client:
        def __init__(self, c):
            self._c = c
        def post(self, *a, **k):
            headers = k.pop('headers', {}) or {}
            headers.setdefault('token', 'test-token')
            return self._c.post(*a, headers=headers, **k)
    return _Client(client_user_only)


def test_friendly_ingest_recursive_flags_forwarding(client_with_token, monkeypatch):
    # Patch the imported symbol used by the media router
    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    captured = {}

    async def fake_process_web_scraping_task(**kwargs):
        # Capture args for assertion
        captured.update(kwargs)
        # Return minimal service-like result
        return {
            "method": "Recursive Scraping",
            "articles": [
                {
                    "url": "https://example.com/",
                    "content": "<html>ok</html>",
                    "extraction_successful": True,
                    "summary": "S",
                }
            ],
        }

    monkeypatch.setattr(media_mod, "process_web_scraping_task", fake_process_web_scraping_task, raising=True)

    payload = {
        "urls": ["https://example.com/"],
        "scrape_method": "recursive_scraping",
        "max_pages": 3,
        "max_depth": 2,
        # Crawl flags
        "crawl_strategy": "default",
        "include_external": True,
        "score_threshold": 0.5,
        # Analysis toggle for coverage
        "perform_analysis": True,
    }
    r = client_with_token.post("/api/v1/media/ingest-web-content", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    assert data.get("count") == 1
    assert data.get("results")[0].get("analysis") == "S"  # mapped from summary

    # Ensure flags forwarded to service
    assert captured.get("scrape_method") == "Recursive Scraping"
    assert captured.get("url_input") == "https://example.com/"
    assert captured.get("crawl_strategy") == "default"
    assert captured.get("include_external") is True
    assert captured.get("score_threshold") == 0.5


def test_friendly_ingest_url_level_flags_forwarding(client_with_token, monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.media as media_mod

    captured = {}

    async def fake_process_web_scraping_task(**kwargs):
        captured.update(kwargs)
        return {
            "method": "URL Level",
            "articles": [
                {
                    "url": "https://example.com/a",
                    "content": "<html>ok</html>",
                    "extraction_successful": True,
                    "summary": "S2",
                }
            ],
        }

    monkeypatch.setattr(media_mod, "process_web_scraping_task", fake_process_web_scraping_task, raising=True)

    payload = {
        "urls": ["https://example.com/"],
        "scrape_method": "url_level",
        "url_level": 2,
        # Crawl flags
        "crawl_strategy": "best_first",
        "include_external": False,
        "score_threshold": 0.0,
    }
    r = client_with_token.post("/api/v1/media/ingest-web-content", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "success"
    assert data.get("count") == 1
    assert data.get("results")[0].get("analysis") == "S2"

    # Ensure forwarding + level handling
    assert captured.get("scrape_method") == "URL Level"
    assert captured.get("url_input") == "https://example.com/"
    assert captured.get("url_level") == 2
    assert captured.get("crawl_strategy") == "best_first"
    assert captured.get("include_external") is False
    assert captured.get("score_threshold") == 0.0
