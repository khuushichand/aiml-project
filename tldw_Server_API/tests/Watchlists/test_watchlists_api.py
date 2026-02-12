import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from importlib import import_module

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.Collections_DB import CollectionsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase


pytestmark = pytest.mark.unit


@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=555, username="wluser", email=None, is_active=True)

    # Route user DB base dir into an isolated temp directory per test.
    base_dir = tmp_path / "test_user_dbs"
    base_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    # Keep this suite focused on watchlists API behavior; seeding behavior is covered separately.
    monkeypatch.setenv("WATCHLISTS_SEED_OUTPUT_TEMPLATES", "false")

    mod = import_module("tldw_Server_API.app.main")
    app = getattr(mod, "app")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_sources_crud_and_tags(client_with_user):


    c = client_with_user

    # Create groups for source membership updates
    r = c.post("/api/v1/watchlists/groups", json={"name": "Group A", "description": "A"})
    assert r.status_code == 200, r.text
    group_a = r.json()
    r = c.post("/api/v1/watchlists/groups", json={"name": "Group B", "description": "B"})
    assert r.status_code == 200, r.text
    group_b = r.json()

    # Create source with tags
    body = {
        "name": "Example RSS",
        "url": "https://example.com/feed.xml",
        "source_type": "rss",
        "tags": ["News", "Tech"],
        "settings": {"top_n": 10},
        "group_ids": [group_a["id"]],
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

    # Update source: replace group membership
    r = c.patch(f"/api/v1/watchlists/sources/{sid}", json={"group_ids": [group_b["id"]]})
    assert r.status_code == 200
    db = WatchlistsDatabase.for_user(555)
    in_group_b = db.list_sources_by_group_ids([int(group_b["id"])])
    assert any(src.id == sid for src in in_group_b)
    in_group_a = db.list_sources_by_group_ids([int(group_a["id"])])
    assert not any(src.id == sid for src in in_group_a)

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


def test_sources_test_endpoint(client_with_user, monkeypatch):

    monkeypatch.setenv("TEST_MODE", "1")
    c = client_with_user
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Example Site",
            "url": "https://example.com/",
            "source_type": "site",
            "settings": {
                "scrape_rules": {
                    "list_url": "https://example.com/",
                    "limit": 3,
                }
            },
        },
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    r = c.post(f"/api/v1/watchlists/sources/{sid}/test", params={"limit": 2})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    assert data["ingestable"] == data["total"]
    assert data["filtered"] == 0
    assert all(it["source_id"] == sid for it in data["items"])


def test_source_group_validation_and_idempotent_create(client_with_user):


    c = client_with_user

    r = c.post("/api/v1/watchlists/groups", json={"name": "Group C", "description": "C"})
    assert r.status_code == 200, r.text
    group_c = r.json()
    r = c.post("/api/v1/watchlists/groups", json={"name": "Group D", "description": "D"})
    assert r.status_code == 200, r.text
    group_d = r.json()

    # Invalid group id on create should fail
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Bad Group Source",
            "url": "https://example.com/invalid-group.xml",
            "source_type": "rss",
            "group_ids": [999999],
        },
    )
    assert r.status_code == 400
    assert "group_not_found" in r.text

    # Create source in Group C
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Group Source",
            "url": "https://example.com/group-source.xml",
            "source_type": "rss",
            "group_ids": [group_c["id"]],
        },
    )
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    # Idempotent create should replace group membership when group_ids provided
    r = c.post(
        "/api/v1/watchlists/sources",
        json={
            "name": "Group Source",
            "url": "https://example.com/group-source.xml",
            "source_type": "rss",
            "group_ids": [group_d["id"]],
        },
    )
    assert r.status_code == 200, r.text

    db = WatchlistsDatabase.for_user(555)
    in_group_d = db.list_sources_by_group_ids([int(group_d["id"])])
    assert any(src.id == sid for src in in_group_d)
    in_group_c = db.list_sources_by_group_ids([int(group_c["id"])])
    assert not any(src.id == sid for src in in_group_c)

    # Invalid group id on update should fail
    r = c.patch(f"/api/v1/watchlists/sources/{sid}", json={"group_ids": [999998]})
    assert r.status_code == 400
    assert "group_not_found" in r.text


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
        "timezone": "UTC",
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


def test_forum_sources_feature_flag(client_with_user, monkeypatch):
    c = client_with_user

    monkeypatch.delenv("WATCHLIST_FORUMS_ENABLED", raising=False)
    r = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Forum Source", "url": "https://forum.example.com/", "source_type": "forum"},
    )
    assert r.status_code == 400
    assert "forum_sources_disabled" in r.text

    monkeypatch.setenv("WATCHLIST_FORUMS_ENABLED", "1")
    r = c.post(
        "/api/v1/watchlists/sources",
        json={"name": "Forum Source", "url": "https://forum.example.com/", "source_type": "forum"},
    )
    assert r.status_code == 200, r.text


def test_watchlists_run_stream_ws(client_with_user, tmp_path):
    from tldw_Server_API.app.core.AuthNZ.jwt_service import create_access_token

    db = WatchlistsDatabase.for_user(555)
    job = db.create_job(
        name="Job",
        description=None,
        scope_json=json.dumps({"sources": []}),
        schedule_expr=None,
        schedule_timezone=None,
        active=True,
        max_concurrency=None,
        per_host_delay_ms=None,
        retry_policy_json=None,
        output_prefs_json=None,
    )
    run = db.create_run(job_id=job.id, status="running")
    log_path = tmp_path / "run.log"
    log_path.write_text("first line\n", encoding="utf-8")
    db.update_run(run.id, stats_json=json.dumps({"items_found": 1}), log_path=str(log_path))

    token = create_access_token(555, "wluser", "admin")
    with client_with_user.websocket_connect(f"/api/v1/watchlists/runs/{run.id}/stream?token={token}") as ws:
        message = ws.receive_json()
        assert message["type"] == "snapshot"
        assert message["run"]["id"] == run.id
        assert "log_tail" in message


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

    # Generate output with no expiry (retention_seconds=0)
    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "retention_seconds": 0})
    assert r.status_code == 200, r.text
    no_expiry = r.json()
    assert no_expiry["version"] == 2
    assert no_expiry["expires_at"] is None

    # Generate a temporary output without specifying title to trigger default naming
    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "temporary": True})
    assert r.status_code == 200, r.text
    temp_output = r.json()
    assert temp_output["version"] == 3
    assert temp_output["title"].startswith("Daily Digest-Output-3")
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

    # Output templates (DB-backed)
    unique_suffix = uuid.uuid4().hex[:8]
    db_template_name = f"db_daily_md_{unique_suffix}"
    db_template_payload = {
        "name": db_template_name,
        "type": "briefing_markdown",
        "format": "md",
        "body": "DB TEMPLATE {{ title }}",
        "description": "DB-backed template",
    }
    r = c.post("/api/v1/outputs/templates", json=db_template_payload)
    assert r.status_code == 200, r.text
    db_template = r.json()
    assert db_template["name"] == db_template_name

    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "template_name": db_template_name, "temporary": True})
    assert r.status_code == 200, r.text
    db_output = r.json()
    assert db_output["version"] == 4
    assert db_output["metadata"].get("template_source") == "outputs_templates"
    assert db_output["metadata"].get("template_id") == db_template["id"]
    assert "DB TEMPLATE" in (db_output.get("content") or "")
    r = c.delete(f"/api/v1/outputs/templates/{db_template['id']}")
    assert r.status_code == 200, r.text

    # Template management
    legacy_template_name = f"daily_md_{unique_suffix}"
    template_payload = {
        "name": legacy_template_name,
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
    assert any(t["name"] == legacy_template_name for t in templates)

    # Get template detail
    r = c.get(f"/api/v1/watchlists/templates/{legacy_template_name}")
    assert r.status_code == 200
    template_detail = r.json()
    assert "Markdown summary template" in template_detail["description"]

    # Generate output using stored template
    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "template_name": legacy_template_name, "temporary": True})
    assert r.status_code == 200, r.text
    templated = r.json()
    assert templated["version"] == 5
    assert templated["format"] == "md"
    assert templated["metadata"].get("template_name") == legacy_template_name
    assert templated["metadata"].get("template_source") == "watchlists_templates"
    assert templated["content"].startswith("Daily Digest-Output-5") or "Daily Digest" in templated["content"]

    # When both stores have the same template name, DB-backed outputs template wins.
    collision_payload = {
        "name": legacy_template_name,
        "type": "briefing_markdown",
        "format": "md",
        "body": "DB OVERRIDE {{ title }}",
        "description": "DB-backed collision template",
    }
    r = c.post("/api/v1/outputs/templates", json=collision_payload)
    assert r.status_code == 200, r.text
    colliding_db_template = r.json()

    r = c.post("/api/v1/watchlists/outputs", json={"run_id": run_id, "template_name": legacy_template_name, "temporary": True})
    assert r.status_code == 200, r.text
    collision_output = r.json()
    assert collision_output["version"] == 6
    assert collision_output["metadata"].get("template_source") == "outputs_templates"
    assert collision_output["metadata"].get("template_id") == colliding_db_template["id"]
    assert "DB OVERRIDE" in (collision_output.get("content") or "")

    r = c.delete(f"/api/v1/outputs/templates/{colliding_db_template['id']}")
    assert r.status_code == 200, r.text

    # Delete template and confirm removal
    r = c.delete(f"/api/v1/watchlists/templates/{legacy_template_name}")
    assert r.status_code == 200
    r = c.get(f"/api/v1/watchlists/templates/{legacy_template_name}")
    assert r.status_code == 404
    r = c.get("/api/v1/watchlists/templates")
    assert all(t["name"] != legacy_template_name for t in r.json().get("items", []))


def test_watchlists_outputs_variants_and_ingest(client_with_user, monkeypatch):


    c = client_with_user
    monkeypatch.setenv("TEST_MODE", "1")

    class DummyTTS:
        async def generate_speech(self, req):  # noqa: ARG002 - signature used by TTS service
            yield b"FAKEAUDIO"

    async def _fake_get_tts_service_v2(*args, **kwargs):  # noqa: ARG002
        return DummyTTS()

    monkeypatch.setattr(
        "tldw_Server_API.app.core.TTS.tts_service_v2.get_tts_service_v2",
        _fake_get_tts_service_v2,
    )

    # Create RSS source
    src_body = {
        "name": "Variants Feed",
        "url": "https://example.com/variants-feed.xml",
        "source_type": "rss",
        "tags": ["variants"],
    }
    r = c.post("/api/v1/watchlists/sources", json=src_body)
    assert r.status_code == 200, r.text
    source_id = r.json()["id"]

    # Job scoped to source
    job_body = {
        "name": "Variants Digest",
        "scope": {"sources": [source_id]},
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
    run_id = r.json()["id"]

    # Create variant templates
    mece_name = f"mece_watchlists_{run_id}"
    mece_payload = {
        "name": mece_name,
        "type": "mece_markdown",
        "format": "md",
        "body": "# MECE\\n{{ items|length }} items",
        "description": "Watchlists MECE template",
        "is_default": False,
    }
    r = c.post("/api/v1/outputs/templates", json=mece_payload)
    assert r.status_code == 200, r.text
    mece_id = r.json()["id"]

    tts_name = f"tts_watchlists_{run_id}"
    tts_payload = {
        "name": tts_name,
        "type": "tts_audio",
        "format": "mp3",
        "body": "Audio briefing for {{ items|length }} items.",
        "description": "Watchlists TTS template",
        "is_default": False,
    }
    r = c.post("/api/v1/outputs/templates", json=tts_payload)
    assert r.status_code == 200, r.text
    tts_id = r.json()["id"]

    # Generate output variants + ingest
    out_payload = {
        "run_id": run_id,
        "title": "Variants Briefing",
        "format": "md",
        "generate_mece": True,
        "mece_template_name": mece_name,
        "generate_tts": True,
        "tts_template_name": tts_name,
        "ingest_to_media_db": True,
    }
    r = c.post("/api/v1/watchlists/outputs", json=out_payload)
    assert r.status_code == 200, r.text
    base_output = r.json()
    assert base_output["media_item_id"] is not None

    r = c.get("/api/v1/watchlists/outputs", params={"run_id": run_id})
    assert r.status_code == 200, r.text
    outputs = r.json()["items"]
    mece_outputs = [o for o in outputs if o.get("type") == "mece_markdown"]
    tts_outputs = [o for o in outputs if o.get("type") == "tts_audio"]
    assert mece_outputs
    assert tts_outputs
    assert all(o.get("media_item_id") for o in mece_outputs)
    assert all(o.get("media_item_id") for o in tts_outputs)

    tts_output = tts_outputs[0]
    assert tts_output.get("format") == "mp3"
    assert tts_output.get("storage_path")
    r = c.get(f"/api/v1/watchlists/outputs/{tts_output['id']}/download")
    assert r.status_code == 200, r.text

    # Cleanup templates
    r = c.delete(f"/api/v1/outputs/templates/{mece_id}")
    assert r.status_code == 200, r.text
    r = c.delete(f"/api/v1/outputs/templates/{tts_id}")
    assert r.status_code == 200, r.text


def test_watchlists_outputs_pagination_excludes_mixed_origin_rows(client_with_user):
    c = client_with_user
    cdb = CollectionsDatabase.for_user(555)
    suffix = uuid.uuid4().hex[:8]
    job_id = int(f"91{suffix[:6]}", 16) % 1_000_000
    run_id = job_id + 1

    wl_old = cdb.create_output_artifact(
        type_="briefing_markdown",
        title=f"wl-old-{suffix}",
        format_="md",
        storage_path=f"wl-old-{suffix}.md",
        metadata_json=json.dumps({"origin": "watchlists"}),
        job_id=job_id,
        run_id=run_id,
    )
    wl_new = cdb.create_output_artifact(
        type_="briefing_markdown",
        title=f"wl-new-{suffix}",
        format_="md",
        storage_path=f"wl-new-{suffix}.md",
        metadata_json=json.dumps({"origin": "watchlists"}),
        job_id=job_id,
        run_id=run_id,
    )
    nw_1 = cdb.create_output_artifact(
        type_="briefing_markdown",
        title=f"non-watch-1-{suffix}",
        format_="md",
        storage_path=f"non-watch-1-{suffix}.md",
        metadata_json=json.dumps({"origin": "outputs"}),
        job_id=job_id,
        run_id=run_id,
    )
    nw_2 = cdb.create_output_artifact(
        type_="briefing_markdown",
        title=f"non-watch-2-{suffix}",
        format_="md",
        storage_path=f"non-watch-2-{suffix}.md",
        metadata_json=json.dumps({"origin": "outputs"}),
        job_id=job_id,
        run_id=run_id,
    )

    r = c.get("/api/v1/watchlists/outputs", params={"job_id": job_id, "page": 1, "size": 1})
    assert r.status_code == 200, r.text
    page1 = r.json()
    assert page1["total"] == 2
    assert len(page1["items"]) == 1
    assert page1["items"][0]["id"] == wl_new.id

    r = c.get("/api/v1/watchlists/outputs", params={"job_id": job_id, "page": 2, "size": 1})
    assert r.status_code == 200, r.text
    page2 = r.json()
    assert page2["total"] == 2
    assert len(page2["items"]) == 1
    assert page2["items"][0]["id"] == wl_old.id

    returned_ids = {page1["items"][0]["id"], page2["items"][0]["id"]}
    assert returned_ids == {wl_old.id, wl_new.id}
    assert nw_1.id not in returned_ids
    assert nw_2.id not in returned_ids


def test_preview_site_sources_returns_items(client_with_user, monkeypatch):


    c = client_with_user
    monkeypatch.delenv("TEST_MODE", raising=False)

    async def _fake_fetch(base_url, rules, *, tenant_id="default", timeout=10.0):
        return [{"title": "Stub Item", "url": "https://example.com/x", "summary": "Stub summary"}]

    from tldw_Server_API.app.api.v1.endpoints import watchlists as watchlists_endpoints
    monkeypatch.setattr(watchlists_endpoints, "fetch_site_items_with_rules", _fake_fetch)

    # Create site source
    src_body = {
        "name": "Preview Site",
        "url": "https://example.com/",
        "source_type": "site",
        "tags": ["preview"],
    }
    r = c.post("/api/v1/watchlists/sources", json=src_body)
    assert r.status_code == 200, r.text
    source_id = r.json()["id"]

    # Job scoped to source
    job_body = {
        "name": "Preview Job",
        "scope": {"sources": [source_id]},
        "schedule_expr": None,
        "timezone": "UTC",
        "active": True,
    }
    r = c.post("/api/v1/watchlists/jobs", json=job_body)
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    r = c.post(f"/api/v1/watchlists/jobs/{job_id}/preview", params={"limit": 10, "per_source": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1


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
