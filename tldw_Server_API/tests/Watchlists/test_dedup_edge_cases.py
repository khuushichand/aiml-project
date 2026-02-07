"""Edge-case unit tests for watchlist dedup (seen-items) logic.

Covers: per-source dedup isolation, re-run skips seen items,
URL normalization independence, and mark_seen_item idempotency.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "1")
    base_dir = tmp_path / "test_user_dbs_dedup_edge_cases"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    yield


# ---------------------------------------------------------------------------
# 1. Dedup is per-source — same key in different sources are independent
# ---------------------------------------------------------------------------

def test_same_key_different_sources_are_independent():
    """The same item_key seen by source A does NOT mark it as seen for source B."""
    user_id = 900
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()

    src_a = db.create_source(
        name="Source A",
        url="https://a.example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )
    src_b = db.create_source(
        name="Source B",
        url="https://b.example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )

    shared_key = "article-abc-123"
    db.mark_seen_item(src_a.id, shared_key)

    # Source A has seen it
    assert db.has_seen_item(src_a.id, shared_key) is True
    # Source B has NOT seen it
    assert db.has_seen_item(src_b.id, shared_key) is False


# ---------------------------------------------------------------------------
# 2. Mark seen is idempotent
# ---------------------------------------------------------------------------

def test_mark_seen_idempotent():
    """Calling mark_seen_item twice with the same key does not raise."""
    user_id = 901
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )

    key = "duplicate-key"
    db.mark_seen_item(src.id, key)
    db.mark_seen_item(src.id, key)  # Should not raise

    assert db.has_seen_item(src.id, key) is True
    stats = db.get_seen_item_stats(src.id)
    assert int(stats["seen_count"]) == 1  # Only counted once


# ---------------------------------------------------------------------------
# 3. URL-like keys with minor variations are treated as distinct
# ---------------------------------------------------------------------------

def test_url_trailing_slash_distinct():
    """URLs with and without trailing slash produce different seen keys
    (dedup is exact-match on item_key, normalization is the fetcher's job)."""
    user_id = 902
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )

    db.mark_seen_item(src.id, "https://example.com/article")
    # Trailing slash is a different key
    assert db.has_seen_item(src.id, "https://example.com/article/") is False
    assert db.has_seen_item(src.id, "https://example.com/article") is True


def test_url_query_params_distinct():
    """URLs with different query parameters are treated as distinct keys."""
    user_id = 903
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )

    db.mark_seen_item(src.id, "https://example.com/article?v=1")
    assert db.has_seen_item(src.id, "https://example.com/article?v=2") is False
    assert db.has_seen_item(src.id, "https://example.com/article") is False


# ---------------------------------------------------------------------------
# 4. Re-run same job skips already-seen items (pipeline integration)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rerun_skips_seen_items():
    """Running the same job twice should skip items that were seen in the first run."""
    from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job

    user_id = 904
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 2}),
        tags=["dedup"],
        group_ids=[],
    )

    job = db.create_job(
        name="DedupJob",
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

    # First run: items should be ingested
    res1 = await run_watchlist_job(user_id, job.id)
    first_ingested = res1.get("items_ingested", 0)
    assert first_ingested >= 1

    # Second run: same items should be skipped (already seen)
    res2 = await run_watchlist_job(user_id, job.id)
    second_ingested = res2.get("items_ingested", 0)
    # In TEST_MODE the same deterministic items are returned, so all should be dupes
    assert second_ingested == 0


# ---------------------------------------------------------------------------
# 5. Seen keys cleared → items re-ingested on next run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_seen_allows_reingestion():
    """After clearing seen keys, the same items should be re-ingested."""
    from tldw_Server_API.app.core.Watchlists.pipeline import run_watchlist_job

    user_id = 905
    db = WatchlistsDatabase.for_user(user_id)

    src = db.create_source(
        name="Feed",
        url="https://example.com/feed.xml",
        source_type="rss",
        active=True,
        settings_json=json.dumps({"limit": 1}),
        tags=["clear"],
        group_ids=[],
    )

    job = db.create_job(
        name="ClearJob",
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

    # First run
    res1 = await run_watchlist_job(user_id, job.id)
    assert res1.get("items_ingested", 0) >= 1

    # Clear seen keys for this source
    db.clear_seen_items(src.id)
    stats = db.get_seen_item_stats(src.id)
    assert int(stats["seen_count"]) == 0

    # Third run: items should be re-ingested since seen keys cleared
    res3 = await run_watchlist_job(user_id, job.id)
    assert res3.get("items_ingested", 0) >= 1
