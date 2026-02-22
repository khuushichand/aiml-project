import pytest

from tldw_Server_API.app.core.RAG.rag_service.response_writer import (
    build_writer_system_prompt,
    format_context_xml,
    get_writer_depth_policy,
)


pytestmark = pytest.mark.unit


def test_format_context_xml_escapes_content_attributes_and_reindexes():
    xml = format_context_xml(
        [
            {"content": "   "},  # skipped
            {
                "content": '5 < 7 & "quoted"',
                "title": 'A "quote" <tag>',
                "url": 'https://example.com?a=1&b="2"',
            },
        ]
    )

    assert '<result index="1"' in xml
    assert 'index="2"' not in xml
    assert '5 &lt; 7 &amp; "quoted"' in xml
    assert 'title="A &quot;quote&quot; &lt;tag&gt;"' in xml
    assert 'source="https://example.com?a=1&amp;b=&quot;2&quot;"' in xml


def test_format_context_xml_returns_no_results_when_all_content_empty():
    xml = format_context_xml([{"content": ""}, {"content": "   "}])
    assert "<context>" in xml
    assert "(no results)" in xml
    assert "<result " not in xml


def test_quality_writer_prompt_adapts_when_budget_is_too_low():
    policy = get_writer_depth_policy(mode="quality", max_generation_tokens=800)
    prompt = build_writer_system_prompt(mode="quality", max_generation_tokens=800)

    assert policy["degraded_due_to_token_budget"] is True
    assert policy["max_generation_tokens"] == 800
    assert "strict 2000+ word minimum is likely not feasible" in prompt
    assert "Available max generation tokens: 800" in prompt


def test_quality_writer_prompt_keeps_full_depth_when_budget_is_sufficient():
    policy = get_writer_depth_policy(mode="quality", max_generation_tokens=5000)
    prompt = build_writer_system_prompt(mode="quality", max_generation_tokens=5000)

    assert policy["degraded_due_to_token_budget"] is False
    assert policy["max_generation_tokens"] == 5000
    assert "supports the 2000+ word target" in prompt
