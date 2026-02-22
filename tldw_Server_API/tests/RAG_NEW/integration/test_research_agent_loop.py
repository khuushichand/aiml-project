import pytest

from tldw_Server_API.app.core.RAG.rag_service.query_classifier import QueryClassification
from tldw_Server_API.app.core.RAG.rag_service import research_agent as ra


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_research_loop_executes_web_and_academic_actions_without_double_processing(monkeypatch):
    import tldw_Server_API.app.core.Chat.chat_service as chat_service
    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    llm_responses = iter([
        '{"reasoning":"Need current context first","action":"web_search","params":{"query":"latest rag updates","result_count":1}}',
        '{"reasoning":"Need papers too","action":"academic_search","params":{"query":"rag benchmarks","result_count":1}}',
        '{"reasoning":"Enough evidence","action":"done","params":{"reason":"enough information"}}',
    ])

    async def _fake_chat_call_async(**_kwargs):  # noqa: ANN001
        return next(llm_responses)

    captured = {"process_calls": 0, "to_thread_calls": 0}

    def _fake_perform_websearch(**kwargs):  # noqa: ANN003
        query = str(kwargs.get("search_query", ""))
        if "site:arxiv.org" in query:
            return {
                "results": [
                    {
                        "title": "RAG Benchmark Paper",
                        "href": "https://arxiv.org/abs/2501.00001",
                        "body": "Academic abstract",
                    }
                ]
            }
        return {
            "results": [
                {
                    "title": "RAG News",
                    "url": "https://example.com/rag-news",
                    "content": "Recent RAG updates",
                }
            ]
        }

    def _fake_process(payload, engine):  # noqa: ANN001
        captured["process_calls"] += 1
        assert engine == "duckduckgo"
        first = payload["results"][0]
        assert "href" in first, "process_web_search_results should only run for raw academic payloads"
        return {
            "results": [
                {
                    "title": first.get("title", ""),
                    "url": first.get("href", ""),
                    "content": first.get("body", ""),
                }
            ]
        }

    async def _fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        captured["to_thread_calls"] += 1
        return func(*args, **kwargs)

    monkeypatch.setattr(chat_service, "perform_chat_api_call_async", _fake_chat_call_async)
    monkeypatch.setattr(web_apis, "perform_websearch", _fake_perform_websearch)
    monkeypatch.setattr(web_apis, "process_web_search_results", _fake_process)
    monkeypatch.setattr(ra.asyncio, "to_thread", _fake_to_thread)

    classification = QueryClassification(
        skip_search=False,
        search_local_db=False,
        search_web=True,
        search_academic=True,
        search_discussions=False,
        standalone_query="latest rag updates and benchmark papers",
        detected_intent="analytical",
    )

    output = await ra.research_loop(
        query="latest rag updates and benchmark papers",
        classification=classification,
        mode="balanced",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        max_iterations=3,
    )

    assert output.completed is True
    assert output.total_iterations == 3
    assert output.total_results == 2
    assert captured["to_thread_calls"] == 2
    assert captured["process_calls"] == 1
    sources = {item.get("source") for item in output.all_results}
    assert "web" in sources
    assert "academic" in sources


@pytest.mark.asyncio
async def test_research_loop_auto_injects_reasoning_preamble_in_balanced_mode(monkeypatch):
    import tldw_Server_API.app.core.Chat.chat_service as chat_service
    import tldw_Server_API.app.core.Web_Scraping.WebSearch_APIs as web_apis

    llm_responses = iter([
        '{"reasoning":"Need current context first","action":"web_search","params":{"query":"latest rag updates","result_count":1}}',
        '{"reasoning":"Enough evidence","action":"done","params":{"reason":"enough information"}}',
    ])

    async def _fake_chat_call_async(**_kwargs):  # noqa: ANN001
        return next(llm_responses)

    def _fake_perform_websearch(**_kwargs):  # noqa: ANN001
        return {
            "results": [
                {
                    "title": "RAG News",
                    "url": "https://example.com/rag-news",
                    "content": "Recent RAG updates",
                }
            ]
        }

    async def _fake_to_thread(func, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(chat_service, "perform_chat_api_call_async", _fake_chat_call_async)
    monkeypatch.setattr(web_apis, "perform_websearch", _fake_perform_websearch)
    monkeypatch.setattr(ra.asyncio, "to_thread", _fake_to_thread)

    classification = QueryClassification(
        skip_search=False,
        search_local_db=False,
        search_web=True,
        search_academic=False,
        search_discussions=False,
        standalone_query="latest rag updates",
        detected_intent="analytical",
    )

    output = await ra.research_loop(
        query="latest rag updates",
        classification=classification,
        mode="balanced",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        max_iterations=2,
    )

    assert output.completed is True
    assert output.total_iterations == 2
    assert output.steps[0].action_name == "web_search"
    assert output.metadata["reasoning_preamble"]["required"] is True
    assert output.metadata["reasoning_preamble"]["completed"] is True
    assert output.metadata["reasoning_preamble"]["manual_calls"] == 0
    assert output.metadata["reasoning_preamble"]["auto_injected"] == 1
