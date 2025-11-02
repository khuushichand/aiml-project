import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.Watchlists import pipeline as wl_pipeline


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    # isolate per-user DBs
    base_dir = Path.cwd() / "Databases" / "test_user_dbs_cond"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    # Ensure pipeline does not fall back to TEST_MODE short-circuit
    monkeypatch.delenv("TEST_MODE", raising=False)
    # not using TEST_MODE here; we mock fetcher
    yield


@pytest.mark.asyncio
async def test_rss_conditional_304_updates_last_scraped_and_status(monkeypatch):
    user_id = 801
    # Ensure a clean slate for this user DB
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    p = DatabasePaths.get_media_db_path(user_id)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 5}),
        tags=["news"],
        group_ids=[],
    )

    # Stub fetcher to return 304
    called = {"n": 0}

    async def _stub_fetch(url, **kwargs):
        called["n"] += 1
        return {"status": 304, "etag": None, "last_modified": None}

    monkeypatch.setattr(wl_pipeline, "fetch_rss_feed", _stub_fetch)
    monkeypatch.setattr(wl_pipeline, "fetch_rss_feed_history", _stub_fetch)

    job = db.create_job(
        name="Job",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
    )

    res = await wl_pipeline.run_watchlist_job(user_id, job.id)
    assert res.get("items_found", 0) == 0
    assert called["n"] == 1

    # status and last_scraped_at set
    s = db.get_source(src.id)
    assert s.last_scraped_at is not None
    assert (s.status or "").startswith("not_modified")


@pytest.mark.asyncio
async def test_rss_retry_after_defers_and_skips(monkeypatch):
    user_id = 802
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    p = DatabasePaths.get_media_db_path(user_id)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 5}),
        tags=["alpha"],
        group_ids=[],
    )

    called = {"n": 0}

    async def _stub_fetch(url, **kwargs):
        called["n"] += 1
        return {"status": 429, "retry_after": 3600}

    monkeypatch.setattr(wl_pipeline, "fetch_rss_feed", _stub_fetch)
    monkeypatch.setattr(wl_pipeline, "fetch_rss_feed_history", _stub_fetch)

    job = db.create_job(
        name="Job",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
    )

    # First run: returns 429 and defers
    res = await wl_pipeline.run_watchlist_job(user_id, job.id)
    assert called["n"] == 1
    s = db.get_source(src.id)
    assert s.defer_until is not None
    # Immediate next run should skip (not call fetch)
    res2 = await wl_pipeline.run_watchlist_job(user_id, job.id)
    assert called["n"] == 1  # unchanged


@pytest.mark.asyncio
async def test_rss_200_sets_etag_last_modified_and_ingests(monkeypatch):
    user_id = 803
    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    p = DatabasePaths.get_media_db_path(user_id)
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 2}),
        tags=["beta"],
        group_ids=[],
    )

    called = {"n": 0}

    async def _stub_fetch(url, **kwargs):
        called["n"] += 1
        return {
            "status": 200,
            "etag": "W/\"abc123\"",
            "last_modified": "Wed, 21 Oct 2015 07:28:00 GMT",
            "items": [
                {"title": "T1", "url": "https://example.com/a", "summary": "s", "guid": "g1"},
                {"title": "T2", "url": "https://example.com/b", "summary": "s", "guid": "g2"},
            ],
        }

    monkeypatch.setattr(wl_pipeline, "fetch_rss_feed", _stub_fetch)
    monkeypatch.setattr(wl_pipeline, "fetch_rss_feed_history", _stub_fetch)
    # Stub site article fetch to avoid network
    def _stub_article(url):
        return {"title": "X", "url": url, "content": "hello", "author": None}
    monkeypatch.setattr(wl_pipeline, "fetch_site_article", _stub_article)

    job = db.create_job(
        name="Job",
        description=None,
        scope_json=json.dumps({"sources": [src.id]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
    )

    res = await wl_pipeline.run_watchlist_job(user_id, job.id)
    assert called["n"] == 1
    assert res.get("items_found", 0) == 2
    assert res.get("items_ingested", 0) >= 1
    s = db.get_source(src.id)
    assert (s.etag or "").startswith("W/")
    assert (s.last_modified or "").endswith("GMT")
