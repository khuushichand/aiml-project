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
                "archived": True,
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
    assert r["metadata"]["archived"] is True


def test_search_web_4chan_include_archived(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws
    from tldw_Server_API.app.core.Security import egress as eg
    from tldw_Server_API.app.core import http_client as hc

    monkeypatch.setattr(ws, "get_loaded_config", lambda: {"search_engines": {}})
    monkeypatch.setattr(
        eg,
        "evaluate_url_policy",
        lambda url: type("Policy", (), {"allowed": True, "reason": None})(),
    )

    seen_urls: list[str] = []

    def fake_fetch_json(*, method: str, url: str, headers=None, timeout=15.0, **kwargs):
        seen_urls.append(url)
        if url.endswith("/catalog.json"):
            return [{"threads": [{"no": 111, "sub": "Other topic", "com": "No match", "time": 1700000000}]}]
        if url.endswith("/archive.json"):
            return [222]
        if url.endswith("/thread/222.json"):
            return {
                "posts": [
                    {
                        "no": 222,
                        "sub": "Rust memory safety",
                        "com": "Discussing Rust ownership and memory safety.",
                        "name": "Anonymous",
                        "time": 1700000100,
                    }
                ]
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(hc, "fetch_json", fake_fetch_json)

    result = ws.search_web_4chan(
        "rust memory safety",
        result_count=5,
        search_params={
            "boards": ["g"],
            "max_threads_per_board": 5,
            "include_archived": True,
        },
    )

    assert result["include_archived"] is True
    assert any(url.endswith("/archive.json") for url in seen_urls)
    assert any(url.endswith("/thread/222.json") for url in seen_urls)
    assert result["results"]
    first = result["results"][0]
    assert first["thread_no"] == 222
    assert first["archived"] is True


def test_search_web_4chan_excludes_archive_when_disabled(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws
    from tldw_Server_API.app.core.Security import egress as eg
    from tldw_Server_API.app.core import http_client as hc

    monkeypatch.setattr(ws, "get_loaded_config", lambda: {"search_engines": {}})
    monkeypatch.setattr(
        eg,
        "evaluate_url_policy",
        lambda url: type("Policy", (), {"allowed": True, "reason": None})(),
    )

    seen_urls: list[str] = []

    def fake_fetch_json(*, method: str, url: str, headers=None, timeout=15.0, **kwargs):
        seen_urls.append(url)
        if url.endswith("/catalog.json"):
            return [
                {
                    "threads": [
                        {
                            "no": 7001,
                            "sub": "Rust memory safety",
                            "com": "Catalog-only thread content",
                            "time": 1700000000,
                        }
                    ]
                }
            ]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(hc, "fetch_json", fake_fetch_json)

    result = ws.search_web_4chan(
        "rust memory safety",
        result_count=5,
        search_params={
            "boards": ["g"],
            "include_archived": False,
        },
    )

    assert result["include_archived"] is False
    assert result["total_results_found"] == 1
    assert all(not url.endswith("/archive.json") for url in seen_urls)
    assert all("/thread/" not in url for url in seen_urls)


def test_search_web_4chan_dedupes_catalog_and_archive_thread(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws
    from tldw_Server_API.app.core.Security import egress as eg
    from tldw_Server_API.app.core import http_client as hc

    monkeypatch.setattr(ws, "get_loaded_config", lambda: {"search_engines": {}})
    monkeypatch.setattr(
        eg,
        "evaluate_url_policy",
        lambda url: type("Policy", (), {"allowed": True, "reason": None})(),
    )

    def fake_fetch_json(*, method: str, url: str, headers=None, timeout=15.0, **kwargs):
        if url.endswith("/catalog.json"):
            return [
                {
                    "threads": [
                        {
                            "no": 111,
                            "sub": "Rust memory safety thread",
                            "com": "Catalog OP content",
                            "time": 1700000000,
                            "replies": 3,
                            "images": 1,
                        }
                    ]
                }
            ]
        if url.endswith("/archive.json"):
            return [111]
        if url.endswith("/thread/111.json"):
            return {
                "posts": [
                    {
                        "no": 111,
                        "sub": "Rust memory safety thread (archived)",
                        "com": "Archived OP content",
                        "time": 1700000100,
                    }
                ]
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(hc, "fetch_json", fake_fetch_json)

    result = ws.search_web_4chan(
        "rust memory safety",
        result_count=10,
        search_params={
            "boards": ["g"],
            "max_threads_per_board": 20,
            "max_archived_threads_per_board": 20,
            "include_archived": True,
        },
    )

    assert result["total_results_found"] == 1
    assert len(result["results"]) == 1
    first = result["results"][0]
    assert first["thread_no"] == 111
    assert first["board"] == "g"
    assert first["archived"] is False


def test_search_web_4chan_dedupe_merges_best_metadata(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws
    from tldw_Server_API.app.core.Security import egress as eg
    from tldw_Server_API.app.core import http_client as hc

    monkeypatch.setattr(ws, "get_loaded_config", lambda: {"search_engines": {}})
    monkeypatch.setattr(
        eg,
        "evaluate_url_policy",
        lambda url: type("Policy", (), {"allowed": True, "reason": None})(),
    )

    def fake_fetch_json(*, method: str, url: str, headers=None, timeout=15.0, **kwargs):
        if url.endswith("/catalog.json"):
            return [
                {
                    "threads": [
                        {
                            "no": 444,
                            "com": "Rust memory safety",
                            "time": 1700000000,
                            "replies": 1,
                            "images": 0,
                        }
                    ]
                }
            ]
        if url.endswith("/archive.json"):
            return [444]
        if url.endswith("/thread/444.json"):
            return {
                "posts": [
                    {
                        "no": 444,
                        "sub": "Rust memory safety archived deep dive",
                        "com": "Archived content has significantly more detail about ownership and borrowing.",
                        "time": 1700000300,
                    },
                    {"no": 445, "tim": 123},
                    {"no": 446, "tim": 124},
                ]
            }
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(hc, "fetch_json", fake_fetch_json)

    result = ws.search_web_4chan(
        "rust memory safety",
        result_count=10,
        search_params={
            "boards": ["g"],
            "max_threads_per_board": 20,
            "max_archived_threads_per_board": 20,
            "include_archived": True,
        },
    )

    assert result["total_results_found"] == 1
    first = result["results"][0]
    assert first["archived"] is False
    assert first["title"] == "Rust memory safety archived deep dive"
    assert "ownership and borrowing" in first["content"]
    assert first["time_epoch"] == 1700000300
    assert first["images"] == 2
    assert first["score"] >= 6.0


def test_search_web_4chan_board_level_partial_failure(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws
    from tldw_Server_API.app.core.Security import egress as eg
    from tldw_Server_API.app.core import http_client as hc

    monkeypatch.setattr(ws, "get_loaded_config", lambda: {"search_engines": {}})
    monkeypatch.setattr(
        eg,
        "evaluate_url_policy",
        lambda url: type("Policy", (), {"allowed": True, "reason": None})(),
    )

    def fake_fetch_json(*, method: str, url: str, headers=None, timeout=15.0, **kwargs):
        if "/g/catalog.json" in url:
            raise TimeoutError("catalog timeout")
        if "/tv/catalog.json" in url:
            return [
                {
                    "threads": [
                        {
                            "no": 90210,
                            "sub": "Rust memory safety",
                            "com": "Thread from tv board",
                            "time": 1700000500,
                        }
                    ]
                }
            ]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(hc, "fetch_json", fake_fetch_json)

    result = ws.search_web_4chan(
        "rust memory safety",
        result_count=10,
        search_params={
            "boards": ["g", "tv"],
            "include_archived": False,
        },
    )

    assert result["total_results_found"] == 1
    assert result["results"][0]["board"] == "tv"
    assert "warnings" in result
    assert any(
        warning.get("board") == "g" and warning.get("phase") == "catalog"
        for warning in result["warnings"]
    )
    assert "error" not in result


def test_search_web_4chan_board_level_all_failures(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws
    from tldw_Server_API.app.core.Security import egress as eg
    from tldw_Server_API.app.core import http_client as hc

    monkeypatch.setattr(ws, "get_loaded_config", lambda: {"search_engines": {}})
    monkeypatch.setattr(
        eg,
        "evaluate_url_policy",
        lambda url: type("Policy", (), {"allowed": True, "reason": None})(),
    )

    def fake_fetch_json(*, method: str, url: str, headers=None, timeout=15.0, **kwargs):
        if url.endswith("/catalog.json"):
            raise ConnectionError("catalog unavailable")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(hc, "fetch_json", fake_fetch_json)

    result = ws.search_web_4chan(
        "rust memory safety",
        result_count=10,
        search_params={
            "boards": ["g", "tv"],
            "include_archived": False,
        },
    )

    assert result["results"] == []
    assert result["total_results_found"] == 0
    assert len(result.get("warnings", [])) == 2
    assert result.get("error") == "4chan search failed for all requested boards."
