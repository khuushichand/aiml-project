import json

import pytest

from tldw_Server_API.app.core.Slides.slides_generator import (
    SlidesGenerator,
    SlidesGenerationOutputError,
    SlidesSourceTooLargeError,
)


def _stub_llm_call(api_provider=None, messages=None, **kwargs):
    user_content = ""
    if messages:
        user_content = messages[-1].get("content", "")
    if "Summarize" in user_content:
        return {"choices": [{"message": {"content": "Summary chunk"}}]}
    payload = {
        "title": "Deck",
        "slides": [
            {"layout": "title", "title": "Deck", "content": "", "order": 0},
            {"layout": "content", "title": "Slide", "content": "- A\n- B", "order": 1},
        ],
    }
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


def test_generate_rejects_large_input_without_chunking():
    generator = SlidesGenerator(llm_call=_stub_llm_call)
    with pytest.raises(SlidesSourceTooLargeError):
        generator.generate_from_text(
            source_text="x" * 50,
            title_hint=None,
            provider="openai",
            model=None,
            api_key=None,
            temperature=None,
            max_tokens=None,
            max_source_tokens=None,
            max_source_chars=10,
            enable_chunking=False,
            chunk_size_tokens=None,
            summary_tokens=None,
        )


def test_generate_parses_json_response():
    generator = SlidesGenerator(llm_call=_stub_llm_call)
    result = generator.generate_from_text(
        source_text="Content",
        title_hint="Hint",
        provider="openai",
        model=None,
        api_key=None,
        temperature=None,
        max_tokens=None,
        max_source_tokens=None,
        max_source_chars=None,
        enable_chunking=False,
        chunk_size_tokens=None,
        summary_tokens=None,
    )
    assert result["title"] == "Deck"
    assert len(result["slides"]) == 2


def test_generate_handles_invalid_json():
    def bad_llm_call(api_provider=None, messages=None, **kwargs):
        return {"choices": [{"message": {"content": "not json"}}]}

    generator = SlidesGenerator(llm_call=bad_llm_call)
    with pytest.raises(SlidesGenerationOutputError):
        generator.generate_from_text(
            source_text="Content",
            title_hint=None,
            provider="openai",
            model=None,
            api_key=None,
            temperature=None,
            max_tokens=None,
            max_source_tokens=None,
            max_source_chars=None,
            enable_chunking=False,
            chunk_size_tokens=None,
            summary_tokens=None,
        )


def test_generate_uses_deterministic_test_mode_payload(monkeypatch):
    monkeypatch.setenv("TLDW_TEST_MODE", "1")

    def failing_llm_call(**kwargs):
        raise AssertionError("LLM call should be bypassed in test mode")

    generator = SlidesGenerator(llm_call=failing_llm_call)
    result = generator.generate_from_text(
        source_text="First key point.\nSecond key point.\nThird key point.",
        title_hint="Test Mode Deck",
        provider="openai",
        model=None,
        api_key=None,
        temperature=None,
        max_tokens=None,
        max_source_tokens=None,
        max_source_chars=None,
        enable_chunking=False,
        chunk_size_tokens=None,
        summary_tokens=None,
    )

    assert result["title"] == "Test Mode Deck"
    assert len(result["slides"]) >= 2
    assert result["slides"][0]["title"] == "Test Mode Deck"
