import pytest

pytestmark = pytest.mark.unit


def test_parse_searx_results_maps_fields():
    from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import parse_searx_results
    out = {}
    raw = {
        "results": [
            {"title": "Example Title", "link": "https://example.com/a", "snippet": "Snippet A", "publishedDate": "2024-01-01"},
            {"title": "B", "url": "https://b.com", "content": "C", "published": "2024-02-02"},
        ]
    }
    parse_searx_results(raw, out)
    assert out.get("processing_error") is None
    assert len(out["results"]) == 2
    first = out["results"][0]
    assert first["title"] == "Example Title"
    assert first["url"].startswith("https://example.com")
    assert first["content"] == "Snippet A"
    assert first["metadata"]["date_published"] == "2024-01-01"


def test_parse_tavily_results_maps_fields():
    from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import parse_tavily_results
    out = {}
    raw = {
        "results": [
            {
                "title": "T",
                "url": "https://t.com",
                "content": "Body",
                "published_date": "2024-03-03",
                "author": "A",
                "language": "en",
                "score": 0.8,
            }
        ]
    }
    parse_tavily_results(raw, out)
    assert out.get("processing_error") is None
    assert len(out["results"]) == 1
    r = out["results"][0]
    assert r["title"] == "T"
    assert r["url"] == "https://t.com"
    assert r["content"] == "Body"
    assert r["metadata"]["date_published"] == "2024-03-03"
    assert r["metadata"]["author"] == "A"
    assert r["metadata"]["language"] == "en"
    assert r["metadata"]["relevance_score"] == 0.8
