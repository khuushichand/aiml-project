import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from importlib import import_module

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=555, username="wluser", email=None, is_active=True)

    # Route user DB base dir into project Databases to avoid permission issues
    base_dir = Path.cwd() / "Databases" / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_sources_crud_and_tags(client_with_user):
    c = client_with_user

    # Create source with tags
    body = {
        "name": "Example RSS",
        "url": "https://example.com/feed.xml",
        "source_type": "rss",
        "tags": ["News", "Tech"],
        "settings": {"top_n": 10},
    }
    r = c.post("/api/v1/watchlists/sources", json=body)
    assert r.status_code == 200, r.text
    src = r.json()
    sid = src["id"]
    assert set(src.get("tags", [])) == {"news", "tech"}

    # List sources filtered by tag
    r = c.get("/api/v1/watchlists/sources", params={"tags": ["tech"]})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert any(it["id"] == sid for it in data["items"])

    # Get source
    r = c.get(f"/api/v1/watchlists/sources/{sid}")
    assert r.status_code == 200

    # Update source: replace tags
    r = c.patch(f"/api/v1/watchlists/sources/{sid}", json={"tags": ["updates", "tech"]})
    assert r.status_code == 200
    up = r.json()
    assert set(up.get("tags", [])) == {"updates", "tech"}

    # Tags list
    r = c.get("/api/v1/watchlists/tags")
    assert r.status_code == 200
    tags = r.json().get("items", [])
    names = {t["name"] for t in tags}
    assert {"news", "tech", "updates"}.issubset(names)

    # Delete source
    r = c.delete(f"/api/v1/watchlists/sources/{sid}")
    assert r.status_code == 200
    r = c.get(f"/api/v1/watchlists/sources/{sid}")
    assert r.status_code == 404


def test_bulk_sources_and_groups_and_jobs(client_with_user):
    c = client_with_user

    # Bulk create two sources
    payload = {
        "sources": [
            {"name": "Site A", "url": "https://a.example.com/", "source_type": "site", "tags": ["alpha"]},
            {"name": "RSS B", "url": "https://b.example.com/feed", "source_type": "rss", "tags": ["beta"]},
        ]
    }
    r = c.post("/api/v1/watchlists/sources/bulk", json=payload)
    assert r.status_code == 200, r.text
    lst = r.json()
    assert lst["total"] == 2

    # Groups
    r = c.post("/api/v1/watchlists/groups", json={"name": "Top", "description": "Root"})
    assert r.status_code == 200
    g = r.json()
    gid = g["id"]
    r = c.get("/api/v1/watchlists/groups")
    assert r.status_code == 200
    assert any(x["id"] == gid for x in r.json().get("items", []))
    r = c.patch(f"/api/v1/watchlists/groups/{gid}", json={"description": "Updated"})
    assert r.status_code == 200
    assert r.json()["description"] == "Updated"

    # Jobs
    job_body = {
        "name": "Morning Brief",
        "scope": {"tags": ["alpha", "beta"]},
        "schedule_expr": "0 8 * * *",
        "timezone": "UTC+8",
        "active": True,
    }
    r = c.post("/api/v1/watchlists/jobs", json=job_body)
    assert r.status_code == 200, r.text
    job = r.json()
    jid = job["id"]
    r = c.get("/api/v1/watchlists/jobs")
    assert r.status_code == 200
    assert any(x["id"] == jid for x in r.json().get("items", []))
    r = c.get(f"/api/v1/watchlists/jobs/{jid}")
    assert r.status_code == 200
    # Update job
    r = c.patch(f"/api/v1/watchlists/jobs/{jid}", json={"active": False})
    assert r.status_code == 200
    assert r.json()["active"] is False

    # Trigger run (stub)
    r = c.post(f"/api/v1/watchlists/jobs/{jid}/run")
    assert r.status_code == 200
    run = r.json()
    rid = run["id"]
    r = c.get(f"/api/v1/watchlists/jobs/{jid}/runs")
    assert r.status_code == 200
    assert any(x["id"] == rid for x in r.json().get("items", []))
    r = c.get(f"/api/v1/watchlists/runs/{rid}")
    assert r.status_code == 200

