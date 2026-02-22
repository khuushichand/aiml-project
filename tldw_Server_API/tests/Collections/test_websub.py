"""
Tests for WebSub (PubSubHubbub) push support in Collections Feeds.

Covers:
- Hub discovery from Atom/RSS XML and HTTP Link headers
- Token/secret generation
- HMAC signature verification
- Push notification XML parsing
- Hub challenge verification callback
- Push notification callback with signature validation
- Database CRUD for websub subscriptions
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.config import settings


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def websub_app(monkeypatch):
    monkeypatch.setenv("MINIMAL_TEST_APP", "0")
    monkeypatch.setenv("ULTRA_MINIMAL_APP", "0")
    monkeypatch.setenv("ROUTES_ENABLE", "collections-feeds,collections-websub")
    monkeypatch.setenv("WEBSUB_CALLBACK_BASE_URL", "https://test.example.com/api/v1")

    base_dir = Path.cwd() / "Databases" / "test_websub_api"
    shutil.rmtree(base_dir, ignore_errors=True)
    base_dir.mkdir(parents=True, exist_ok=True)
    prev_base_dir = settings.get("USER_DB_BASE_DIR")
    settings.USER_DB_BASE_DIR = str(base_dir)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    from tldw_Server_API.app import main as app_main

    importlib.reload(app_main)
    fastapi_app = app_main.app

    try:
        yield fastapi_app
    finally:
        fastapi_app.dependency_overrides.clear()
        if prev_base_dir is not None:
            settings.USER_DB_BASE_DIR = prev_base_dir
        else:
            try:
                del settings.USER_DB_BASE_DIR
            except AttributeError:
                pass


@pytest.fixture()
def db_for_test():
    """Create a WatchlistsDatabase for testing."""
    import uuid

    from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase

    db = WatchlistsDatabase.for_user(user_id=999)
    db.ensure_schema()
    # Create a source with unique URL to avoid UNIQUE constraint conflicts
    unique_url = f"https://example.com/feed-{uuid.uuid4().hex[:8]}.xml"
    source = db.create_source(
        name="WebSub Test Feed",
        url=unique_url,
        source_type="rss",
        active=True,
    )
    return db, source


# ---------------------------------------------------------------------------
# Hub discovery tests
# ---------------------------------------------------------------------------


ATOM_FEED_WITH_HUB = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Feed</title>
  <link rel="self" href="https://example.com/feed.atom" />
  <link rel="hub" href="https://hub.example.com/" />
  <entry>
    <title>Test Entry</title>
    <link rel="alternate" href="https://example.com/post/1" />
    <id>urn:uuid:1234</id>
    <updated>2025-01-01T00:00:00Z</updated>
    <summary>Test summary</summary>
  </entry>
</feed>
"""

RSS_FEED_WITH_HUB = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Test Feed</title>
    <atom:link rel="self" href="https://example.com/feed.xml" />
    <atom:link rel="hub" href="https://hub.example.com/" />
    <item>
      <title>Test Item</title>
      <link>https://example.com/post/1</link>
      <guid>guid-1</guid>
      <description>Test description</description>
    </item>
  </channel>
</rss>
"""

RSS_FEED_NO_HUB = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Test Item</title>
      <link>https://example.com/post/1</link>
    </item>
  </channel>
</rss>
"""


def test_discover_hub_url_from_atom_xml():
    from tldw_Server_API.app.core.Watchlists.fetchers import discover_hub_url

    hub, self_url = discover_hub_url(ATOM_FEED_WITH_HUB)
    assert hub == "https://hub.example.com/"
    assert self_url == "https://example.com/feed.atom"


def test_discover_hub_url_from_rss_xml():
    from tldw_Server_API.app.core.Watchlists.fetchers import discover_hub_url

    hub, self_url = discover_hub_url(RSS_FEED_WITH_HUB)
    assert hub == "https://hub.example.com/"
    assert self_url == "https://example.com/feed.xml"


def test_discover_hub_url_from_link_header():
    from tldw_Server_API.app.core.Watchlists.fetchers import discover_hub_url

    headers = {
        "Link": '<https://hub.example.com/>; rel="hub", <https://example.com/feed.xml>; rel="self"'
    }
    hub, self_url = discover_hub_url(RSS_FEED_NO_HUB, response_headers=headers)
    assert hub == "https://hub.example.com/"
    assert self_url == "https://example.com/feed.xml"


def test_discover_hub_url_missing():
    from tldw_Server_API.app.core.Watchlists.fetchers import discover_hub_url

    hub, self_url = discover_hub_url(RSS_FEED_NO_HUB)
    assert hub is None
    assert self_url is None


def test_discover_hub_url_xml_takes_precedence_over_missing_header():
    """When XML has hub but no Link header, still finds it."""
    from tldw_Server_API.app.core.Watchlists.fetchers import discover_hub_url

    hub, self_url = discover_hub_url(ATOM_FEED_WITH_HUB, response_headers={})
    assert hub == "https://hub.example.com/"


# ---------------------------------------------------------------------------
# Token / secret generation tests
# ---------------------------------------------------------------------------


def test_generate_callback_token_unique():
    from tldw_Server_API.app.core.Watchlists.websub import generate_callback_token

    t1 = generate_callback_token()
    t2 = generate_callback_token()
    assert t1 != t2
    assert len(t1) > 20


def test_generate_secret():
    from tldw_Server_API.app.core.Watchlists.websub import generate_secret

    s = generate_secret()
    assert len(s) == 64  # 32 bytes hex = 64 chars


def test_build_callback_url(monkeypatch):
    monkeypatch.setenv("WEBSUB_CALLBACK_BASE_URL", "https://myserver.com/api/v1")
    from tldw_Server_API.app.core.Watchlists.websub import build_callback_url

    # With user_id — encodes user in the URL path for multi-user per-DB routing
    url = build_callback_url("test-token-123", user_id=42)
    assert url == "https://myserver.com/api/v1/websub/callback/42/test-token-123"

    # Without user_id — backwards-compatible format
    url_legacy = build_callback_url("test-token-123")
    assert url_legacy == "https://myserver.com/api/v1/websub/callback/test-token-123"


def test_build_callback_url_no_env(monkeypatch):
    monkeypatch.delenv("WEBSUB_CALLBACK_BASE_URL", raising=False)
    # Need to reimport to pick up env change
    import importlib

    import tldw_Server_API.app.core.Watchlists.websub as ws_mod

    importlib.reload(ws_mod)
    with pytest.raises(RuntimeError, match="WEBSUB_CALLBACK_BASE_URL"):
        ws_mod.build_callback_url("test-token")


# ---------------------------------------------------------------------------
# HMAC signature verification tests
# ---------------------------------------------------------------------------


def test_verify_signature_valid():
    from tldw_Server_API.app.core.Watchlists.websub import verify_hub_signature

    body = b"<feed>test content</feed>"
    secret = "mysecret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    sig_header = f"sha256={digest}"

    assert verify_hub_signature(body, sig_header, secret) is True


def test_verify_signature_sha1():
    from tldw_Server_API.app.core.Watchlists.websub import verify_hub_signature

    body = b"<feed>test</feed>"
    secret = "mysecret"
    digest = hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()
    sig_header = f"sha1={digest}"

    assert verify_hub_signature(body, sig_header, secret) is True


def test_verify_signature_invalid():
    from tldw_Server_API.app.core.Watchlists.websub import verify_hub_signature

    body = b"<feed>test content</feed>"
    assert verify_hub_signature(body, "sha256=wrongdigest", "mysecret") is False


def test_verify_signature_missing():
    from tldw_Server_API.app.core.Watchlists.websub import verify_hub_signature

    assert verify_hub_signature(b"data", None, "secret") is False
    assert verify_hub_signature(b"data", "", "secret") is False


def test_verify_signature_unsupported_algo():
    from tldw_Server_API.app.core.Watchlists.websub import verify_hub_signature

    assert verify_hub_signature(b"data", "md5=abc123", "secret") is False


# ---------------------------------------------------------------------------
# Push notification XML parsing tests
# ---------------------------------------------------------------------------


ATOM_PUSH_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Push Feed</title>
  <entry>
    <title>New Post</title>
    <link rel="alternate" href="https://example.com/new-post" />
    <id>urn:uuid:5678</id>
    <updated>2025-06-01T12:00:00Z</updated>
    <summary>A new post summary</summary>
  </entry>
  <entry>
    <title>Another Post</title>
    <link rel="alternate" href="https://example.com/another-post" />
    <id>urn:uuid:9999</id>
    <updated>2025-06-01T11:00:00Z</updated>
    <summary>Another summary</summary>
  </entry>
</feed>
"""

RSS_PUSH_XML = b"""\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Push RSS</title>
    <item>
      <title>RSS Item</title>
      <link>https://example.com/rss-item</link>
      <guid>rss-guid-1</guid>
      <description>RSS item description</description>
      <pubDate>Sat, 01 Jun 2025 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parse_push_items_atom():
    from tldw_Server_API.app.core.Watchlists.websub import parse_push_items

    items = parse_push_items(ATOM_PUSH_XML)
    assert len(items) == 2
    assert items[0]["title"] == "New Post"
    assert items[0]["url"] == "https://example.com/new-post"
    assert items[0]["guid"] == "urn:uuid:5678"
    assert items[1]["title"] == "Another Post"


def test_parse_push_items_rss():
    from tldw_Server_API.app.core.Watchlists.websub import parse_push_items

    items = parse_push_items(RSS_PUSH_XML)
    assert len(items) == 1
    assert items[0]["title"] == "RSS Item"
    assert items[0]["url"] == "https://example.com/rss-item"
    assert items[0]["guid"] == "rss-guid-1"
    assert items[0]["published"] == "Sat, 01 Jun 2025 12:00:00 GMT"


def test_parse_push_items_invalid_xml():
    from tldw_Server_API.app.core.Watchlists.websub import parse_push_items

    items = parse_push_items(b"<not valid xml")
    assert items == []


def test_parse_push_items_empty():
    from tldw_Server_API.app.core.Watchlists.websub import parse_push_items

    items = parse_push_items(b"")
    assert items == []


# ---------------------------------------------------------------------------
# Database CRUD tests
# ---------------------------------------------------------------------------


def test_subscription_crud(db_for_test):
    import uuid

    db, source = db_for_test
    token = f"test-token-crud-{uuid.uuid4().hex[:8]}"

    # Create
    sub = db.create_websub_subscription(
        source_id=source.id,
        hub_url="https://hub.example.com/",
        topic_url=source.url,
        callback_token=token,
        secret="test-secret-crud",
        lease_seconds=86400,
    )
    assert sub.id is not None
    assert sub.state == "pending"
    assert sub.hub_url == "https://hub.example.com/"
    assert sub.callback_token == token

    # Read by token
    found = db.get_websub_subscription_by_token(token)
    assert found is not None
    assert found.id == sub.id

    # Read by source
    found_source = db.get_websub_subscription_for_source(source.id)
    assert found_source is not None
    assert found_source.id == sub.id

    # Update
    updated = db.update_websub_subscription(sub.id, {
        "state": "verified",
        "verified_at": "2025-01-01T00:00:00Z",
        "expires_at": "2025-01-11T00:00:00Z",
    })
    assert updated.state == "verified"
    assert updated.verified_at == "2025-01-01T00:00:00Z"
    assert updated.expires_at == "2025-01-11T00:00:00Z"

    # Delete
    db.delete_websub_subscription(sub.id)
    assert db.get_websub_subscription_by_token(token) is None


def test_websub_table_created(db_for_test):
    db, _source = db_for_test
    # Just verify the table exists by querying it
    rows = db.backend.execute(
        "SELECT COUNT(*) AS cnt FROM feed_websub_subscriptions WHERE user_id = ?",
        (db.user_id,),
    ).first
    assert rows is not None
    assert int(rows.get("cnt", 0)) >= 0


def test_list_expiring_subscriptions(db_for_test):
    import uuid

    db, source = db_for_test

    # Create a verified subscription that expires soon
    sub = db.create_websub_subscription(
        source_id=source.id,
        hub_url="https://hub.example.com/",
        topic_url=source.url,
        callback_token=f"test-token-expiring-{uuid.uuid4().hex[:8]}",
        secret="test-secret-expiring",
        lease_seconds=3600,
    )
    db.update_websub_subscription(sub.id, {
        "state": "verified",
        "expires_at": "2020-01-01T00:00:00+00:00",  # already expired
    })

    # List should find it
    expiring = db.list_expiring_websub_subscriptions("2025-01-01T00:00:00+00:00")
    assert len(expiring) >= 1
    assert any(s.id == sub.id for s in expiring)


def test_get_nonexistent_subscription(db_for_test):
    db, _source = db_for_test
    assert db.get_websub_subscription_by_token("nonexistent-token") is None
    assert db.get_websub_subscription_for_source(999999) is None


# ---------------------------------------------------------------------------
# Hub challenge verification callback tests
# ---------------------------------------------------------------------------


def test_hub_challenge_verification(websub_app, monkeypatch):
    from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase

    async def override_user():
        return User(id=700, username="websub_test", email=None, is_active=True)

    websub_app.dependency_overrides[get_request_user] = override_user

    with TestClient(websub_app) as client:
        # First create a subscription record in DB
        db = WatchlistsDatabase.for_user(user_id=700)
        db.ensure_schema()
        source = db.create_source(
            name="Challenge Test Feed",
            url="https://example.com/challenge-feed.xml",
            source_type="rss",
        )
        sub = db.create_websub_subscription(
            source_id=source.id,
            hub_url="https://hub.example.com/",
            topic_url="https://example.com/challenge-feed.xml",
            callback_token="challenge-test-token",
            secret="challenge-test-secret",
        )

        # Mock the DB lookup to find our subscription
        with patch(
            "tldw_Server_API.app.api.v1.endpoints.collections_websub._lookup_subscription_by_token"
        ) as mock_lookup:
            mock_lookup.return_value = sub

            # GET callback with user_id in path + correct topic -> should echo challenge
            r = client.get(
                "/api/v1/websub/callback/700/challenge-test-token",
                params={
                    "hub.mode": "subscribe",
                    "hub.topic": "https://example.com/challenge-feed.xml",
                    "hub.challenge": "test-challenge-string",
                    "hub.lease_seconds": "86400",
                },
            )
            assert r.status_code == 200, r.text
            assert r.text == "test-challenge-string"


def test_hub_challenge_wrong_topic(websub_app, monkeypatch):
    from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WebSubRow

    async def override_user():
        return User(id=701, username="websub_test2", email=None, is_active=True)

    websub_app.dependency_overrides[get_request_user] = override_user

    with TestClient(websub_app) as client:
        mock_sub = WebSubRow(
            id=1, user_id="701", source_id=1,
            hub_url="https://hub.example.com/",
            topic_url="https://example.com/correct-topic.xml",
            callback_token="wrong-topic-token",
            secret="secret",
            state="pending",
            lease_seconds=None, verified_at=None, expires_at=None,
            last_push_at=None, created_at="2025-01-01", updated_at="2025-01-01",
        )

        with patch(
            "tldw_Server_API.app.api.v1.endpoints.collections_websub._lookup_subscription_by_token"
        ) as mock_lookup:
            mock_lookup.return_value = mock_sub

            r = client.get(
                "/api/v1/websub/callback/701/wrong-topic-token",
                params={
                    "hub.mode": "subscribe",
                    "hub.topic": "https://example.com/WRONG-topic.xml",
                    "hub.challenge": "challenge",
                },
            )
            assert r.status_code == 404


# ---------------------------------------------------------------------------
# Push notification callback tests
# ---------------------------------------------------------------------------


def test_push_notification_valid_signature(websub_app, monkeypatch):
    from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WebSubRow

    async def override_user():
        return User(id=702, username="websub_push", email=None, is_active=True)

    websub_app.dependency_overrides[get_request_user] = override_user

    secret = "push-test-secret"
    body = ATOM_PUSH_XML
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    mock_sub = WebSubRow(
        id=1, user_id="702", source_id=1,
        hub_url="https://hub.example.com/",
        topic_url="https://example.com/feed.xml",
        callback_token="push-valid-token",
        secret=secret,
        state="verified",
        lease_seconds=86400, verified_at="2025-01-01", expires_at="2025-01-11",
        last_push_at=None, created_at="2025-01-01", updated_at="2025-01-01",
    )

    with TestClient(websub_app) as client:
        with patch(
            "tldw_Server_API.app.api.v1.endpoints.collections_websub._lookup_subscription_by_token"
        ) as mock_lookup, patch(
            "tldw_Server_API.app.api.v1.endpoints.collections_websub._process_push_items"
        ) as mock_process, patch(
            "tldw_Server_API.app.core.DB_Management.Watchlists_DB.WatchlistsDatabase.update_websub_subscription"
        ):
            mock_lookup.return_value = mock_sub
            mock_process.return_value = 2

            r = client.post(
                "/api/v1/websub/callback/702/push-valid-token",
                content=body,
                headers={"X-Hub-Signature": f"sha256={digest}"},
            )
            assert r.status_code == 200
            # _process_push_items is called via _process_and_record_push background task;
            # TestClient runs background tasks synchronously before returning.
            mock_process.assert_called_once()


def test_push_notification_invalid_signature(websub_app, monkeypatch):
    from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WebSubRow

    mock_sub = WebSubRow(
        id=1, user_id="703", source_id=1,
        hub_url="https://hub.example.com/",
        topic_url="https://example.com/feed.xml",
        callback_token="push-invalid-token",
        secret="real-secret",
        state="verified",
        lease_seconds=86400, verified_at="2025-01-01", expires_at="2025-01-11",
        last_push_at=None, created_at="2025-01-01", updated_at="2025-01-01",
    )

    with TestClient(websub_app) as client:
        with patch(
            "tldw_Server_API.app.api.v1.endpoints.collections_websub._lookup_subscription_by_token"
        ) as mock_lookup:
            mock_lookup.return_value = mock_sub

            r = client.post(
                "/api/v1/websub/callback/703/push-invalid-token",
                content=b"<feed>fake</feed>",
                headers={"X-Hub-Signature": "sha256=totally_wrong_digest"},
            )
            assert r.status_code == 403


def test_push_notification_no_signature(websub_app, monkeypatch):
    from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WebSubRow

    mock_sub = WebSubRow(
        id=1, user_id="704", source_id=1,
        hub_url="https://hub.example.com/",
        topic_url="https://example.com/feed.xml",
        callback_token="push-nosig-token",
        secret="some-secret",
        state="verified",
        lease_seconds=86400, verified_at="2025-01-01", expires_at="2025-01-11",
        last_push_at=None, created_at="2025-01-01", updated_at="2025-01-01",
    )

    with TestClient(websub_app) as client:
        with patch(
            "tldw_Server_API.app.api.v1.endpoints.collections_websub._lookup_subscription_by_token"
        ) as mock_lookup:
            mock_lookup.return_value = mock_sub

            r = client.post(
                "/api/v1/websub/callback/704/push-nosig-token",
                content=b"<feed>data</feed>",
            )
            assert r.status_code == 403
