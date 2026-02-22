import pytest

from tldw_Server_API.app.core.Claims_Extraction.alignment import align_claim_span


@pytest.mark.unit
def test_align_claim_span_exact_mode():
    text = "Alpha Beta Gamma."
    span = align_claim_span(text, "Beta", mode="exact")
    assert span is not None
    assert text[span[0] : span[1]] == "Beta"


@pytest.mark.unit
def test_align_claim_span_whitespace_normalized():
    text = "Alpha  Beta\nGamma"
    span = align_claim_span(text, "Alpha Beta Gamma", mode="exact")
    assert span is not None
    assert "Alpha" in text[span[0] : span[1]]


@pytest.mark.unit
def test_align_claim_span_fuzzy_handles_hyphen_variants():
    text = "state-of-the-art systems are common."
    span = align_claim_span(text, "state of the art systems", mode="fuzzy", threshold=0.6)
    assert span is not None
    assert "state-of-the-art" in text[span[0] : span[1]]


@pytest.mark.unit
def test_align_claim_span_unmatched_returns_none():
    text = "Completely unrelated sentence."
    assert align_claim_span(text, "Different claim", mode="exact") is None


@pytest.mark.unit
def test_align_claim_span_off_mode_disables_alignment():
    text = "Alpha Beta"
    assert align_claim_span(text, "Alpha", mode="off") is None
