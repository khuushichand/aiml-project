from __future__ import annotations

from typing import Any, Dict

import pytest

from tldw_Server_API.app.core.WebSearch import Web_Search as web_search


def test_aggregate_results_returns_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_chat_api_call(**_: Any) -> str:
        return "Aggregated answer text."

    monkeypatch.setattr(web_search, "chat_api_call", fake_chat_api_call)

    relevant_results = {
        "0": {"content": "Summary content", "reasoning": "Contains the answer"}
    }

    result = web_search.aggregate_results(
        relevant_results=relevant_results,
        question="What is the capital of France?",
        sub_questions=[],
        api_endpoint="fake-llm",
    )

    assert result["text"] == "Aggregated answer text."
    assert result["confidence"] == pytest.approx(0.495, abs=1e-3)
    assert result["evidence"][0]["id"] == "0"
    assert result["chunks"]
    assert result["chunks"][0]["chunk_index"] == 1
    assert result["chunks"][0]["generated"] is True


def test_aggregate_results_handles_large_context(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk_calls = {"count": 0}

    def fake_summarize(input_data: str, **_: Any) -> str:
        chunk_calls["count"] += 1
        return f"chunk-summary-{chunk_calls['count']}"

    def fake_chat_api_call(**_: Any) -> str:
        return "Final aggregated answer."

    monkeypatch.setattr(web_search, "summarize", fake_summarize)
    monkeypatch.setattr(web_search, "chat_api_call", fake_chat_api_call)

    large_snippet = "Paris is the capital of France. " * 300  # ~8400 characters
    relevant_results = {
        "0": {"content": large_snippet, "reasoning": "Contains capital info"},
        "1": {"content": large_snippet, "reasoning": "Additional confirmation"},
    }

    result = web_search.aggregate_results(
        relevant_results=relevant_results,
        question="What is the capital of France?",
        sub_questions=[],
        api_endpoint="fake-llm",
    )

    assert result["text"] == "Final aggregated answer."
    assert chunk_calls["count"] >= 2  # Expect at least two chunk summaries
    assert len(result["chunks"]) >= 2
    assert all("summary" in chunk for chunk in result["chunks"])
    assert result["confidence"] > 0.5


@pytest.mark.asyncio
async def test_search_result_relevance_filters_irrelevant_results(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: Dict[str, int] = {"relevance": 0}

    async def fake_scrape_article(url: str) -> Dict[str, Any]:
        return {"content": f"Full article for {url}"}

    def fake_summarize(**_: Any) -> str:
        return "Summarized content"

    responses = iter([
        "Selected Answer: True\nReasoning: Contains the requested information.",
        "Selected Answer: False\nReasoning: Off topic.",
    ])

    def fake_chat_api_call(**_: Any) -> str:
        calls["relevance"] += 1
        return next(responses)

    async def instant_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(web_search, "scrape_article", fake_scrape_article)
    monkeypatch.setattr(web_search, "summarize", fake_summarize)
    monkeypatch.setattr(web_search, "chat_api_call", fake_chat_api_call)
    monkeypatch.setattr(web_search.asyncio, "sleep", instant_sleep)
    monkeypatch.setattr(web_search.random, "uniform", lambda *_: 0.0)

    search_results = [
        {"id": "keep", "url": "https://example.com/keep", "content": "Snippet keep"},
        {"id": "drop", "url": "https://example.com/drop", "content": "Snippet drop"},
    ]

    relevant = await web_search.search_result_relevance(
        search_results=search_results,
        original_question="What is the capital of France?",
        sub_questions=["capital of France"],
        api_endpoint="fake-llm",
    )

    assert "keep" in relevant
    assert relevant["keep"]["content"] == "Summarized content"
    assert "drop" not in relevant
    assert calls["relevance"] == 2


def test_search_web_brave_builds_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response_payload = {"web": {"results": []}}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> Dict[str, Any]:
            return fake_response_payload

    def fake_get(url: str, headers: Dict[str, str], params: Dict[str, Any]) -> DummyResponse:
        fake_get.last_request = {"url": url, "headers": headers, "params": params}  # type: ignore[attr-defined]
        return DummyResponse()

    monkeypatch.setattr(web_search.requests, "get", fake_get)
    monkeypatch.setattr(
        web_search,
        "loaded_config_data",
        {
            "search_engines": {
                "brave_search_ai_api_key": "ai-key",
                "brave_search_api_key": "web-key",
                "search_engine_country_code_brave": "GB",
                "search_result_max_per_query": 7,
            }
        },
    )

    result = web_search.search_web_brave(
        search_term="capital of france",
        country="FR",
        search_lang="fr",
        ui_lang="en",
        result_count=5,
        safesearch="active",
        date_range="w",
        site_blacklist=["example.com", "test.com"],
    )

    assert result == fake_response_payload

    captured = fake_get.last_request  # type: ignore[attr-defined]
    assert captured["headers"]["X-Subscription-Token"] == "ai-key"
    assert captured["params"]["source"] == "ai"
    assert captured["params"]["safeSearch"] == "Active"
    assert captured["params"]["country"] == "FR"
    assert captured["params"]["search_lang"] == "fr"
    assert captured["params"]["ui_lang"] == "en"
    assert captured["params"]["count"] == 5
    assert captured["params"]["freshness"] == "w"
    assert captured["params"]["exclude_sites"] == "example.com,test.com"
