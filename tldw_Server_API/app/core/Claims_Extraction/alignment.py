from __future__ import annotations

import re
import unicodedata
from collections import Counter, deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from math import ceil

_HYPHEN_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\-]+")
_SPACE_RE = re.compile(r"\s+")
# Unicode-aware "word" matcher (letters/digits across scripts), excluding "_".
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_NON_SPACED_SCRIPT_RE = re.compile(
    r"[\u3400-\u4DBF\u4E00-\u9FFF\u3040-\u30FF\u31F0-\u31FF\uAC00-\uD7AF\u0E00-\u0E7F\u0E80-\u0EFF\u1780-\u17FF\u1000-\u109F]"
)


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
        folded = ch.casefold()
        for folded_char in folded:
            normalized.append(folded_char)
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
    folded = (text or "").casefold()
    folded = _HYPHEN_RE.sub(" ", folded)
    folded = _SPACE_RE.sub(" ", folded)
    return folded.strip()


def _is_word_char(ch: str) -> bool:
    return bool(ch and _WORD_RE.fullmatch(ch))


def _is_non_spaced_script_char(ch: str) -> bool:
    return bool(ch and _NON_SPACED_SCRIPT_RE.match(ch))


@lru_cache(maxsize=4096)
def _script_group(ch: str) -> str:
    if not ch:
        return "unknown"

    if ord(ch) < 128:
        return "latin"

    name = unicodedata.name(ch, "")
    if name.startswith("LATIN"):
        return "latin"
    if name.startswith("CYRILLIC"):
        return "cyrillic"
    if name.startswith("GREEK"):
        return "greek"
    if name.startswith("ARABIC"):
        return "arabic"
    if name.startswith("HEBREW"):
        return "hebrew"
    if name.startswith("DEVANAGARI"):
        return "devanagari"
    return "unknown"


def _extract_tokens_with_offsets(
    text: str,
    *,
    normalize_input: bool,
) -> list[tuple[str, int, int]]:
    tokens: list[tuple[str, int, int]] = []
    working_text = _normalize_for_tokens(text) if normalize_input else str(text or "")
    if not working_text:
        return tokens

    current_chars: list[str] = []
    current_start = 0
    current_script: str | None = None
    current_kind: str | None = None

    def _flush(end_idx: int) -> None:
        nonlocal current_chars, current_start, current_script, current_kind
        if not current_chars:
            return
        token_text = "".join(current_chars)
        token = token_text if normalize_input else _normalize_for_tokens(token_text)
        if token:
            tokens.append((token, current_start, end_idx))
        current_chars = []
        current_script = None
        current_kind = None

    for idx, ch in enumerate(working_text):
        if not _is_word_char(ch):
            _flush(idx)
            continue

        if ch.isdigit():
            if current_chars and current_kind != "number":
                _flush(idx)
            if not current_chars:
                current_start = idx
                current_kind = "number"
            current_chars.append(ch)
            continue

        if _is_non_spaced_script_char(ch):
            _flush(idx)
            token = ch if normalize_input else _normalize_for_tokens(ch)
            if token:
                tokens.append((token, idx, idx + 1))
            continue

        ch_script = _script_group(ch)
        if ch_script == "unknown":
            _flush(idx)
            token = ch if normalize_input else _normalize_for_tokens(ch)
            if token:
                tokens.append((token, idx, idx + 1))
            continue

        if current_chars and (current_kind != "word" or current_script != ch_script):
            _flush(idx)

        if not current_chars:
            current_start = idx
            current_script = ch_script
            current_kind = "word"
        current_chars.append(ch)

    _flush(len(working_text))
    return tokens


def _extract_word_tokens_with_offsets(text: str) -> list[tuple[str, int, int]]:
    return _extract_tokens_with_offsets(text, normalize_input=True)


def _extract_source_tokens_with_offsets(text: str) -> list[tuple[str, int, int]]:
    return _extract_tokens_with_offsets(text, normalize_input=False)


def _normalize_token(token: str) -> str:
    normalized = str(token or "").casefold()
    if len(normalized) > 3 and normalized.endswith("s") and not normalized.endswith("ss"):
        normalized = normalized[:-1]
    return normalized


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
    query_norm = [_normalize_token(tok) for tok in query]
    source_norm = [_normalize_token(tok) for tok, _, _ in source_tokens]
    query_len = len(query)
    max_window = len(source_tokens)
    query_counter = Counter(query_norm)
    clamped_threshold = max(0.0, min(1.0, float(threshold)))
    min_overlap = int(query_len * clamped_threshold)
    min_window = max(1, ceil(query_len * clamped_threshold))
    matcher = SequenceMatcher(None, [], query_norm, autojunk=False)

    best: AlignmentResult | None = None
    for window_size in range(min_window, max_window + 1):
        window_norm = deque(source_norm[0:window_size])
        window_counts = Counter(window_norm)

        for start in range(0, len(source_tokens) - window_size + 1):
            overlap = sum((query_counter & window_counts).values())
            if overlap >= min_overlap:
                matcher.set_seq1(list(window_norm))
                matched_token_count = sum(size for _, _, size in matcher.get_matching_blocks())
                ratio = matched_token_count / max(1, query_len)
                overlap_ratio = overlap / max(1, query_len)
                score = max(ratio, overlap_ratio)
                if best is None or score > best.score:
                    span = (source_tokens[start][1], source_tokens[start + window_size - 1][2])
                    best = AlignmentResult(span=span, method="fuzzy", score=float(score))

            if start + window_size < len(source_tokens):
                old_token = window_norm.popleft()
                window_counts[old_token] -= 1
                if window_counts[old_token] <= 0:
                    del window_counts[old_token]

                new_token = source_norm[start + window_size]
                window_norm.append(new_token)
                window_counts[new_token] += 1

    if best is None:
        return None
    if best.score < clamped_threshold:
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
