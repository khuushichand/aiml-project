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


def test_parse_exa_results_maps_fields():
    from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import parse_exa_results
    out = {}
    raw = {
        "results": [
            {
                "title": "Exa Title",
                "url": "https://exa.example",
                "summary": "Summary text",
                "publishedDate": "2024-05-05",
                "author": "Author",
                "language": "en",
                "score": 0.9,
            }
        ]
    }
    parse_exa_results(raw, out)
    assert out.get("processing_error") is None
    assert len(out["results"]) == 1
    r = out["results"][0]
    assert r["title"] == "Exa Title"
    assert r["url"] == "https://exa.example"
    assert r["content"] == "Summary text"
    assert r["metadata"]["date_published"] == "2024-05-05"
    assert r["metadata"]["author"] == "Author"
    assert r["metadata"]["language"] == "en"
    assert r["metadata"]["relevance_score"] == 0.9


def test_parse_firecrawl_results_maps_fields():
    from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import parse_firecrawl_results
    out = {}
    raw = {
        "data": [
            {
                "title": "Firecrawl Title",
                "url": "https://firecrawl.example",
                "description": "Description text",
                "publishedDate": "2024-06-06",
                "author": "Author",
                "language": "en",
                "score": 0.7,
            }
        ]
    }
    parse_firecrawl_results(raw, out)
    assert out.get("processing_error") is None
    assert len(out["results"]) == 1
    r = out["results"][0]
    assert r["title"] == "Firecrawl Title"
    assert r["url"] == "https://firecrawl.example"
    assert r["content"] == "Description text"
    assert r["metadata"]["date_published"] == "2024-06-06"
    assert r["metadata"]["author"] == "Author"
    assert r["metadata"]["language"] == "en"
    assert r["metadata"]["relevance_score"] == 0.7


def test_parse_serper_results_maps_fields():
    from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import parse_serper_results

    out = {}
    raw = {
        "organic": [
            {
                "title": "Serper Title",
                "link": "https://serper.example/article",
                "snippet": "Serper snippet",
                "date": "2024-07-07",
                "position": 1,
            }
        ]
    }
    parse_serper_results(raw, out)
    assert out.get("processing_error") is None
    assert len(out["results"]) == 1
    r = out["results"][0]
    assert r["title"] == "Serper Title"
    assert r["url"] == "https://serper.example/article"
    assert r["content"] == "Serper snippet"
    assert r["metadata"]["date_published"] == "2024-07-07"
    assert r["metadata"]["source"] == "serper.example"
    assert r["metadata"]["relevance_score"] == 1


def test_parse_4chan_results_maps_fields():
    from tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs import parse_4chan_results

    out = {}
    raw = {
        "results": [
            {
                "title": "/g/ Thread 123",
                "url": "https://boards.4chan.org/g/thread/123",
                "content": "Snippet from OP post",
                "publishedDate": "2026-02-08T00:00:00Z",
                "author": "Anonymous",
                "source": "4chan",
                "score": 4.2,
                "board": "g",
                "thread_no": 123,
                "replies": 20,
                "images": 5,
            }
        ]
    }
    parse_4chan_results(raw, out)
    assert out.get("processing_error") is None
    assert len(out["results"]) == 1
    r = out["results"][0]
    assert r["title"] == "/g/ Thread 123"
    assert r["url"] == "https://boards.4chan.org/g/thread/123"
    assert r["content"] == "Snippet from OP post"
    assert r["metadata"]["date_published"] == "2026-02-08T00:00:00Z"
    assert r["metadata"]["author"] == "Anonymous"
    assert r["metadata"]["source"] == "4chan"
    assert r["metadata"]["relevance_score"] == 4.2
    assert r["metadata"]["board"] == "g"
    assert r["metadata"]["thread_no"] == 123
    assert r["metadata"]["replies"] == 20
    assert r["metadata"]["images"] == 5
