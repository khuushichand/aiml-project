from __future__ import annotations

from tldw_Server_API.app.core.Claims_Extraction.alignment import align_claim_span


def find_text_span(
    doc_text: str,
    query_text: str,
    *,
    fallback_text: str | None = None,
) -> tuple[int, int] | None:
    """Backward-compatible wrapper around the unified claim aligner."""
    if not isinstance(doc_text, str) or not doc_text:
        return None
    query = (query_text or "").strip()
    fallback = (fallback_text or "").strip()

    for candidate in (query, fallback):
        if not candidate:
            continue
        span = align_claim_span(doc_text, candidate, mode="exact")
        if span is not None:
            return span
    for candidate in (query, fallback):
        if not candidate:
            continue
        span = align_claim_span(doc_text, candidate, mode="fuzzy", threshold=0.6)
        if span is not None:
            return span

    return None


__all__ = ["find_text_span"]
