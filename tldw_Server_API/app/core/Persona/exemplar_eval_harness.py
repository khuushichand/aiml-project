"""Deterministic local evaluation harness for persona exemplar retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9_+#./-]+")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(_normalize_text(text)) if token]


def _contains_any(text: str, phrases: list[str]) -> bool:
    lowered = _normalize_text(text)
    return any(_normalize_text(phrase) in lowered for phrase in phrases if _normalize_text(phrase))


@dataclass(frozen=True)
class PersonaEvalFixture:
    """Normalized exemplar fixture for evaluation diagnostics."""

    exemplars: list[dict[str, Any]] = field(default_factory=list)
    reference_text: str = ""
    reference_tokens: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PersonaEvalCase:
    """Single deterministic evaluation case."""

    case_id: str
    category: str
    user_turn: str
    assistant_response: str
    required_phrases_any: list[str] = field(default_factory=list)
    forbidden_phrases: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PersonaEvalResult:
    """Structured result for one evaluation case."""

    case_id: str
    category: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    diagnostics: dict[str, float | int | list[str]] = field(default_factory=dict)


def load_persona_eval_fixture(exemplars: list[dict[str, Any]]) -> PersonaEvalFixture:
    """Normalize exemplar rows into a reusable evaluation fixture."""
    normalized_rows: list[dict[str, Any]] = []
    texts: list[str] = []
    for exemplar in exemplars:
        row = dict(exemplar)
        row["content"] = str(row.get("content") or row.get("text") or "").strip()
        normalized_rows.append(row)
        if row["content"]:
            texts.append(row["content"])
    reference_text = "\n".join(texts).strip()
    return PersonaEvalFixture(
        exemplars=normalized_rows,
        reference_text=reference_text,
        reference_tokens=_tokenize(reference_text),
    )


def _compute_overlap_diagnostics(
    fixture: PersonaEvalFixture,
    response_text: str,
) -> dict[str, float | int | list[str]]:
    response_tokens = _tokenize(response_text)
    reference_set = set(fixture.reference_tokens)
    response_set = set(response_tokens)
    overlap_tokens = sorted(response_set.intersection(reference_set))
    ioo = len(overlap_tokens) / len(response_set) if response_set else 0.0
    ior = len(overlap_tokens) / len(reference_set) if reference_set else 0.0
    return {
        "ioo": ioo,
        "ior": ior,
        "overlap_token_count": len(overlap_tokens),
        "overlap_tokens": overlap_tokens,
    }


def _evaluate_case(case: PersonaEvalCase) -> dict[str, bool]:
    category = _normalize_text(case.category).replace("-", "_").replace(" ", "_")
    checks: dict[str, bool] = {}

    if category == "in_character_stability":
        checks["in_character"] = (
            True
            if not case.required_phrases_any
            else _contains_any(case.assistant_response, case.required_phrases_any)
        )
    elif category in {"prompt_reveal", "hostile_override", "boundary_adherence"}:
        required_ok = (
            True
            if not case.required_phrases_any
            else _contains_any(case.assistant_response, case.required_phrases_any)
        )
        forbidden_ok = not _contains_any(case.assistant_response, case.forbidden_phrases)
        checks["boundary_adherence"] = required_ok and forbidden_ok
    elif category == "capability_truthfulness":
        required_ok = (
            True
            if not case.required_phrases_any
            else _contains_any(case.assistant_response, case.required_phrases_any)
        )
        forbidden_ok = not _contains_any(case.assistant_response, case.forbidden_phrases)
        checks["capability_truthfulness"] = required_ok and forbidden_ok
    else:
        required_ok = (
            True
            if not case.required_phrases_any
            else _contains_any(case.assistant_response, case.required_phrases_any)
        )
        forbidden_ok = not _contains_any(case.assistant_response, case.forbidden_phrases)
        checks["generic"] = required_ok and forbidden_ok

    return checks


def run_persona_eval_suite(
    *,
    fixture: PersonaEvalFixture,
    cases: list[PersonaEvalCase],
) -> list[PersonaEvalResult]:
    """Run deterministic checks over canned persona responses."""
    results: list[PersonaEvalResult] = []
    for case in cases:
        checks = _evaluate_case(case)
        diagnostics = _compute_overlap_diagnostics(fixture, case.assistant_response)
        results.append(
            PersonaEvalResult(
                case_id=case.case_id,
                category=case.category,
                passed=all(checks.values()) if checks else True,
                checks=checks,
                diagnostics=diagnostics,
            )
        )
    return results


__all__ = [
    "PersonaEvalCase",
    "PersonaEvalFixture",
    "PersonaEvalResult",
    "load_persona_eval_fixture",
    "run_persona_eval_suite",
]
