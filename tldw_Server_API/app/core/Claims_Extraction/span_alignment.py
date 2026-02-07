from __future__ import annotations

_WINDOW_SIZES = (160, 128, 96, 64, 48, 32)


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


def _map_normalized_span(index_map: list[int], start: int, end: int) -> tuple[int, int] | None:
    if not index_map or start < 0 or end <= start:
        return None
    if start >= len(index_map) or end - 1 >= len(index_map):
        return None
    return index_map[start], index_map[end - 1] + 1


def _window_candidates(text: str, size: int) -> list[str]:
    if size <= 0 or len(text) < size:
        return []
    candidates = [text[:size]]
    mid_start = max(0, (len(text) - size) // 2)
    candidates.append(text[mid_start: mid_start + size])
    candidates.append(text[-size:])
    seen: set[str] = set()
    unique: list[str] = []
    for cand in candidates:
        if cand and cand not in seen:
            seen.add(cand)
            unique.append(cand)
    return unique


def _find_window_span(
    normalized_doc: str,
    index_map: list[int],
    normalized_query: str,
) -> tuple[int, int] | None:
    fallback = None
    for size in _WINDOW_SIZES:
        if len(normalized_query) < size:
            continue
        for window in _window_candidates(normalized_query, size):
            idx = normalized_doc.find(window)
            if idx < 0:
                continue
            span = _map_normalized_span(index_map, idx, idx + len(window))
            if span is None:
                continue
            if normalized_doc.find(window, idx + 1) == -1:
                return span
            if fallback is None:
                fallback = span
        if fallback is not None:
            return fallback
    return None


def find_text_span(
    doc_text: str,
    query_text: str,
    *,
    fallback_text: str | None = None,
) -> tuple[int, int] | None:
    if not isinstance(doc_text, str) or not doc_text:
        return None
    query = (query_text or "").strip()
    fallback = (fallback_text or "").strip()

    if query:
        idx = doc_text.find(query)
        if idx >= 0:
            return idx, idx + len(query)
    if fallback:
        idx = doc_text.find(fallback)
        if idx >= 0:
            return idx, idx + len(fallback)

    normalized_doc, index_map = _normalize_text_with_map(doc_text)
    if not normalized_doc:
        return None

    normalized_query = ""
    normalized_fallback = ""
    if query:
        normalized_query, _ = _normalize_text_with_map(query)
        if normalized_query:
            idx = normalized_doc.find(normalized_query)
            if idx >= 0:
                return _map_normalized_span(index_map, idx, idx + len(normalized_query))
    if fallback:
        normalized_fallback, _ = _normalize_text_with_map(fallback)
        if normalized_fallback:
            idx = normalized_doc.find(normalized_fallback)
            if idx >= 0:
                return _map_normalized_span(index_map, idx, idx + len(normalized_fallback))

    candidate = normalized_fallback or normalized_query
    if candidate:
        return _find_window_span(normalized_doc, index_map, candidate)

    return None


__all__ = ["find_text_span"]
