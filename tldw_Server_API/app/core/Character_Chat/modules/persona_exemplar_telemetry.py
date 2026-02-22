"""Telemetry helpers for persona exemplar usage diagnostics."""

from __future__ import annotations

import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-zA-Z0-9']+")
_WHITESPACE_RE = re.compile(r"\s+")
_REFUSAL_MARKERS = (
    "i can't",
    "i cannot",
    "i can’t",
    "i won't",
    "i will not",
    "i'm unable",
    "i am unable",
    "cannot assist",
    "can't help",
)
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i", "in", "is", "it",
    "of", "on", "or", "that", "the", "this", "to", "was", "we", "with", "you", "your",
}


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    return [token for token in _TOKEN_RE.findall(lowered) if token and token not in _STOPWORDS]


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


def _strip_catchphrases(text: str, approved_catchphrases: list[str]) -> str:
    normalized = str(text or "")
    for phrase in approved_catchphrases:
        phrase_text = str(phrase or "").strip()
        if not phrase_text:
            continue
        normalized = re.sub(re.escape(phrase_text), " ", normalized, flags=re.IGNORECASE)
    return normalized


def _lcs_length(lhs: list[str], rhs: list[str], cap: int = 512) -> int:
    """Compute token-level LCS length with bounded memory and runtime."""
    if not lhs or not rhs:
        return 0
    lhs = lhs[:cap]
    rhs = rhs[:cap]
    prev = [0] * (len(rhs) + 1)
    for left_token in lhs:
        curr = [0]
        for idx, right_token in enumerate(rhs, start=1):
            if left_token == right_token:
                curr.append(prev[idx - 1] + 1)
            else:
                curr.append(max(curr[-1], prev[idx]))
        prev = curr
    return prev[-1]


def compute_persona_exemplar_telemetry(
    output_text: str,
    selected_exemplars: list[dict[str, Any]],
    *,
    approved_catchphrases: list[str] | None = None,
) -> dict[str, Any]:
    """Compute IOO/IOR/LCS diagnostics for persona exemplar selection."""
    catchphrases = approved_catchphrases or []
    normalized_output = _strip_catchphrases(output_text or "", catchphrases)
    output_tokens = _tokenize(normalized_output)

    exemplar_texts: list[str] = []
    exemplar_tokens_flat: list[str] = []
    for exemplar in selected_exemplars or []:
        text = str(exemplar.get("text") or "").strip()
        if not text:
            continue
        exemplar_texts.append(text)
        exemplar_tokens_flat.extend(_tokenize(_strip_catchphrases(text, catchphrases)))

    output_token_count = len(output_tokens)
    output_token_set = set(output_tokens)
    exemplar_token_set = set(exemplar_tokens_flat)

    overlap_output = len([token for token in output_tokens if token in exemplar_token_set])
    overlap_retrieved = len(exemplar_token_set.intersection(output_token_set))

    ioo = (overlap_output / output_token_count) if output_token_count else 0.0
    ior = (overlap_retrieved / len(exemplar_token_set)) if exemplar_token_set else 0.0

    output_lcs_tokens = _tokenize(_normalize_text(normalized_output))
    lcs_scores: list[float] = []
    for exemplar_text in exemplar_texts:
        exemplar_lcs_tokens = _tokenize(_normalize_text(_strip_catchphrases(exemplar_text, catchphrases)))
        if not output_lcs_tokens or not exemplar_lcs_tokens:
            continue
        lcs_len = _lcs_length(output_lcs_tokens, exemplar_lcs_tokens)
        denom = max(len(output_lcs_tokens), len(exemplar_lcs_tokens), 1)
        lcs_scores.append(lcs_len / denom)
    lcs = max(lcs_scores) if lcs_scores else 0.0

    safety_flags: list[str] = []
    output_lower = _normalize_text(output_text or "")
    if output_token_count > 150 and ioo > 0.4:
        safety_flags.append("ioo_high")
    if any(marker in output_lower for marker in _REFUSAL_MARKERS):
        safety_flags.append("refusal_detected")

    return {
        "ioo": round(max(0.0, min(1.0, ioo)), 6),
        "ior": round(max(0.0, min(1.0, ior)), 6),
        "lcs": round(max(0.0, min(1.0, lcs)), 6),
        "safety_flags": safety_flags,
    }


__all__ = ["compute_persona_exemplar_telemetry"]
