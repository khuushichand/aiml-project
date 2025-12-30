import pytest

from tldw_Server_API.app.core.Claims_Extraction.span_alignment import find_text_span


def _normalize(text: str) -> str:
    parts = []
    prev_space = False
    for ch in text:
        if ch.isspace():
            if prev_space:
                continue
            parts.append(" ")
            prev_space = True
            continue
        prev_space = False
        parts.append(ch.lower())
    return "".join(parts).strip()


@pytest.mark.unit
def test_find_text_span_handles_whitespace_variants():
    doc_text = "Alpha  Beta\nGamma"
    query_text = "Alpha Beta Gamma"
    span = find_text_span(doc_text, query_text)
    assert span is not None
    start, end = span
    assert _normalize(doc_text[start:end]) == _normalize(query_text)


@pytest.mark.unit
def test_find_text_span_uses_fallback_window():
    doc_text = "Intro: " + ("lorem " * 40) + "END."
    fallback = "lorem " * 20
    span = find_text_span(doc_text, "missing text", fallback_text=fallback)
    assert span is not None
    start, end = span
    assert "lorem" in doc_text[start:end].lower()
