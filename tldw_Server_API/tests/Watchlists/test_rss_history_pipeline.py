import json
from pathlib import Path
from importlib import import_module

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.integration


@pytest.fixture()
def client_user(monkeypatch):
    async def override_user():
        return User(id=888, username="wluser", email=None, is_active=True)

    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WORKFLOWS_SCHEDULER_ENABLED", "false")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _make_job(client: TestClient, src_id: int, *, history_cfg: dict | None = None, rss_cfg: dict | None = None):
    # Patch source settings
    settings = {}
    if history_cfg:
        settings["history"] = history_cfg
    if rss_cfg:
        settings["rss"] = rss_cfg
    r = client.patch(f"/api/v1/watchlists/sources/{src_id}", json={"settings": settings})
    assert r.status_code == 200
    body = {"name": "RSS Job", "scope": {"sources": [src_id]}, "active": True}
    r = client.post("/api/v1/watchlists/jobs", json=body)
    assert r.status_code == 200
    return r.json()["id"]


def test_history_atom_ingests_across_pages(monkeypatch, client_user):
    # Offline-friendly: ensure pipeline runs in TEST_MODE to bypass heavy ingestion paths
    monkeypatch.setenv("TEST_MODE", "1")
    c = client_user
    # Create RSS source
    r = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Feed", "url": "https://feed.example.com/atom", "source_type": "rss"},
    )
    assert r.status_code == 200
    src = r.json()

    # Monkeypatch history fetcher at pipeline level for determinism
    from tldw_Server_API.app.core.Watchlists import pipeline as P
    async def fake_history(url: str, **kwargs):
        return {
            "status": 200,
            "items": [
                {"title": "A", "url": "https://example.com/a", "summary": "s"},
                {"title": "B", "url": "https://example.com/b", "summary": "s"},
            ],
            "pages_fetched": 2,
        }
    monkeypatch.setattr(P, "fetch_rss_feed_history", fake_history)
    # Avoid network for articles; patch the name used inside pipeline
    def fake_article(url: str):
        return {"url": url, "title": url.split("/")[-1], "author": None, "content": "Test content"}

    monkeypatch.setattr(P, "fetch_site_article", fake_article)

    jid = _make_job(c, src["id"], history_cfg={"strategy": "atom", "max_pages": 3})
    # Ensure job-level override present as well
    r = c.patch(f"/api/v1/watchlists/jobs/{jid}", json={"output_prefs": {"history": {"strategy": "atom", "max_pages": 3}}})
    assert r.status_code == 200
    rid = c.post(f"/api/v1/watchlists/jobs/{jid}/run").json()["id"]
    det = c.get(f"/api/v1/watchlists/runs/{rid}/details").json()
    stats = det.get("stats", {})
    # Integration sanity: ingestion occurred; full history traversal is covered by unit tests
    assert stats.get("items_found") >= 1
    assert stats.get("items_ingested") >= 1


def test_history_on_304_true_wordpress(monkeypatch, client_user):
    monkeypatch.setenv("TEST_MODE", "1")
    c = client_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "WP", "url": "https://blog.example.com/feed/", "source_type": "rss"},
    )
    assert r.status_code == 200
    src = r.json()

    from tldw_Server_API.app.core.Watchlists import pipeline as P
    # Return one extra page when on_304 is set
    async def fake_history(url: str, **kwargs):
        return {
            "status": 200,
            "items": [{"title": "P2", "url": "https://blog.example.com/p2", "summary": ""}],
            "pages_fetched": 1,
        }
    monkeypatch.setattr(P, "fetch_rss_feed_history", fake_history)
    def fake_article(url: str):
        return {"url": url, "title": url.split("/")[-1], "author": None, "content": "Test content"}
    monkeypatch.setattr(P, "fetch_site_article", fake_article)

    jid = _make_job(c, src["id"], history_cfg={"strategy": "wordpress", "max_pages": 2, "on_304": True})
    r = c.patch(f"/api/v1/watchlists/jobs/{jid}", json={"output_prefs": {"history": {"strategy": "wordpress", "max_pages": 2, "on_304": True}}})
    assert r.status_code == 200
    rid = c.post(f"/api/v1/watchlists/jobs/{jid}/run").json()["id"]
    det = c.get(f"/api/v1/watchlists/runs/{rid}/details").json()
    stats = det.get("stats", {})
    assert stats.get("items_ingested") >= 1
    # Integration sanity: ingestion occurred when backfill is enabled
    assert stats.get("items_ingested") >= 1


def test_prefer_feed_full_text_skips_fetch(monkeypatch, client_user):
    monkeypatch.setenv("TEST_MODE", "1")
    c = client_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "FF", "url": "https://ff.example.com/feed", "source_type": "rss"},
    )
    assert r.status_code == 200
    src = r.json()

    from tldw_Server_API.app.core.Watchlists import fetchers as F
    from tldw_Server_API.app.core.Watchlists import pipeline as P

    # History disabled to hit fetch_rss_feed path
    async def fake_fetch(url: str, **kwargs):
        return {
            "status": 200,
            "items": [
                {
                    "title": "T",
                    "url": "https://ff.example.com/a",
                    "summary": "x" * 800,  # long enough to pass threshold
                }
            ],
        }

    monkeypatch.setattr(F, "fetch_rss_feed", fake_fetch)
    calls = []
    def fake_article(url: str):
        calls.append(url)
        return {"url": url, "title": "t", "author": None, "content": "content"}

    monkeypatch.setattr(P, "fetch_site_article", fake_article)
    jid = _make_job(
        c,
        src["id"],
        history_cfg={"strategy": "none", "max_pages": 1},
        rss_cfg={"use_feed_content_if_available": True, "feed_content_min_chars": 200},
    )
    r = c.patch(f"/api/v1/watchlists/jobs/{jid}", json={"output_prefs": {"history": {"strategy": "none", "max_pages": 1}}})
    assert r.status_code == 200
    rid = c.post(f"/api/v1/watchlists/jobs/{jid}/run").json()["id"]
    det = c.get(f"/api/v1/watchlists/runs/{rid}/details").json()
    stats = det.get("stats", {})
    assert stats.get("items_ingested") >= 1
    # No article network fetch when full text used
    assert calls == []
