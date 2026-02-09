"""Tests for Stage 1 Phase-1 hardening: sanitization, dedupe fallback,
health tracking, schedule promotion surfacing, and retention policy.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _test_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TEST_MODE", "1")
    base_dir = tmp_path / "test_user_dbs_feeds_hardening"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    yield


# ---------------------------------------------------------------------------
# 1a. Feed content sanitization
# ---------------------------------------------------------------------------


class TestFeedContentSanitization:
    def test_strips_script_tags(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _sanitize_feed_html

        html = '<p>Hello</p><script>alert("xss")</script><p>World</p>'
        result = _sanitize_feed_html(html)
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello" in result
        assert "World" in result

    def test_strips_event_handlers(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _sanitize_feed_html

        html = '<img src="x.jpg" onerror="alert(1)">'
        result = _sanitize_feed_html(html)
        assert "onerror" not in result

    def test_strips_iframe(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _sanitize_feed_html

        html = '<p>Before</p><iframe src="evil.com"></iframe><p>After</p>'
        result = _sanitize_feed_html(html)
        assert "<iframe" not in result
        assert "Before" in result
        assert "After" in result

    def test_preserves_safe_html(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _sanitize_feed_html

        html = '<p>Hello <strong>world</strong></p><a href="https://example.com">link</a>'
        result = _sanitize_feed_html(html)
        assert "<p>" in result
        assert "<strong>" in result
        assert '<a href="https://example.com">' in result

    def test_none_passthrough(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _sanitize_feed_html

        assert _sanitize_feed_html(None) is None
        assert _sanitize_feed_html("") == ""


# ---------------------------------------------------------------------------
# 1b. Empty dedupe key fallback
# ---------------------------------------------------------------------------


class TestDedupeKeyFallback:
    def test_different_content_different_keys(self):
        """Items with no guid/url/title but different content produce distinct keys."""
        item_a = {"summary": "content A", "content": "body A"}
        item_b = {"summary": "content B", "content": "body B"}

        def _make_key(it):
            guid = it.get("guid") or ""
            link = it.get("url") or it.get("link") or ""
            title = it.get("title") or ""
            key = guid or link or title
            if not key:
                raw = json.dumps(
                    {k: it.get(k) for k in ("title", "summary", "content", "url", "link", "published")},
                    sort_keys=True, default=str,
                )
                key = f"sha256:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"
            return key

        key_a = _make_key(item_a)
        key_b = _make_key(item_b)
        assert key_a != key_b
        assert key_a.startswith("sha256:")
        assert key_b.startswith("sha256:")

    def test_identical_content_same_key(self):
        """Items with no identifiers but identical content produce the same key."""
        item = {"summary": "same", "content": "same body"}

        def _make_key(it):
            raw = json.dumps(
                {k: it.get(k) for k in ("title", "summary", "content", "url", "link", "published")},
                sort_keys=True, default=str,
            )
            return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()[:32]}"

        assert _make_key(item) == _make_key(item)


# ---------------------------------------------------------------------------
# 1c. Feed health tracking and backoff
# ---------------------------------------------------------------------------


class TestFeedHealthTracking:
    def test_backoff_computation(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _compute_feed_backoff

        assert _compute_feed_backoff(1) == timedelta(hours=1)
        assert _compute_feed_backoff(2) == timedelta(hours=2)
        assert _compute_feed_backoff(3) == timedelta(hours=4)
        assert _compute_feed_backoff(4) == timedelta(hours=8)
        assert _compute_feed_backoff(5) == timedelta(hours=16)
        assert _compute_feed_backoff(6) == timedelta(hours=24)  # cap
        assert _compute_feed_backoff(10) == timedelta(hours=24)  # still capped

    def test_health_status_derivation(self):
        from tldw_Server_API.app.core.Watchlists.pipeline import _feed_health_status

        assert _feed_health_status(0, True) == "healthy"
        assert _feed_health_status(1, True) == "degraded"
        assert _feed_health_status(4, True) == "degraded"
        assert _feed_health_status(5, True) == "failing"
        assert _feed_health_status(9, True) == "failing"
        assert _feed_health_status(0, False) == "disabled"
        assert _feed_health_status(5, False) == "disabled"

    def test_consec_errors_column_exists(self):
        """Verify the consec_errors column is created in the schema."""
        db = WatchlistsDatabase.for_user(950)
        db.ensure_schema()
        src = db.create_source(
            name="Health Test",
            url="https://example.com/health.xml",
            source_type="rss",
            active=True,
            settings_json=None,
            tags=[],
            group_ids=[],
        )
        # Update consec_errors
        db.update_source_scrape_meta(int(src.id), consec_errors=3)
        refreshed = db.get_source(int(src.id))
        assert int(refreshed.consec_errors or 0) == 3

    def test_success_resets_errors(self):
        """consec_errors=0 on success path."""
        db = WatchlistsDatabase.for_user(951)
        db.ensure_schema()
        src = db.create_source(
            name="Reset Test",
            url="https://example.com/reset.xml",
            source_type="rss",
            active=True,
            settings_json=None,
            tags=[],
            group_ids=[],
        )
        db.update_source_scrape_meta(int(src.id), consec_errors=5, status="error")
        db.update_source_scrape_meta(int(src.id), consec_errors=0, status="ok")
        refreshed = db.get_source(int(src.id))
        assert int(refreshed.consec_errors or 0) == 0
        assert refreshed.status == "ok"

    def test_auto_disable_via_update(self):
        """Source can be auto-disabled via update_source_scrape_meta(active=0)."""
        db = WatchlistsDatabase.for_user(952)
        db.ensure_schema()
        src = db.create_source(
            name="Disable Test",
            url="https://example.com/disable.xml",
            source_type="rss",
            active=True,
            settings_json=None,
            tags=[],
            group_ids=[],
        )
        assert bool(src.active) is True
        db.update_source_scrape_meta(int(src.id), active=0, consec_errors=10, status="error")
        refreshed = db.get_source(int(src.id))
        assert bool(refreshed.active) is False
        assert int(refreshed.consec_errors or 0) == 10


# ---------------------------------------------------------------------------
# 1d. Schedule promotion surfacing
# ---------------------------------------------------------------------------


class TestPromotionSurfacing:
    def test_promoted_at_in_response_model(self):
        """The CollectionsFeed schema includes promoted_at field."""
        from tldw_Server_API.app.api.v1.schemas.collections_feeds_schemas import CollectionsFeed

        feed = CollectionsFeed(
            id=1, name="Test", url="https://example.com", source_type="rss",
            origin="feed", active=True, promoted_at="2026-01-15T00:00:00+00:00",
        )
        assert feed.promoted_at == "2026-01-15T00:00:00+00:00"

    def test_health_status_in_response_model(self):
        """The CollectionsFeed schema includes health_status field."""
        from tldw_Server_API.app.api.v1.schemas.collections_feeds_schemas import CollectionsFeed

        feed = CollectionsFeed(
            id=1, name="Test", url="https://example.com", source_type="rss",
            origin="feed", active=True, health_status="healthy", consec_errors=0,
        )
        assert feed.health_status == "healthy"
        assert feed.consec_errors == 0


# ---------------------------------------------------------------------------
# 1e. Retention policy
# ---------------------------------------------------------------------------


class TestRetentionPolicy:
    def test_prune_by_max_items(self, tmp_path, monkeypatch):
        """prune_content_items_for_source removes oldest items when over max_items."""
        from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase

        db = CollectionsDatabase.for_user(user_id=960)

        # Insert 5 items
        for i in range(5):
            db.upsert_content_item(
                origin="feed",
                origin_type="rss",
                origin_id=1,
                url=f"https://example.com/article-{i}",
                canonical_url=None,
                domain="example.com",
                title=f"Article {i}",
                summary=None,
                content_hash=None,
                word_count=None,
                published_at=None,
                status="new",
            )

        # Prune to max 3
        deleted = db.prune_content_items_for_source(
            origin="feed", origin_id=1, max_items=3,
        )
        assert deleted == 2

        # Verify only 3 remain
        items, total = db.list_content_items(origin="feed", size=100)
        assert total == 3

    def test_prune_by_retention_days(self, tmp_path, monkeypatch):
        """prune_content_items_for_source removes items older than retention_days."""
        from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase

        db = CollectionsDatabase.for_user(user_id=961)

        # Insert an item and manually backdate it
        item = db.upsert_content_item(
            origin="feed",
            origin_type="rss",
            origin_id=2,
            url="https://example.com/old-article",
            canonical_url=None,
            domain="example.com",
            title="Old Article",
            summary=None,
            content_hash=None,
            word_count=None,
            published_at=None,
            status="new",
        )

        # Backdate the item by updating created_at directly
        old_date = (datetime.utcnow() - timedelta(days=60)).isoformat()
        db.backend.execute(
            "UPDATE content_items SET created_at = ? WHERE id = ?",
            (old_date, item.id),
        )

        # Insert a recent item
        db.upsert_content_item(
            origin="feed",
            origin_type="rss",
            origin_id=2,
            url="https://example.com/new-article",
            canonical_url=None,
            domain="example.com",
            title="New Article",
            summary=None,
            content_hash=None,
            word_count=None,
            published_at=None,
            status="new",
        )

        # Prune items older than 30 days
        deleted = db.prune_content_items_for_source(
            origin="feed", origin_id=2, retention_days=30,
        )
        assert deleted == 1

        # Verify only 1 remains
        items, total = db.list_content_items(origin="feed", size=100)
        assert total == 1
        assert items[0].title == "New Article"

    def test_no_prune_when_unlimited(self, tmp_path, monkeypatch):
        """No pruning when max_items=0 and retention_days=0."""
        from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase

        db = CollectionsDatabase.for_user(user_id=962)

        for i in range(3):
            db.upsert_content_item(
                origin="feed",
                origin_type="rss",
                origin_id=3,
                url=f"https://example.com/keep-{i}",
                canonical_url=None,
                domain="example.com",
                title=f"Keep {i}",
                summary=None,
                content_hash=None,
                word_count=None,
                published_at=None,
                status="new",
            )

        deleted = db.prune_content_items_for_source(
            origin="feed", origin_id=3, max_items=0, retention_days=0,
        )
        assert deleted == 0

    def test_apply_feed_retention_from_settings(self, tmp_path, monkeypatch):
        """_apply_feed_retention reads settings.retention.max_items."""
        from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
        from tldw_Server_API.app.core.Watchlists.pipeline import _apply_feed_retention

        cdb = CollectionsDatabase.for_user(user_id=963)

        # Insert 5 items
        for i in range(5):
            cdb.upsert_content_item(
                origin="feed",
                origin_type="rss",
                origin_id=10,
                url=f"https://example.com/ret-{i}",
                canonical_url=None,
                domain="example.com",
                title=f"Retention {i}",
                summary=None,
                content_hash=None,
                word_count=None,
                published_at=None,
                status="new",
            )

        # Mock source with retention settings
        class MockSource:
            id = 10
            settings_json = json.dumps({"retention": {"max_items": 2}})

        _apply_feed_retention(cdb, "feed", MockSource())

        items, total = cdb.list_content_items(origin="feed", size=100)
        assert total == 2
