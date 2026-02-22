from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher

_HYPHEN_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\-]+")
_SPACE_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class AlignmentResult:
    span: tuple[int, int]
    method: str
    score: float


def _normalize_text_with_map(text: str) -> tuple[str, list[int]]:
    if not text:
        return "", []
    normalized: list[str] = []
    index_map: list[int] = []
    prev_space = False
    for idx, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            normalized.append(" ")
            index_map.append(idx)
            prev_space = True
            continue
        prev_space = False
        normalized.append(ch.lower())
        index_map.append(idx)
    start = 0
    end = len(normalized)
    while start < end and normalized[start] == " ":
        start += 1
    while end > start and normalized[end - 1] == " ":
        end -= 1
    return "".join(normalized[start:end]), index_map[start:end]


def _map_span(index_map: list[int], start: int, end: int) -> tuple[int, int] | None:
    if not index_map or start < 0 or end <= start:
        return None
    if start >= len(index_map) or end - 1 >= len(index_map):
        return None
    return index_map[start], index_map[end - 1] + 1


def _normalize_for_tokens(text: str) -> str:
    lowered = (text or "").lower()
    lowered = _HYPHEN_RE.sub(" ", lowered)
    lowered = _SPACE_RE.sub(" ", lowered)
    return lowered.strip()


def _extract_word_tokens_with_offsets(text: str) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    if not text:
        return tokens
    for match in _WORD_RE.finditer(_normalize_for_tokens(text)):
        token = match.group(0).strip()
        if token:
            tokens.append((token, match.start(), match.end()))
    return tokens


def _extract_source_tokens_with_offsets(text: str) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    if not text:
        return tokens
    for match in _WORD_RE.finditer(text):
        token = _normalize_for_tokens(match.group(0))
        if token:
            tokens.append((token, match.start(), match.end()))
    return tokens


def _exact_or_normalized_span(source_text: str, claim_text: str) -> AlignmentResult | None:
    claim = (claim_text or "").strip()
    if not claim:
        return None
    idx = source_text.find(claim)
    if idx >= 0:
        return AlignmentResult(span=(idx, idx + len(claim)), method="exact", score=1.0)

    normalized_source, source_map = _normalize_text_with_map(source_text)
    normalized_claim, _ = _normalize_text_with_map(claim)
    if not normalized_source or not normalized_claim:
        return None
    nidx = normalized_source.find(normalized_claim)
    if nidx < 0:
        return None
    mapped = _map_span(source_map, nidx, nidx + len(normalized_claim))
    if mapped is None:
        return None
    return AlignmentResult(span=mapped, method="normalized_exact", score=0.98)


def _fuzzy_token_span(source_text: str, claim_text: str, threshold: float) -> AlignmentResult | None:
    claim_tokens = _extract_word_tokens_with_offsets(claim_text)
    source_tokens = _extract_source_tokens_with_offsets(source_text)
    if not claim_tokens or not source_tokens:
        return None

    query = [tok for tok, _, _ in claim_tokens]
    query_len = len(query)
    min_window = max(1, query_len - max(2, query_len // 3))
    max_window = min(len(source_tokens), query_len + max(2, query_len // 3))
    query_text = " ".join(query)
    query_counter = Counter(query)

    best: AlignmentResult | None = None
    for window_size in range(min_window, max_window + 1):
        for start in range(0, len(source_tokens) - window_size + 1):
            segment = source_tokens[start : start + window_size]
            seg_tokens = [tok for tok, _, _ in segment]
            if not seg_tokens:
                continue
            seg_text = " ".join(seg_tokens)
            ratio = SequenceMatcher(None, query_text, seg_text).ratio()
            overlap_counter = Counter(seg_tokens)
            overlap = sum((query_counter & overlap_counter).values())
            overlap_ratio = overlap / max(1, query_len)
            score = max(ratio, overlap_ratio)
            if best is None or score > best.score:
                span = (segment[0][1], segment[-1][2])
                best = AlignmentResult(span=span, method="fuzzy", score=float(score))

    if best is None:
        return None
    if best.score < max(0.0, min(1.0, float(threshold))):
        return None
    return best


def align_claim_span(
    source_text: str,
    claim_text: str,
    *,
    mode: str = "fuzzy",
    threshold: float = 0.75,
) -> tuple[int, int] | None:
    """Backward-compatible span-only alignment helper."""
    result = align_claim(
        source_text,
        claim_text,
        mode=mode,
        threshold=threshold,
    )
    return result.span if result is not None else None


def align_claim(
    source_text: str,
    claim_text: str,
    *,
    mode: str = "fuzzy",
    threshold: float = 0.75,
) -> AlignmentResult | None:
    """Align claim text to source text using exact/normalized/fuzzy token matching."""
    strategy = str(mode or "fuzzy").strip().lower()
    if strategy in {"off", "none", "disabled"}:
        return None
    if not isinstance(source_text, str) or not source_text:
        return None
    if not isinstance(claim_text, str) or not claim_text.strip():
        return None

    exact = _exact_or_normalized_span(source_text, claim_text)
    if exact is not None:
        return exact
    if strategy == "exact":
        return None

    fuzzy = _fuzzy_token_span(source_text, claim_text, threshold)
    return fuzzy


__all__ = ["AlignmentResult", "align_claim", "align_claim_span"]
