"""Claims monitoring helpers."""

from __future__ import annotations


def record_postcheck_metrics(total_claims: int, unsupported_claims: int) -> None:
    """Record post-generation verification counters for claims."""
    if total_claims <= 0 and unsupported_claims <= 0:
        return
    try:
        from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter
    except Exception:
        return
    try:
        if total_claims > 0:
            increment_counter("rag_total_claims_checked_total", total_claims)
        if unsupported_claims > 0:
            increment_counter("rag_unsupported_claims_total", unsupported_claims)
    except Exception:
        pass
