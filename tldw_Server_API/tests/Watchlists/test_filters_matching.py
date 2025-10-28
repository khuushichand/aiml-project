import pytest

pytestmark = pytest.mark.unit

from tldw_Server_API.app.core.Watchlists.filters import normalize_filters, evaluate_filters


def test_keyword_any_and_all():
    payload = {
        "filters": [
            {"type": "keyword", "action": "exclude", "value": {"keywords": ["ai", "ml"], "match": "any"}, "priority": 5},
            {"type": "keyword", "action": "flag", "value": {"keywords": ["research", "paper"], "match": "all"}, "priority": 1},
        ]
    }
    flt = normalize_filters(payload)

    decision, meta = evaluate_filters(flt, {"title": "New AI breakthroughs", "summary": "..."})
    assert decision == "exclude"
    assert meta and "key" in meta

    decision, _ = evaluate_filters(flt, {"title": "Interesting research", "summary": "..."})
    # 'all' requires both keywords; should not match when only one present
    assert decision is None

    decision, _ = evaluate_filters(flt, {"title": "Great research paper", "summary": "..."})
    assert decision == "flag"


def test_regex_flags_and_field():
    payload = {
        "filters": [
            {"type": "regex", "action": "exclude", "value": {"pattern": "(?i)breaking", "field": "title"}},
            {"type": "regex", "action": "flag", "value": {"pattern": "^Author:.*Doe$", "flags": "i", "field": "author"}},
        ]
    }
    flt = normalize_filters(payload)

    decision, _ = evaluate_filters(flt, {"title": "Breaking News", "author": "Jane"})
    assert decision == "exclude"

    decision, _ = evaluate_filters(flt, {"title": "Regular", "author": "author: John Doe"})
    assert decision == "flag"


def test_date_range_max_age_days():
    from datetime import datetime, timezone, timedelta

    recent_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    old_iso = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    payload = {
        "filters": [
            {"type": "date_range", "action": "exclude", "value": {"max_age_days": 7}},
        ]
    }
    flt = normalize_filters(payload)

    decision, _ = evaluate_filters(flt, {"published_at": old_iso})
    assert decision != "exclude"  # too old should not match include-only filter

    decision, _ = evaluate_filters(flt, {"published_at": recent_iso})
    assert decision == "exclude"
