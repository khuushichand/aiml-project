import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from importlib import import_module

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths


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


def test_items_and_outputs_flow(client_with_user, monkeypatch):
    c = client_with_user
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("WATCHLIST_OUTPUT_DEFAULT_TTL_SECONDS", "0")
    monkeypatch.setenv("WATCHLIST_OUTPUT_TEMP_TTL_SECONDS", "90")

    # Create RSS source
    src_body = {
        "name": "Daily Feed",
        "url": "https://example.com/feed.xml",
        "source_type": "rss",
        "tags": ["daily"],
    }
    r = c.post("/api/v1/watchlists/sources", json=src_body)
    assert r.status_code == 200, r.text
    source_id = r.json()["id"]

    # Job covering tag
    job_body = {
        "name": "Daily Digest",
        "scope": {"tags": ["daily"]},
        "schedule_expr": None,
        "timezone": "UTC",
        "active": True,
    }
    r = c.post("/api/v1/watchlists/jobs", json=job_body)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    # Trigger run
    r = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert r.status_code == 200, r.text
    run = r.json()
    run_id = run["id"]

    # List items
    r = c.get("/api/v1/watchlists/items", params={"run_id": run_id})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    first_item = data["items"][0]
    item_id = first_item["id"]
    assert first_item["status"] in {"ingested", "error", "duplicate"}

    # Mark reviewed
    r = c.patch(f"/api/v1/watchlists/items/{item_id}", json={"reviewed": True})
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["reviewed"] is True

    # Filter reviewed items
    r = c.get("/api/v1/watchlists/items", params={"run_id": run_id, "reviewed": True})
    assert r.status_code == 200, r.text
    filt = r.json()
    assert any(it["id"] == item_id for it in filt["items"])

    # Generate output
    out_payload = {
        "run_id": run_id,
        "title": "Daily Briefing",
        "format": "md",
        "retention_seconds": 3600,
    }
    r = c.post("/api/v1/watchlists/outputs", json=out_payload)
    assert r.status_code == 200, r.text
    output = r.json()
    output_id = output["id"]
    assert "Daily Briefing" in (output.get("content") or "")
    assert output["version"] == 1
    assert output["expires_at"] is not None
    expires_at = datetime.fromisoformat(output["expires_at"])
    assert expires_at > datetime.now(timezone.utc)

    # Generate a temporary output without specifying title to trigger default naming
    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "temporary": True})
    assert r.status_code == 200, r.text
    temp_output = r.json()
    assert temp_output["version"] == 2
    assert temp_output["title"].startswith("Daily Digest-Output-2")
    assert temp_output["expires_at"] is not None

    # Outputs listing (should include both)
    r = c.get("/api/v1/watchlists/outputs", params={"run_id": run_id})
    assert r.status_code == 200, r.text
    outputs = r.json()
    assert outputs["total"] >= 2
    assert any(o["id"] == output_id for o in outputs["items"])

    # Output metadata
    r = c.get(f"/api/v1/watchlists/outputs/{output_id}")
    assert r.status_code == 200, r.text
    meta = r.json()
    assert meta["version"] == 1

    # Download output
    r = c.get(f"/api/v1/watchlists/outputs/{output_id}/download")
    assert r.status_code == 200, r.text
    assert "Daily Briefing" in r.text

    # Template management
    template_payload = {
        "name": "daily_md",
        "format": "md",
        "content": "{{ title }}\\n{% for item in items %}- {{ loop.index }}. {{ item.title }}{% endfor %}",
        "description": "Markdown summary template",
    }
    r = c.post("/api/v1/watchlists/templates", json=template_payload)
    assert r.status_code == 200, r.text
    # Duplicate without overwrite should fail
    r = c.post("/api/v1/watchlists/templates", json=template_payload)
    assert r.status_code == 409

    # List templates
    r = c.get("/api/v1/watchlists/templates")
    assert r.status_code == 200
    templates = r.json()["items"]
    assert any(t["name"] == "daily_md" for t in templates)

    # Get template detail
    r = c.get("/api/v1/watchlists/templates/daily_md")
    assert r.status_code == 200
    template_detail = r.json()
    assert "Markdown summary template" in template_detail["description"]

    # Generate output using stored template
    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "template_name": "daily_md", "temporary": True})
    assert r.status_code == 200, r.text
    templated = r.json()
    assert templated["version"] == 3
    assert templated["format"] == "md"
    assert templated["metadata"].get("template_name") == "daily_md"
    assert templated["content"].startswith("Daily Digest-Output-3") or "Daily Digest" in templated["content"]

    # Delete template and confirm removal
    r = c.delete("/api/v1/watchlists/templates/daily_md")
    assert r.status_code == 200
    r = c.get("/api/v1/watchlists/templates/daily_md")
    assert r.status_code == 404
    r = c.get("/api/v1/watchlists/templates")
    assert all(t["name"] != "daily_md" for t in r.json().get("items", []))


def test_output_deliveries_email_and_chatbook(client_with_user, monkeypatch, tmp_path):
    c = client_with_user
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("EMAIL_PROVIDER", "mock")

    src_body = {
        "name": "Daily Feed",
        "url": "https://example.com/feed.xml",
        "source_type": "rss",
        "tags": ["daily"],
    }
    r = c.post("/api/v1/watchlists/sources", json=src_body)
    assert r.status_code == 200, r.text

    job_body = {
        "name": "Daily Digest",
        "scope": {"tags": ["daily"]},
        "output_prefs": {
            "retention": {"default_seconds": 7200, "temporary_seconds": 600},
            "deliveries": {
                "email": {"recipients": ["digest@example.com"], "attach_file": False},
                "chatbook": {"enabled": True, "metadata": {"category": "digest"}},
            },
        },
    }
    r = c.post("/api/v1/watchlists/jobs", json=job_body)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    r = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert r.status_code == 200, r.text
    run_id = r.json()["id"]

    payload = {
        "run_id": run_id,
        "title": "Digest",
        "deliveries": {
            "email": {"subject": "Daily Digest", "recipients": ["alt@example.com"], "attach_file": True},
            "chatbook": {"title": "Digest Document", "description": "Auto", "metadata": {"origin": "test"}},
        },
    }
    r = c.post("/api/v1/watchlists/outputs", json=payload)
    assert r.status_code == 200, r.text
    output = r.json()

    deliveries = output.get("metadata", {}).get("deliveries", [])
    assert len(deliveries) == 2
    channels = {d["channel"] for d in deliveries}
    assert {"email", "chatbook"} == channels
    email_result = next(d for d in deliveries if d["channel"] == "email")
    assert email_result["status"] in {"sent", "partial"}
    chat_result = next(d for d in deliveries if d["channel"] == "chatbook")
    assert chat_result["status"] in {"stored", "failed"}

    chatbook_id = output.get("metadata", {}).get("chatbook_document_id")
    if chat_result["status"] == "stored":
        assert isinstance(chatbook_id, int)
        assert output.get("chatbook_path") == f"generated_document:{chatbook_id}"

        db_path = DatabasePaths.get_chacha_db_path(555)
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT metadata FROM generated_documents WHERE id = ?", (chatbook_id,)).fetchone()
            assert row is not None
            stored_meta = json.loads(row[0])
            assert stored_meta.get("job_id") == job_id
            assert stored_meta.get("run_id") == run_id
            assert stored_meta.get("origin") == "test"
