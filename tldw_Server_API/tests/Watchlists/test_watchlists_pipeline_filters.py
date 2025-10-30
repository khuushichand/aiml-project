import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    # Force offline behavior and isolate DBs
    monkeypatch.setenv("TEST_MODE", "1")
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_pipeline_filters"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    yield


@pytest.mark.asyncio
async def test_exclude_filter_blocks_ingestion_and_records_filtered():
    user_id = 812
    db = WatchlistsDatabase.for_user(user_id)

    # Create a simple RSS source (test mode generates one item with title/summary)
    rss = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 1}),
        tags=["news"],
        group_ids=[],
    )

    # Create job scoped to the single source with an exclude keyword rule matching the test item
    job = db.create_job(
        name="ExcludeJob",
        description=None,
        scope_json=json.dumps({"sources": [rss.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=json.dumps({
            "filters": [
                {"type": "keyword", "action": "exclude", "value": {"keywords": ["Test"], "match": "any"}},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    # items_found at least 1 (rss test item)
    assert res.get("items_found", 0) >= 1

    # Verify a filtered scraped item exists and nothing ingested from this source
    items, total = db.list_items(run_id=None, job_id=job.id, status=None, limit=100, offset=0)
    assert total >= 1
    assert any(i.status == "filtered" for i in items)


@pytest.mark.asyncio
async def test_flag_filter_ingests_and_tags_flagged():
    user_id = 813
    db = WatchlistsDatabase.for_user(user_id)

    rss = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 1}),
        tags=["ai"],
        group_ids=[],
    )

    # Flag rule should ingest and mark content with the 'flagged' tag in Collections
    job = db.create_job(
        name="FlagJob",
        description=None,
        scope_json=json.dumps({"sources": [rss.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=json.dumps({
            "filters": [
                {"type": "keyword", "action": "flag", "value": {"keywords": ["Test"], "match": "any"}},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    assert res.get("items_ingested", 0) >= 1

    # Verify Collections entry has 'flagged' tag attached
    collections_db = CollectionsDatabase.for_user(user_id)
    items, total = collections_db.list_content_items(page=1, size=50, job_id=job.id)
    assert total >= 1
    assert any("flagged" in (itm.tags or []) for itm in items)


@pytest.mark.asyncio
async def test_include_only_gating_blocks_site_items_without_match():
    user_id = 814
    db = WatchlistsDatabase.for_user(user_id)

    # Create a site source with simple scrape rules; TEST_MODE yields deterministic items
    rules = {"list_url": "https://example.com/articles", "limit": 2}
    site = db.create_source(
        name="Site",
        url="https://example.com/",
        source_type="site",
        active=True,
        settings_json=json.dumps({"scrape_rules": rules}),
        tags=["news"],
        group_ids=[],
    )

    # Job with include-only gating enabled and an include rule that does NOT match test items
    job = db.create_job(
        name="SiteIncludeOnly",
        description=None,
        scope_json=json.dumps({"sources": [site.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=json.dumps({
            "require_include": True,
            "filters": [
                {"type": "keyword", "action": "include", "value": {"keywords": ["NoMatch"], "match": "any"}},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    # Items found but none ingested due to include-only gating without a match
    assert res.get("items_found", 0) >= 1
    assert res.get("items_ingested", 0) == 0

    items, total = db.list_items(run_id=None, job_id=job.id, status=None, limit=100, offset=0)
    assert total >= 1
    assert all(i.status == "filtered" for i in items)
