from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase


pytestmark = pytest.mark.unit


def _seed_source_with_seen(user_id: int, *, key_prefix: str = "seen") -> int:
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()
    unique = uuid4().hex
    src = db.create_source(
        name=f"Source-{user_id}-{unique}",
        url=f"https://example.com/{user_id}/feed-{unique}.xml",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )
    db.mark_seen_item(src.id, f"{key_prefix}-1")
    db.mark_seen_item(src.id, f"{key_prefix}-2")
    db.update_source_scrape_meta(
        src.id,
        defer_until=datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        status="not_modified_backoff:60",
        consec_not_modified=4,
    )
    return int(src.id)


@pytest.fixture()
def user_client(monkeypatch):
    async def override_user():
        return User(id=9101, username="watch-user", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_seen_tools"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_client(monkeypatch):
    async def override_user():
        u = User(id=9199, username="watch-admin", email=None, is_active=True)
        setattr(u, "is_admin", True)
        return u

    base_dir = Path.cwd() / "Databases" / "test_user_dbs_seen_tools"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_seen_stats_and_reset_for_current_user(user_client):
    source_id = _seed_source_with_seen(user_id=9101, key_prefix="self")

    r = user_client.get(f"/api/v1/watchlists/sources/{source_id}/seen", params={"keys_limit": 2})
    assert r.status_code == 200, r.text
    stats = r.json()
    assert stats["user_id"] == 9101
    assert stats["seen_count"] == 2
    assert len(stats["recent_keys"]) == 2
    assert stats["defer_until"] is not None
    assert stats["consec_not_modified"] == 4

    r = user_client.delete(f"/api/v1/watchlists/sources/{source_id}/seen")
    assert r.status_code == 200, r.text
    cleared = r.json()
    assert cleared["source_id"] == source_id
    assert cleared["user_id"] == 9101
    assert cleared["cleared"] == 2
    assert cleared["cleared_backoff"] is True

    r = user_client.get(f"/api/v1/watchlists/sources/{source_id}/seen")
    assert r.status_code == 200, r.text
    stats_after = r.json()
    assert stats_after["seen_count"] == 0
    assert stats_after["defer_until"] is None
    assert stats_after["consec_not_modified"] == 0


def test_seen_target_user_requires_admin(user_client):
    target_user_id = 9102
    source_id = _seed_source_with_seen(user_id=target_user_id, key_prefix="target")

    r = user_client.get(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 403
    assert "watchlists_admin_required_for_target_user" in r.text


def test_admin_can_inspect_and_reset_seen_for_target_user(admin_client):
    target_user_id = 9103
    source_id = _seed_source_with_seen(user_id=target_user_id, key_prefix="admin")

    r = admin_client.get(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id, "keys_limit": 1},
    )
    assert r.status_code == 200, r.text
    stats = r.json()
    assert stats["user_id"] == target_user_id
    assert stats["seen_count"] == 2
    assert len(stats["recent_keys"]) == 1

    r = admin_client.delete(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id, "clear_backoff": True},
    )
    assert r.status_code == 200, r.text
    reset = r.json()
    assert reset["user_id"] == target_user_id
    assert reset["cleared"] == 2
    assert reset["cleared_backoff"] is True

    db = WatchlistsDatabase.for_user(target_user_id)
    post_stats = db.get_seen_item_stats(source_id)
    assert int(post_stats["seen_count"]) == 0
    src = db.get_source(source_id)
    assert src.defer_until is None
    assert src.consec_not_modified == 0
