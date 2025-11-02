import os
import pytest

pytestmark = pytest.mark.unit


def test_aggregate_results_schema(monkeypatch):
    from tldw_Server_API.app.core.Web_Scraping import WebSearch_APIs as ws

    # Arrange: fake LLM call returns a simple string
    def fake_chat_api_call(**kwargs):
        return "This is a synthesized final answer."

    monkeypatch.setattr(ws, "chat_api_call", lambda *args, **kwargs: fake_chat_api_call(**kwargs))

    relevant_results = {
        "0": {"content": "Snippet 1", "reasoning": "Relevant due to match"},
        "1": {"content": "Snippet 2", "reasoning": "Also relevant"},
    }

    # Act
    result = ws.aggregate_results(
        relevant_results=relevant_results,
        question="what is the capital of france",
        sub_questions=[],
        api_endpoint="openai",
    )

    # Assert: matches WebSearchFinalAnswer shape (text/evidence/confidence/chunks)
    assert isinstance(result, dict)
    assert set(["text", "evidence", "confidence", "chunks"]).issubset(result.keys())
    assert isinstance(result["text"], str)
    assert isinstance(result["evidence"], list)
    assert isinstance(result["confidence"], float)
    assert isinstance(result["chunks"], list)
