import pytest

from tldw_Server_API.app.core.RAG.rag_service.query_classifier import QueryClassification
from tldw_Server_API.app.core.RAG.rag_service.research_agent import create_default_registry


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_registry_disables_url_scrape_action_when_requested():
    registry = create_default_registry(enable_url_scraping=False)
    assert registry.get("scrape_url") is None
    assert registry.get("discussion_search") is not None
    assert registry.get("done") is not None


@pytest.mark.asyncio
async def test_discussion_action_uses_configured_default_platforms(monkeypatch):
    captured: dict[str, object] = {}

    async def _fake_search_discussions(query, platforms=None, max_results=10, search_engine="duckduckgo"):  # noqa: ANN001
        captured["query"] = query
        captured["platforms"] = platforms
        captured["max_results"] = max_results
        captured["search_engine"] = search_engine
        return [
            {
                "title": "Thread",
                "url": "https://reddit.com/r/test/comments/1",
                "content": "Community answer",
                "source": "discussion",
                "platform": "reddit",
            }
        ]

    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    monkeypatch.setattr(web_apis, "search_discussions", _fake_search_discussions)

    registry = create_default_registry(
        discussion_platforms=["reddit", "stackoverflow"],
        enable_url_scraping=True,
    )
    classification = QueryClassification(
        skip_search=False,
        search_local_db=False,
        search_web=False,
        search_academic=False,
        search_discussions=True,
        standalone_query="community feedback",
        detected_intent="exploratory",
    )
    available_names = {a.name for a in registry.get_available(classification)}
    assert "discussion_search" in available_names

    out = await registry.execute("discussion_search", {"query": "community feedback"})
    assert out.success is True
    assert out.result_count == 1
    assert captured.get("platforms") == ["reddit", "stackoverflow"]


@pytest.mark.asyncio
async def test_web_search_action_uses_to_thread_and_skips_reprocessing(monkeypatch):
    import tldw_Server_API.app.core.RAG.rag_service.research_agent as ra
    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    captured: dict[str, object] = {}

    def _fake_perform_websearch(**kwargs):  # noqa: ANN003
        captured["search_query"] = kwargs.get("search_query")
        return {
            "results": [
                {
                    "title": "Latest RAG Update",
                    "url": "https://example.com/rag-update",
                    "content": "New retrieval pipeline details.",
                }
            ]
        }

    def _fail_process(_payload, _engine):  # noqa: ANN001
        raise AssertionError("process_web_search_results should not be called for normalized payloads")

    async def _fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        captured["to_thread_called"] = True
        captured["to_thread_func"] = getattr(func, "__name__", str(func))
        return func(*args, **kwargs)

    monkeypatch.setattr(web_apis, "perform_websearch", _fake_perform_websearch)
    monkeypatch.setattr(web_apis, "process_web_search_results", _fail_process)
    monkeypatch.setattr(ra.asyncio, "to_thread", _fake_to_thread)

    registry = create_default_registry(enable_url_scraping=True)
    out = await registry.execute(
        "web_search",
        {"query": "latest rag update", "engine": "duckduckgo", "result_count": 1},
    )

    assert captured.get("to_thread_called") is True
    assert out.success is True
    assert out.result_count == 1
    assert out.results[0]["url"] == "https://example.com/rag-update"
    assert out.results[0]["source"] == "web"


@pytest.mark.asyncio
async def test_academic_search_action_processes_raw_results_once(monkeypatch):
    import tldw_Server_API.app.core.RAG.rag_service.research_agent as ra
    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    captured = {"process_calls": 0, "to_thread_calls": 0}

    def _fake_perform_websearch(**kwargs):  # noqa: ANN003
        assert "site:arxiv.org" in str(kwargs.get("search_query", ""))
        return {
            "results": [
                {
                    "title": "RAG Paper",
                    "href": "https://arxiv.org/abs/1234.5678",
                    "body": "Paper abstract snippet.",
                }
            ]
        }

    def _fake_process(payload, engine):  # noqa: ANN001
        captured["process_calls"] += 1
        assert engine == "duckduckgo"
        result = payload["results"][0]
        return {
            "results": [
                {
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "content": result.get("body", ""),
                }
            ]
        }

    async def _fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        captured["to_thread_calls"] += 1
        return func(*args, **kwargs)

    monkeypatch.setattr(web_apis, "perform_websearch", _fake_perform_websearch)
    monkeypatch.setattr(web_apis, "process_web_search_results", _fake_process)
    monkeypatch.setattr(ra.asyncio, "to_thread", _fake_to_thread)

    registry = create_default_registry(enable_url_scraping=True)
    out = await registry.execute(
        "academic_search",
        {"query": "rag benchmark", "result_count": 1},
    )

    assert captured["to_thread_calls"] == 1
    assert captured["process_calls"] == 1
    assert out.success is True
    assert out.result_count == 1
    assert out.results[0]["url"] == "https://arxiv.org/abs/1234.5678"
    assert out.results[0]["source"] == "academic"
