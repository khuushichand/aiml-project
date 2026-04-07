from tldw_Server_API.app.core.StudySuggestions.topic_pipeline import (
    normalize_topic_labels,
    rank_suggestion_topics,
    resolve_topic_candidates,
)


def test_source_metadata_outranks_tags_and_tags_outrank_derived_labels():
    candidates = resolve_topic_candidates(
        source_labels=["Kidney function"],
        tag_labels=["renal basics"],
        derived_labels=["how kidneys work"],
    )

    assert [candidate.evidence_class for candidate in candidates] == [  # nosec B101
        "grounded",
        "weakly_grounded",
        "derived",
    ]
    assert candidates[0].canonical_label == "kidney function"  # nosec B101


def test_obvious_near_duplicates_normalize_to_one_canonical_label():
    normalized = normalize_topic_labels([" Renal Basics ", "renal-basics", "Kidney basics"])

    assert normalized[0].canonical_label == "renal basics"  # nosec B101
    assert normalized[0].raw_labels == [" Renal Basics ", "renal-basics", "Kidney basics"]  # nosec B101


def test_weakness_first_ranking_preserves_weakness_before_adjacent_topics():
    candidates = resolve_topic_candidates(
        source_labels=["Kidney function", "Electrolyte balance"],
        tag_labels=[],
        derived_labels=[],
    )

    ranked = rank_suggestion_topics(
        candidates,
        weakness_labels=["Electrolyte balance"],
        adjacent_labels=["Kidney function"],
        exploratory_labels=[],
    )

    assert [topic.canonical_label for topic in ranked[:2]] == [  # nosec B101
        "electrolyte balance",
        "kidney function",
    ]
    assert ranked[0].rank_reason == "weakness"  # nosec B101
    assert ranked[1].rank_reason == "adjacent"  # nosec B101


def test_exploratory_topics_never_claim_source_aware_adjacency():
    candidates = resolve_topic_candidates(
        source_labels=[],
        tag_labels=[],
        derived_labels=["dialysis overview"],
    )

    ranked = rank_suggestion_topics(
        candidates,
        weakness_labels=[],
        adjacent_labels=["dialysis overview"],
        exploratory_labels=["dialysis overview"],
    )

    assert ranked[0].canonical_label == "dialysis overview"  # nosec B101
    assert ranked[0].rank_reason == "exploratory"  # nosec B101
    assert ranked[0].adjacency_is_source_aware is False  # nosec B101
