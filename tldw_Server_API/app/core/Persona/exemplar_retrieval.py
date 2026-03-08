"""Deterministic retrieval for persona-owned exemplars."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


_BOUNDARY_KINDS = {"boundary"}
_STYLE_KINDS = {"style", "scenario_demo"}
_AUXILIARY_KINDS = {"catchphrase", "tool_behavior"}
_ALLOWED_KINDS = _BOUNDARY_KINDS | _STYLE_KINDS | _AUXILIARY_KINDS
_CAPS_BY_BUCKET = {
    "boundary": 1,
    "style": 2,
    "auxiliary": 1,
}


@dataclass(frozen=True)
class PersonaExemplarSelectionResult:
    """Selected and rejected exemplars for a single retrieval turn."""

    selected: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)


def _normalize_text(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    return text or None


def _normalize_tag_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        source = value
    else:
        source = [value]
    normalized: list[str] = []
    seen: set[str] = set()
    for item in source:
        text = _normalize_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _bucket_for_kind(kind: str) -> str | None:
    if kind in _BOUNDARY_KINDS:
        return "boundary"
    if kind in _STYLE_KINDS:
        return "style"
    if kind in _AUXILIARY_KINDS:
        return "auxiliary"
    return None


def _rejected_entry(candidate: dict[str, Any], reason: str) -> dict[str, Any]:
    item = dict(candidate)
    item["reason"] = reason
    return item


def select_persona_exemplars(
    *,
    persona_id: str,
    exemplars: list[dict[str, Any]],
    requested_scenario_tags: list[str] | None = None,
    requested_tone: str | None = None,
) -> PersonaExemplarSelectionResult:
    """Select a bounded deterministic set of persona exemplars for a turn."""
    requested_persona_id = str(persona_id or "").strip()
    requested_tags = set(_normalize_tag_list(requested_scenario_tags))
    normalized_tone = _normalize_text(requested_tone)

    ranked_candidates: list[tuple[tuple[int, int, int, str], dict[str, Any], str]] = []
    rejected: list[dict[str, Any]] = []

    for raw_candidate in exemplars:
        candidate = dict(raw_candidate)
        candidate_persona_id = str(candidate.get("persona_id") or "").strip()
        if candidate_persona_id != requested_persona_id:
            rejected.append(_rejected_entry(candidate, "persona_mismatch"))
            continue
        if bool(candidate.get("deleted", False)):
            rejected.append(_rejected_entry(candidate, "deleted"))
            continue
        if not bool(candidate.get("enabled", True)):
            rejected.append(_rejected_entry(candidate, "disabled"))
            continue

        kind = _normalize_text(candidate.get("kind")) or "style"
        bucket = _bucket_for_kind(kind)
        if bucket is None:
            rejected.append(_rejected_entry(candidate, "invalid_kind"))
            continue

        scenario_tags = _normalize_tag_list(candidate.get("scenario_tags"))
        tone = _normalize_text(candidate.get("tone"))
        try:
            priority = int(candidate.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0

        scenario_match_score = len(requested_tags.intersection(scenario_tags)) if requested_tags else 0
        tone_match_score = 1 if normalized_tone and tone == normalized_tone else 0

        candidate["kind"] = kind
        candidate["tone"] = tone
        candidate["scenario_tags"] = scenario_tags
        candidate["selection_bucket"] = bucket
        ranked_candidates.append(
            (
                (-scenario_match_score, -tone_match_score, -priority, str(candidate.get("id") or "")),
                candidate,
                bucket,
            )
        )

    ranked_candidates.sort(key=lambda item: item[0])

    selected: list[dict[str, Any]] = []
    counts_by_bucket = {bucket: 0 for bucket in _CAPS_BY_BUCKET}

    for _, candidate, bucket in ranked_candidates:
        cap = _CAPS_BY_BUCKET[bucket]
        if counts_by_bucket[bucket] >= cap:
            reason = "boundary_cap" if bucket == "boundary" else "kind_cap"
            rejected.append(_rejected_entry(candidate, reason))
            continue
        counts_by_bucket[bucket] += 1
        selected.append(candidate)

    return PersonaExemplarSelectionResult(selected=selected, rejected=rejected)
