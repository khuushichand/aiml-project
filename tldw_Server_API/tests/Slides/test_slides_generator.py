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


def test_timeline_style_generates_visual_block_and_text_fallback():
    captured = {}

    def timeline_llm_call(api_provider=None, messages=None, **kwargs):
        user_content = ""
        if messages:
            captured["system_prompt"] = messages[0].get("content", "")
            user_content = messages[-1].get("content", "")
        if "Summarize" in user_content:
            return {"choices": [{"message": {"content": "Summary chunk"}}]}
        payload = {
            "title": "History Deck",
            "slides": [
                {"layout": "title", "title": "History Deck", "content": "", "order": 0},
                {
                    "layout": "content",
                    "title": "Key Events",
                    "content": "",
                    "order": 1,
                    "metadata": {
                        "visual_blocks": [
                            {
                                "type": "timeline",
                                "items": [
                                    {
                                        "label": "1776",
                                        "title": "Declaration",
                                        "description": "American independence declared",
                                    },
                                    {
                                        "label": "1947",
                                        "title": "Independence",
                                        "description": "India becomes independent",
                                    },
                                ],
                            }
                        ]
                    },
                },
            ],
        }
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}

    generator = SlidesGenerator(llm_call=timeline_llm_call)
    result = generator.generate_from_text(
        source_text="1776, 1947",
        title_hint="History",
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
        visual_style_snapshot={
            "id": "timeline",
            "name": "Timeline",
            "generation_rules": {"chronology_bias": "high"},
            "artifact_preferences": ["timeline"],
        },
    )

    slide = result["slides"][1]
    assert "timeline" in captured["system_prompt"].lower() or "chronology" in captured["system_prompt"].lower()
    assert slide["metadata"]["visual_blocks"][0]["type"] == "timeline"
    assert "1776" in slide["content"]
    assert "1947" in slide["content"]
