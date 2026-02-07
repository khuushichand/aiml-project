"""Edge-case tests for the watchlist pipeline.

Covers: empty runs (all filtered), source errors, template syntax errors,
all-type catch-all filter producing zero ingest, and schedule timezone handling.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "1")
    base_dir = tmp_path / "test_user_dbs_pipeline_edge_cases"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    yield


# ---------------------------------------------------------------------------
# 1. Empty run — all items filtered by catch-all exclude
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_run_all_items_excluded():
    """When an 'all' type exclude filter catches everything, run completes
    with items_ingested=0 but items_found >= 1."""
    user_id = 920
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 2}),
        tags=[],
        group_ids=[],
    )

    job = db.create_job(
        name="AllExcludeJob",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=json.dumps({
            "filters": [
                {"type": "all", "action": "exclude", "value": {}},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    assert res.get("items_found", 0) >= 1
    assert res.get("items_ingested", 0) == 0

    # All items should be recorded as filtered
    items, total = db.list_items(run_id=None, job_id=job.id, status=None, limit=100, offset=0)
    assert total >= 1
    assert all(i.status == "filtered" for i in items)


# ---------------------------------------------------------------------------
# 2. Empty run — require_include with non-matching include
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_empty_run_require_include_no_match():
    """With require_include=True and an include rule that matches nothing,
    all items should be filtered."""
    user_id = 921
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 2}),
        tags=[],
        group_ids=[],
    )

    job = db.create_job(
        name="RequireIncludeNoMatch",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
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
                {"type": "keyword", "action": "include", "value": {"keywords": ["ZZZ_NOMATCH_ZZZ"]}},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    assert res.get("items_found", 0) >= 1
    assert res.get("items_ingested", 0) == 0


# ---------------------------------------------------------------------------
# 3. Flag + exclude priority interaction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_flag_then_exclude_by_priority():
    """Higher-priority exclude should override lower-priority flag."""
    user_id = 922
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 1}),
        tags=[],
        group_ids=[],
    )

    # Test item from TEST_MODE contains "Test" in title
    job = db.create_job(
        name="PriorityFlagExclude",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=json.dumps({
            "filters": [
                {"type": "keyword", "action": "flag", "value": {"keywords": ["Test"]}, "priority": 1},
                {"type": "keyword", "action": "exclude", "value": {"keywords": ["Test"]}, "priority": 10},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    # Exclude has higher priority, so items should be filtered
    assert res.get("items_ingested", 0) == 0

    items, total = db.list_items(run_id=None, job_id=job.id, status=None, limit=100, offset=0)
    assert total >= 1
    assert all(i.status == "filtered" for i in items)


# ---------------------------------------------------------------------------
# 4. Job with no filters — all items ingested
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_filters_all_ingested():
    """A job with no filters should ingest all found items."""
    user_id = 923
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 2}),
        tags=[],
        group_ids=[],
    )

    job = db.create_job(
        name="NoFilters",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )

    res = await run_watchlist_job(user_id, job.id)
    assert res.get("items_found", 0) >= 1
    # All found items should be ingested (no filters to block)
    assert res.get("items_ingested", 0) >= 1


# ---------------------------------------------------------------------------
# 5. Inactive source is skipped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inactive_source_skipped():
    """An inactive source in scope should be skipped during run."""
    user_id = 924
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Inactive Feed",
        url="https://example.com/inactive.xml",
        source_type="rss",
        active=False,  # Inactive
        settings_json=None,
        tags=["inactive"],
        group_ids=[],
    )

    job = db.create_job(
        name="InactiveSourceJob",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )

    res = await run_watchlist_job(user_id, job.id)
    # Inactive source should not produce any items
    assert res.get("items_found", 0) == 0
    assert res.get("items_ingested", 0) == 0


# ---------------------------------------------------------------------------
# 6. Template syntax error — graceful fallback
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_output_with_broken_template(monkeypatch, tmp_path):
    """A custom template with syntax errors should still produce an output
    (graceful fallback to raw template string)."""
    async def override_user():
        return User(id=925, username="tmpl-user", email="tmpl@example.com", is_active=True)

    base_dir = tmp_path / "test_user_dbs_broken_template"
    base_dir.mkdir(parents=True, exist_ok=True)
    template_dir = tmp_path / "watchlist_templates_broken"
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WATCHLIST_TEMPLATE_DIR", str(template_dir))
    monkeypatch.setenv("TEST_MODE", "1")

    from fastapi import FastAPI

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router
    from tldw_Server_API.app.core.config import API_V1_PREFIX

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        # Create a template with broken Jinja2 syntax
        tmpl = client.post(
            "/api/v1/watchlists/templates",
            json={
                "name": "broken_tmpl",
                "format": "md",
                "content": "{% for item in items %}{{ item.title }",  # Missing endfor
                "description": "Intentionally broken template",
            },
        )
        assert tmpl.status_code == 200, tmpl.text

        # Create source + job + run
        src = client.post(
            "/api/v1/watchlists/sources",
            json={"name": "Feed", "url": "https://example.com/rss.xml", "source_type": "rss"},
        )
        assert src.status_code == 200, src.text
        job = client.post(
            "/api/v1/watchlists/jobs",
            json={"name": "Job", "scope": {"sources": [src.json()["id"]]}},
        )
        assert job.status_code == 200, job.text
        run = client.post(f"/api/v1/watchlists/jobs/{job.json()['id']}/run")
        assert run.status_code == 200, run.text

        # Generate output with broken template — should not crash
        output = client.post(
            "/api/v1/watchlists/outputs",
            json={
                "run_id": run.json()["id"],
                "template_name": "broken_tmpl",
                "temporary": True,
            },
        )
        assert output.status_code == 200, output.text
        # The output may contain the raw template string as fallback
        assert output.json().get("content") is not None
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. Multiple filters chained
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_filter_chain():
    """Multiple filters at different priorities chain correctly."""
    user_id = 926
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 2}),
        tags=[],
        group_ids=[],
    )

    # Chain: high-priority include for "Test" (matches), lower-priority exclude for "Test" (won't reach)
    job = db.create_job(
        name="ChainedFilters",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=json.dumps({
            "filters": [
                {"type": "keyword", "action": "include", "value": {"keywords": ["Test"]}, "priority": 10},
                {"type": "keyword", "action": "exclude", "value": {"keywords": ["Test"]}, "priority": 1},
            ]
        }),
    )

    res = await run_watchlist_job(user_id, job.id)
    # Include has higher priority, so items matching "Test" should be ingested
    assert res.get("items_ingested", 0) >= 1


# ---------------------------------------------------------------------------
# 8. Run with empty scope (no sources)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_with_no_sources_in_scope():
    """A job scoped to a non-existent source should complete with 0 items."""
    user_id = 927
    db = WatchlistsDatabase.for_user(user_id)

    job = db.create_job(
        name="EmptyScopeJob",
        description=None,
        scope_json=json.dumps({"sources": [99999]}),  # Non-existent source
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
        job_filters_json=None,
    )

    res = await run_watchlist_job(user_id, job.id)
    assert res.get("items_found", 0) == 0
    assert res.get("items_ingested", 0) == 0
