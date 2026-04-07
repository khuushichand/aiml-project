"""Minimal deterministic topic normalization and ranking helpers."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Iterable

from .types import NormalizedTopicLabel, RankedTopic, TopicCandidate


_WHITESPACE_RE = re.compile(r"\s+")
_SEPARATOR_RE = re.compile(r"[-_/]+")
_GROUPING_SYNONYMS = {
    "kidney": "renal",
    "kidneys": "renal",
}
_EVIDENCE_PRIORITY = {
    "grounded": 0,
    "weakly_grounded": 1,
    "derived": 2,
}


def _clean_label(label: object) -> str | None:
    text = str(label or "").strip().lower()
    if not text:
        return None
    text = _SEPARATOR_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip() or None


def _fingerprint(label: str) -> str:
    tokens = [_GROUPING_SYNONYMS.get(token, token) for token in label.split()]
    return " ".join(tokens)


def _canonical_preference(label: str) -> tuple[int, int, str]:
    lacks_renal = "renal" not in label.split()
    return (lacks_renal, len(label), label)


def normalize_topic_labels(labels: Iterable[object]) -> list[NormalizedTopicLabel]:
    grouped: "OrderedDict[str, list[tuple[str, str]]]" = OrderedDict()
    for raw_label in labels:
        cleaned = _clean_label(raw_label)
        if cleaned is None:
            continue
        fingerprint = _fingerprint(cleaned)
        grouped.setdefault(fingerprint, []).append((cleaned, str(raw_label)))

    normalized: list[NormalizedTopicLabel] = []
    for entries in grouped.values():
        canonical = min((cleaned for cleaned, _ in entries), key=_canonical_preference)
        normalized.append(
            NormalizedTopicLabel(
                canonical_label=canonical,
                raw_labels=[raw for _, raw in entries],
            )
        )
    return normalized


def resolve_topic_candidates(
    *,
    source_labels: Iterable[object],
    tag_labels: Iterable[object],
    derived_labels: Iterable[object],
) -> list[TopicCandidate]:
    combined: dict[str, TopicCandidate] = {}

    for evidence_class, labels in (
        ("grounded", source_labels),
        ("weakly_grounded", tag_labels),
        ("derived", derived_labels),
    ):
        for normalized in normalize_topic_labels(labels):
            existing = combined.get(normalized.canonical_label)
            if existing is None:
                combined[normalized.canonical_label] = TopicCandidate(
                    canonical_label=normalized.canonical_label,
                    raw_labels=list(normalized.raw_labels),
                    evidence_class=evidence_class,
                )
                continue

            existing.raw_labels.extend(
                raw for raw in normalized.raw_labels if raw not in existing.raw_labels
            )
            if _EVIDENCE_PRIORITY[evidence_class] < _EVIDENCE_PRIORITY[existing.evidence_class]:
                existing.evidence_class = evidence_class

    return sorted(
        combined.values(),
        key=lambda candidate: (
            _EVIDENCE_PRIORITY[candidate.evidence_class],
            candidate.canonical_label,
        ),
    )


def _canonical_set(labels: Iterable[object]) -> set[str]:
    return {item.canonical_label for item in normalize_topic_labels(labels)}


def rank_suggestion_topics(
    candidates: Iterable[TopicCandidate],
    *,
    weakness_labels: Iterable[object],
    adjacent_labels: Iterable[object],
    exploratory_labels: Iterable[object],
) -> list[RankedTopic]:
    weakness = _canonical_set(weakness_labels)
    adjacent = _canonical_set(adjacent_labels)
    exploratory = _canonical_set(exploratory_labels)

    ranked: list[tuple[tuple[int, int, str], RankedTopic]] = []
    for candidate in candidates:
        canonical = candidate.canonical_label
        if canonical in weakness:
            rank_reason = "weakness"
            source_aware = candidate.evidence_class != "derived"
            priority = 0
        elif canonical in exploratory:
            rank_reason = "exploratory"
            source_aware = False
            priority = 2
        elif canonical in adjacent and candidate.evidence_class != "derived":
            rank_reason = "adjacent"
            source_aware = True
            priority = 1
        else:
            rank_reason = "candidate"
            source_aware = False
            priority = 3

        ranked.append(
            (
                (priority, _EVIDENCE_PRIORITY[candidate.evidence_class], canonical),
                RankedTopic(
                    canonical_label=canonical,
                    raw_labels=list(candidate.raw_labels),
                    evidence_class=candidate.evidence_class,
                    rank_reason=rank_reason,
                    adjacency_is_source_aware=source_aware,
                ),
            )
        )

    ranked.sort(key=lambda item: item[0])
    return [topic for _, topic in ranked]
