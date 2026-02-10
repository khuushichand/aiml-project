from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase
from tldw_Server_API.app.core.config import API_V1_PREFIX


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=919, username="wl-phase3", email=None, is_active=True)

    base_dir = tmp_path / "watchlists_phase3_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(
            id=920,
            username="wl-phase3-admin",
            email=None,
            role="user",
            roles=["admin"],
            permissions=["system.configure"],
            is_admin=False,
            is_active=True,
        )

    base_dir = tmp_path / "watchlists_phase3_dbs_admin"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("TEST_MODE", "0")
    monkeypatch.setenv("TLDW_TEST_MODE", "0")

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _seed_source(user_id: int, source_type: str = "rss") -> int:
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()
    unique = uuid4().hex
    source = db.create_source(
        name=f"Phase3 {source_type} Source {unique}",
        url=f"https://example.com/{source_type}/{unique}",
        source_type=source_type,
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )
    return int(source.id)


def _seed_job_run_item(user_id: int) -> dict[str, int | str]:
    db = WatchlistsDatabase.for_user(user_id)
    db.ensure_schema()
    unique = uuid4().hex
    source = db.create_source(
        name=f"Phase3 Job Source {unique}",
        url=f"https://example.com/jobs/{unique}",
        source_type="rss",
        active=True,
        settings_json=None,
        tags=[],
        group_ids=[],
    )
    job = db.create_job(
        name=f"Phase3 Job {unique}",
        description="cross-user read test",
        scope_json=json.dumps({"sources": [int(source.id)]}),
        schedule_expr=None,
        schedule_timezone="UTC",
        active=True,
        max_concurrency=1,
        per_host_delay_ms=0,
        retry_policy_json=json.dumps({}),
        output_prefs_json=json.dumps({}),
        job_filters_json=None,
    )
    run = db.create_run(int(job.id), status="finished")

    user_dir = DatabasePaths.get_user_base_directory(user_id)
    log_rel_path = f"logs/watchlists/{int(run.id)}.log"
    log_path = user_dir / log_rel_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"phase3-run-log-{unique}", encoding="utf-8")
    db.update_run(
        int(run.id),
        status="finished",
        stats_json=json.dumps({"items_found": 1, "items_ingested": 1}),
        log_path=log_rel_path,
    )

    item = db.record_scraped_item(
        run_id=int(run.id),
        job_id=int(job.id),
        source_id=int(source.id),
        media_id=None,
        media_uuid=None,
        url=f"https://example.com/items/{unique}",
        title=f"Phase3 Item {unique}",
        summary="phase3",
        published_at=None,
        tags=["phase3"],
        status="ingested",
    )

    return {
        "source_id": int(source.id),
        "job_id": int(job.id),
        "run_id": int(run.id),
        "item_id": int(item.id),
        "log_path": log_rel_path,
    }


def test_settings_exposes_phase3_capabilities(client_with_user, monkeypatch):
    monkeypatch.delenv("WATCHLIST_SHARING_MODE", raising=False)
    r = client_with_user.get("/api/v1/watchlists/settings")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert "default_output_ttl_seconds" in payload
    assert "temporary_output_ttl_seconds" in payload
    assert payload.get("sharing_mode") == "admin_cross_user"
    assert payload.get("watchlists_backend") in {"sqlite", "postgres"}
    assert isinstance(payload.get("forum_default_top_n"), int)
    assert isinstance(payload.get("forums_enabled"), bool)


def test_settings_forums_enabled_reflects_env(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_FORUMS_ENABLED", "1")
    r = client_with_user.get("/api/v1/watchlists/settings")
    assert r.status_code == 200, r.text
    assert r.json().get("forums_enabled") is True


def test_settings_forum_default_top_n_reflects_env(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_FORUM_DEFAULT_TOP_N", "35")
    r = client_with_user.get("/api/v1/watchlists/settings")
    assert r.status_code == 200, r.text
    assert r.json().get("forum_default_top_n") == 35


def test_settings_sharing_mode_reflects_env(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "private_only")
    r = client_with_user.get("/api/v1/watchlists/settings")
    assert r.status_code == 200, r.text
    assert r.json().get("sharing_mode") == "private_only"


def test_settings_sharing_mode_admin_same_org_reflects_env(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_same_org")
    r = client_with_user.get("/api/v1/watchlists/settings")
    assert r.status_code == 200, r.text
    assert r.json().get("sharing_mode") == "admin_same_org"


def test_forum_source_test_uses_forum_default_top_n(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_FORUMS_ENABLED", "1")
    monkeypatch.setenv("WATCHLIST_FORUM_DEFAULT_TOP_N", "20")

    calls: list[tuple[str, int, str]] = []

    async def _fake_fetch_site_top_links(url: str, *, top_n: int = 1, method: str = "auto"):
        calls.append((url, top_n, method))
        return [f"{url.rstrip('/')}/topic-{idx}" for idx in range(1, 4)]

    from tldw_Server_API.app.core.Watchlists import fetchers as watchlist_fetchers

    monkeypatch.setattr(watchlist_fetchers, "fetch_site_top_links", _fake_fetch_site_top_links)

    created = client_with_user.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Forum Source",
            "url": "https://forum.example.com/",
            "source_type": "forum",
            "settings": {},
        },
    )
    assert created.status_code == 200, created.text
    source_id = created.json()["id"]

    preview = client_with_user.post(f"/api/v1/watchlists/sources/{source_id}/test", params={"limit": 10})
    assert preview.status_code == 200, preview.text
    assert calls, "expected fetch_site_top_links to be called"
    _url, top_n, _method = calls[0]
    assert top_n == 20
    assert preview.json().get("total", 0) >= 1


def test_forum_source_test_honors_forum_top_n_override(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_FORUMS_ENABLED", "1")
    monkeypatch.setenv("WATCHLIST_FORUM_DEFAULT_TOP_N", "31")

    calls: list[tuple[str, int, str]] = []

    async def _fake_fetch_site_top_links(url: str, *, top_n: int = 1, method: str = "auto"):
        calls.append((url, top_n, method))
        return [f"{url.rstrip('/')}/topic-{idx}" for idx in range(1, 3)]

    from tldw_Server_API.app.core.Watchlists import fetchers as watchlist_fetchers

    monkeypatch.setattr(watchlist_fetchers, "fetch_site_top_links", _fake_fetch_site_top_links)

    source_id = _seed_source(919, source_type="forum")
    preview = client_with_user.post(f"/api/v1/watchlists/sources/{source_id}/test", params={"limit": 5})
    assert preview.status_code == 200, preview.text
    assert calls
    assert calls[0][1] == 31


def test_private_only_sharing_blocks_admin_cross_user_seen(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "private_only")
    target_user_id = 927
    source_id = _seed_source(target_user_id)

    r = admin_client_with_user.get(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 403
    assert "watchlists_private_only_mode" in r.text


def test_admin_cross_user_sharing_allows_admin_seen_access(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_cross_user")
    target_user_id = 928
    source_id = _seed_source(target_user_id)

    r = admin_client_with_user.get(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 200, r.text


def test_admin_same_org_blocks_cross_user_without_overlap(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_same_org")

    async def _fake_org_memberships(user_id: int):
        if int(user_id) == 920:
            return [{"org_id": 10, "role": "owner"}]
        if int(user_id) == 929:
            return [{"org_id": 20, "role": "member"}]
        return []

    from tldw_Server_API.app.core.AuthNZ import orgs_teams as orgs_teams_module

    monkeypatch.setattr(orgs_teams_module, "list_org_memberships_for_user", _fake_org_memberships)

    target_user_id = 929
    source_id = _seed_source(target_user_id)
    r = admin_client_with_user.get(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 403
    assert "watchlists_admin_same_org_required" in r.text


def test_admin_same_org_allows_cross_user_with_overlap(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_same_org")

    async def _fake_org_memberships(user_id: int):
        if int(user_id) == 920:
            return [{"org_id": 10, "role": "owner"}, {"org_id": 30, "role": "admin"}]
        if int(user_id) == 930:
            return [{"org_id": 30, "role": "member"}]
        return []

    from tldw_Server_API.app.core.AuthNZ import orgs_teams as orgs_teams_module

    monkeypatch.setattr(orgs_teams_module, "list_org_memberships_for_user", _fake_org_memberships)

    target_user_id = 930
    source_id = _seed_source(target_user_id)
    r = admin_client_with_user.get(
        f"/api/v1/watchlists/sources/{source_id}/seen",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 200, r.text


def test_non_admin_target_user_blocks_jobs_list(client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_cross_user")
    target_user_id = 931
    _seed_job_run_item(target_user_id)

    r = client_with_user.get(
        "/api/v1/watchlists/jobs",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 403
    assert "watchlists_admin_required_for_target_user" in r.text


def test_private_only_sharing_blocks_admin_cross_user_jobs_list(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "private_only")
    target_user_id = 932
    _seed_job_run_item(target_user_id)

    r = admin_client_with_user.get(
        "/api/v1/watchlists/jobs",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 403
    assert "watchlists_private_only_mode" in r.text


def test_admin_same_org_blocks_jobs_reads_without_overlap(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_same_org")

    async def _fake_org_memberships(user_id: int):
        if int(user_id) == 920:
            return [{"org_id": 100, "role": "owner"}]
        if int(user_id) == 933:
            return [{"org_id": 200, "role": "member"}]
        return []

    from tldw_Server_API.app.core.AuthNZ import orgs_teams as orgs_teams_module

    monkeypatch.setattr(orgs_teams_module, "list_org_memberships_for_user", _fake_org_memberships)

    target_user_id = 933
    _seed_job_run_item(target_user_id)
    r = admin_client_with_user.get(
        "/api/v1/watchlists/jobs",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 403
    assert "watchlists_admin_same_org_required" in r.text


def test_admin_cross_user_reads_target_jobs_runs_and_items(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_cross_user")
    target_user_id = 934
    seeded = _seed_job_run_item(target_user_id)

    jobs_resp = admin_client_with_user.get(
        "/api/v1/watchlists/jobs",
        params={"target_user_id": target_user_id},
    )
    assert jobs_resp.status_code == 200, jobs_resp.text
    job_ids = [int(row["id"]) for row in jobs_resp.json().get("items", [])]
    assert seeded["job_id"] in job_ids

    details_resp = admin_client_with_user.get(
        f"/api/v1/watchlists/runs/{seeded['run_id']}/details",
        params={"target_user_id": target_user_id},
    )
    assert details_resp.status_code == 200, details_resp.text
    detail_payload = details_resp.json()
    assert detail_payload.get("job_id") == seeded["job_id"]
    assert detail_payload.get("log_path") == seeded["log_path"]

    items_resp = admin_client_with_user.get(
        "/api/v1/watchlists/items",
        params={"target_user_id": target_user_id, "run_id": seeded["run_id"]},
    )
    assert items_resp.status_code == 200, items_resp.text
    item_ids = [int(row["id"]) for row in items_resp.json().get("items", [])]
    assert seeded["item_id"] in item_ids


def test_admin_same_org_allows_jobs_reads_with_overlap(admin_client_with_user, monkeypatch):
    monkeypatch.setenv("WATCHLIST_SHARING_MODE", "admin_same_org")

    async def _fake_org_memberships(user_id: int):
        if int(user_id) == 920:
            return [{"org_id": 300, "role": "owner"}]
        if int(user_id) == 935:
            return [{"org_id": 300, "role": "member"}]
        return []

    from tldw_Server_API.app.core.AuthNZ import orgs_teams as orgs_teams_module

    monkeypatch.setattr(orgs_teams_module, "list_org_memberships_for_user", _fake_org_memberships)

    target_user_id = 935
    seeded = _seed_job_run_item(target_user_id)
    r = admin_client_with_user.get(
        "/api/v1/watchlists/jobs",
        params={"target_user_id": target_user_id},
    )
    assert r.status_code == 200, r.text
    job_ids = [int(row["id"]) for row in r.json().get("items", [])]
    assert seeded["job_id"] in job_ids
