"""
Integration tests for /api/v1/research/websearch with specific engines.
Monkeypatch provider layer to avoid network.
"""
import os
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

# Disable rate limiting and heavy imports
os.environ["TEST_MODE"] = "true"


def _mini_app_with_user():
    from tldw_Server_API.app.api.v1.endpoints import research as research_module
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

    app = FastAPI()
    app.include_router(research_module.router, prefix="/api/v1/research")

    async def override_user():
        return User(id=1, username="tester", email="t@e.com", is_active=True, is_admin=True)

    app.dependency_overrides[get_request_user] = override_user
    return app


def test_websearch_searx_engine(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws

    def fake_perform_websearch(search_engine, search_query, *args, **kwargs):
        assert search_engine == "searx"
        return {
            "results": [
                {
                    "title": "Searx Result",
                    "url": "https://searx.example/result",
                    "content": "An example.",
                    "metadata": {"date_published": None},
                }
            ],
            "total_results_found": 1,
            "search_time": 0.01,
        }

    monkeypatch.setattr(ws, "perform_websearch", fake_perform_websearch)

    app = _mini_app_with_user()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/research/websearch",
            json={"query": "q", "engine": "searx", "result_count": 3, "aggregate": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "web_search_results_dict" in data
        assert data["web_search_results_dict"]["results"]


def test_websearch_tavily_engine(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws

    def fake_perform_websearch(search_engine, search_query, *args, **kwargs):
        assert search_engine == "tavily"
        return {
            "results": [
                {
                    "title": "Tavily Result",
                    "url": "https://tavily.example/article",
                    "content": "Content.",
                    "metadata": {"date_published": "2024-01-01"},
                }
            ],
            "total_results_found": 1,
            "search_time": 0.02,
        }

    monkeypatch.setattr(ws, "perform_websearch", fake_perform_websearch)

    app = _mini_app_with_user()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/research/websearch",
            json={"query": "q", "engine": "tavily", "result_count": 3, "aggregate": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "web_search_results_dict" in data
        assert data["web_search_results_dict"]["results"]


def test_websearch_kagi_engine(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws

    def fake_perform_websearch(search_engine, search_query, *args, **kwargs):
        assert search_engine == "kagi"
        return {
            "results": [
                {
                    "title": "Kagi Result",
                    "url": "https://kagi.example/article",
                    "content": "Kagi content.",
                    "metadata": {"date_published": None},
                }
            ],
            "total_results_found": 1,
            "search_time": 0.01,
        }

    monkeypatch.setattr(ws, "perform_websearch", fake_perform_websearch)

    app = _mini_app_with_user()
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/research/websearch",
            json={"query": "q", "engine": "kagi", "result_count": 2, "aggregate": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "web_search_results_dict" in data
        assert data["web_search_results_dict"]["results"]
