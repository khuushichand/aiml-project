from __future__ import annotations

import time

import pytest

from tldw_Server_API.app.core.Watchlists.filters import evaluate_filters, normalize_filters


@pytest.mark.performance
@pytest.mark.unit
def test_filter_evaluation_large_rule_set_within_budget():
    raw_filters: list[dict[str, object]] = []
    for idx in range(120):
        raw_filters.append(
            {
                "type": "keyword",
                "action": "exclude" if idx % 2 else "include",
                "value": {"terms": [f"term-{idx}", f"signal-{idx}"]},
                "priority": idx,
                "is_active": True,
            }
        )
    normalized = normalize_filters({"filters": raw_filters})
    candidate = {
        "title": "signal-3 watchlists performance candidate",
        "summary": "term-18 appears in this summary",
        "content": "This body includes term-22 and more text.",
        "author": "system",
        "published_at": None,
    }

    start = time.perf_counter()
    for _ in range(600):
        action, meta = evaluate_filters(normalized, candidate)
        assert action in {"include", "exclude", "flag", None}
        assert meta is None or isinstance(meta, dict)
    elapsed = time.perf_counter() - start

    # Guardrail for obvious regressions without being overly strict across environments.
    assert elapsed < 8.0
