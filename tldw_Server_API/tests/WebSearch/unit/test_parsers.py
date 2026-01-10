import json
import pytest

from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import (
    parse_duckduckgo_results,
    parse_brave_results,
    parse_google_results,
    parse_kagi_results,
)


pytestmark = pytest.mark.unit


def test_parse_duckduckgo_results_minimal():
    raw = {
        "results": [
            {"title": "Example", "href": "https://example.com", "body": "A snippet"}
        ]
    }
    out = {"results": []}
    parse_duckduckgo_results(raw, out)
    assert out["results"], "results should not be empty"
    item = out["results"][0]
    assert item["title"] == "Example"
    assert item["url"] == "https://example.com"
    assert item["content"] == "A snippet"
    assert "metadata" in item


def test_parse_brave_results_minimal():
    raw = {
        "query": {"original": "test", "country": "US"},
        "web": {
            "results": [
                {
                    "title": "Brave Result",
                    "url": "https://brave.example",
                    "description": "desc",
                    "profile": {"name": "source"},
                }
            ]
        },
        "mixed": {"main": [1, 2, 3]},
    }
    out = {"results": []}
    parse_brave_results(raw, out)
    assert out["results"], "results should not be empty"
    item = out["results"][0]
    assert item["title"] == "Brave Result"
    assert item["url"].startswith("https://")
    assert "content" in item


def test_parse_google_results_minimal():
    raw = {
        "searchInformation": {"totalResults": "1", "searchTime": 0.12},
        "queries": {"request": [{"searchTerms": "q", "language": "en", "count": 1}]},
        "items": [
            {
                "title": "Google Item",
                "link": "https://google.example",
                "snippet": "snippet",
                "pagemap": {"metatags": [{"article:published_time": "2020-01-01", "article:author": "A"}]},
            }
        ],
    }
    out = {"results": []}
    parse_google_results(raw, out)
    assert out["results"], "results should not be empty"
    item = out["results"][0]
    assert item["title"] == "Google Item"
    assert item["url"].startswith("https://")
    assert item["content"] == "snippet"


def test_parse_kagi_results_minimal():
    raw = {
        "meta": {"ms": 120, "id": "abc"},
        "data": [
            {"t": 0, "title": "Kagi", "url": "https://kagi.example", "snippet": "k-snippet"},
            {"t": 1, "list": ["related 1", "related 2"]},
        ],
    }
    out = {"results": []}
    parse_kagi_results(raw, out)
    assert out.get("total_results_found", 0) >= 1
    assert out["results"], "results should not be empty"
    first = out["results"][0]
    assert first["title"] == "Kagi"
    assert first["url"].startswith("https://")
