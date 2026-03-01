from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.Watchlists.filters import evaluate_filters, normalize_filters
from tldw_Server_API.tests.Watchlists.test_perf_plan_metadata import (
    WATCHLISTS_SCALE_GUARDRAILS,
    WATCHLISTS_SCALE_SCENARIOS,
)


@pytest.mark.performance
@pytest.mark.unit
def test_filter_evaluation_large_rule_set_within_budget():
    scenario = WATCHLISTS_SCALE_SCENARIOS["filter_eval_large_rule_set"]
    guardrail_seconds = WATCHLISTS_SCALE_GUARDRAILS["filter_eval_large_rule_set_seconds"]

    raw_filters: list[dict[str, object]] = []
    for idx in range(scenario["rule_count"]):
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
    for _ in range(scenario["evaluation_iterations"]):
        action, meta = evaluate_filters(normalized, candidate)
        assert action in {"include", "exclude", "flag", None}  # nosec B101
        assert meta is None or isinstance(meta, dict)  # nosec B101
    elapsed = time.perf_counter() - start

    # Guardrail for obvious regressions without being overly strict across environments.
    assert elapsed < guardrail_seconds  # nosec B101


@pytest.mark.performance
@pytest.mark.load
@pytest.mark.unit
def test_watchlists_db_large_sources_and_jobs_listing_within_budget(monkeypatch):
    scenario = WATCHLISTS_SCALE_SCENARIOS["watchlists_db_listing"]
    sources_guardrail = WATCHLISTS_SCALE_GUARDRAILS["sources_listing_seconds"]
    jobs_guardrail = WATCHLISTS_SCALE_GUARDRAILS["jobs_listing_seconds"]

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_watchlists_perf_stage2"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    user_id = 9301
    user_db_path = DatabasePaths.get_media_db_path(user_id)
    try:
        if user_db_path.exists():
            user_db_path.unlink()
    except Exception:
        _ = None

    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()

    source_count = scenario["source_count"]
    for idx in range(source_count):
        db.create_source(
            name=f"PerfSource{idx}",
            url=f"https://example.com/perf-source-{idx}.xml",
            source_type="rss",
            active=True,
            settings_json=None,
            tags=[],
            group_ids=[],
        )

    job_count = scenario["job_count"]
    for idx in range(job_count):
        db.create_job(
            name=f"PerfJob{idx}",
            description="perf",
            scope_json=json.dumps({"sources": [((idx % source_count) + 1)]}),
            schedule_expr="*/30 * * * *",
            schedule_timezone="UTC",
            active=True,
            max_concurrency=1,
            per_host_delay_ms=50,
            retry_policy_json=json.dumps({}),
            output_prefs_json=json.dumps({}),
            job_filters_json=None,
        )

    sources_start = time.perf_counter()
    source_rows, source_total = db.list_sources(
        q=None, tag_names=None, limit=scenario["page_size"], offset=0
    )
    sources_elapsed = time.perf_counter() - sources_start

    jobs_start = time.perf_counter()
    job_rows, jobs_total = db.list_jobs(q=None, limit=scenario["page_size"], offset=0)
    jobs_elapsed = time.perf_counter() - jobs_start

    assert source_total >= source_count  # nosec B101
    assert jobs_total >= job_count  # nosec B101
    assert len(source_rows) <= scenario["page_size"]  # nosec B101
    assert len(job_rows) <= scenario["page_size"]  # nosec B101

    # Stage 2 scale sanity guardrails for high-cardinality listings.
    assert sources_elapsed < sources_guardrail  # nosec B101
    assert jobs_elapsed < jobs_guardrail  # nosec B101
