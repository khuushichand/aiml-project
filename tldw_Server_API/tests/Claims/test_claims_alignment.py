import pytest

from tldw_Server_API.app.core.Claims_Extraction.alignment import align_claim, align_claim_span


@pytest.mark.unit
def test_align_claim_span_exact_mode():
    text = "Alpha Beta Gamma."
    result = align_claim(text, "Beta", mode="exact")
    assert result is not None
    assert result.method == "exact"
    assert result.score == pytest.approx(1.0)
    assert text[result.span[0] : result.span[1]] == "Beta"

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


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "claim"),
    [
        ("Привет-мир это тест.", "Привет мир это тест"),
        ("Γειά-σου κόσμε", "Γειά σου κόσμε"),
        ("東京-大学は有名です", "東京 大学は有名です"),
    ],
)
def test_align_claim_span_fuzzy_handles_unicode_scripts_with_hyphen_variants(text: str, claim: str):
    span = align_claim_span(text, claim, mode="fuzzy", threshold=0.6)
    assert span is not None
    assert text[span[0] : span[1]]


@pytest.mark.unit
def test_align_claim_span_fuzzy_handles_segmented_non_spaced_script_query():
    text = "東京大学は有名です"
    span = align_claim_span(text, "東京 大学 は 有名 です", mode="fuzzy", threshold=0.6)
    assert span is not None
    assert text[span[0] : span[1]] == text


@pytest.mark.unit
def test_align_claim_exact_mode_uses_unicode_casefold_for_normalized_exact():
    text = "Straße ist lang."
    result = align_claim(text, "STRASSE IST LANG.", mode="exact")
    assert result is not None
    assert result.method == "normalized_exact"
    assert text[result.span[0] : result.span[1]] == "Straße ist lang."


@pytest.mark.unit
def test_align_claim_fuzzy_rejects_character_level_near_matches_without_token_overlap():
    text = "alpha beta gamma"
    span = align_claim_span(text, "alphx bety gammz", mode="fuzzy", threshold=0.75)
    assert span is None


@pytest.mark.unit
def test_align_claim_fuzzy_handles_simple_plural_variants():
    text = "Cats chase mice quickly near houses."
    result = align_claim(
        text,
        "cat chase mouse quickly near house",
        mode="fuzzy",
        threshold=0.75,
    )
    assert result is not None
    assert result.method == "fuzzy"
    assert text[result.span[0] : result.span[1]].startswith("Cats chase mice quickly near houses")


@pytest.mark.unit
def test_align_claim_fuzzy_handles_large_intervening_token_window():
    text = "alpha one two three beta"
    span = align_claim_span(text, "alpha beta", mode="fuzzy", threshold=0.75)
    assert span is not None
    assert text[span[0] : span[1]] == "alpha one two three beta"


@pytest.mark.unit
def test_align_claim_fuzzy_rejects_extreme_intervening_token_window():
    text = "alpha " + " ".join(f"tok{i}" for i in range(120)) + " beta"
    span = align_claim_span(text, "alpha beta", mode="fuzzy", threshold=0.75)
    assert span is None


@pytest.mark.unit
def test_align_claim_fuzzy_prefers_tight_partial_overlap_span():
    text = "Findings consistent with degenerative disc disease at L5-S1."
    span = align_claim_span(text, "mild degenerative disc disease", mode="fuzzy", threshold=0.75)
    assert span is not None
    assert text[span[0] : span[1]] == "degenerative disc disease"


@pytest.mark.unit
def test_align_claim_fuzzy_splits_letter_digit_boundaries():
    text = "Findings consistent with degenerative disc disease at L5-S1."
    span = align_claim_span(
        text,
        "degenerative disc disease at L 5 S 1",
        mode="fuzzy",
        threshold=0.75,
    )
    assert span is not None
    assert text[span[0] : span[1]] == "degenerative disc disease at L5-S1"


@pytest.mark.unit
def test_align_claim_fuzzy_does_not_stem_singular_s_endings():
    text = "news update today"
    span = align_claim_span(text, "new update today", mode="fuzzy", threshold=1.0)
    assert span is None


@pytest.mark.unit
def test_align_claim_fuzzy_handles_mixed_script_token_boundaries():
    text = "AcmeБета launched today."
    span = align_claim_span(text, "Acme Бета launched", mode="fuzzy", threshold=0.75)
    assert span is not None
    assert text[span[0] : span[1]] == "AcmeБета launched"
