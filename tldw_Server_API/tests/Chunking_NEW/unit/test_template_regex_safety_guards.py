import pytest

from tldw_Server_API.app.core.Chunking.templates import TemplateProcessor, ChunkingTemplate, TemplateStage


def test_remove_headers_unsafe_pattern_is_skipped():
    # pattern with nested quantifiers likely flagged by safety checker
    unsafe = r"(a+)+"
    text = "header\n\ncontent body"
    tpl = ChunkingTemplate(
        name="t",
        base_method="words",
        stages=[
            TemplateStage("preprocess", [{"operation": "remove_headers", "config": {"patterns": [unsafe]}}]),
            TemplateStage("chunk", [{"method": "words", "config": {"max_size": 5, "overlap": 0}}])
        ],
    )
    proc = TemplateProcessor()
    out = proc.process_template(text, tpl)
    # Text should still be chunked; header not removed by unsafe pattern
    assert isinstance(out, list)
    assert any(isinstance(c, dict) and 'text' in c for c in out)


def test_extract_sections_unsafe_pattern_falls_back():
    # Disallow grouping | wildcard etc. The processor should fall back to default pattern
    unsafe = r"(.*)"
    text = "# Title\n\nSome content.\n# Section A\nMore."
    tpl = ChunkingTemplate(
        name="t2",
        base_method="words",
        stages=[
            TemplateStage("preprocess", [{"operation": "extract_sections", "config": {"pattern": unsafe}}]),
            TemplateStage("chunk", [{"method": "words", "config": {"max_size": 5, "overlap": 0}}])
        ],
    )
    proc = TemplateProcessor()
    out = proc.process_template(text, tpl)
    # Should complete without error and produce chunks
    assert isinstance(out, list)
    # No assertion about sections content; this test ensures guardrails don't break pipeline

