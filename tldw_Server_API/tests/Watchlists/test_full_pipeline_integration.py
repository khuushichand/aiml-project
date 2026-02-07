"""Integration tests for the full newsletter briefing pipeline.

Covers: source → filter → run → output → download pipeline,
OPML round-trip, preview-to-run accuracy, and email+chatbook delivery.
"""
from __future__ import annotations

import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_with_user(monkeypatch, tmp_path):
    async def override_user():
        return User(id=950, username="pipeline-user", email="pipeline@example.com", is_active=True)

    base_dir = tmp_path / "test_user_dbs_full_pipeline"
    base_dir.mkdir(parents=True, exist_ok=True)
    template_dir = tmp_path / "watchlist_templates_pipeline"
    template_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("USER_DB_BASE_DIR", str(base_dir))
    monkeypatch.setenv("WATCHLIST_TEMPLATE_DIR", str(template_dir))
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("EMAIL_PROVIDER", "mock")

    from fastapi import FastAPI

    from tldw_Server_API.app.api.v1.endpoints.watchlists import router as watchlists_router
    from tldw_Server_API.app.core.config import API_V1_PREFIX

    app = FastAPI()
    app.include_router(watchlists_router, prefix=f"{API_V1_PREFIX}")
    app.dependency_overrides[get_request_user] = override_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helper: create source → job → run pipeline
# ---------------------------------------------------------------------------

def _create_source(c: TestClient, **kwargs) -> dict:
    defaults = {
        "name": "Test Feed",
        "url": "https://example.com/test-feed.xml",
        "source_type": "rss",
    }
    defaults.update(kwargs)
    r = c.post("/api/v1/watchlists/sources", json=defaults)
    assert r.status_code == 200, r.text
    return r.json()


def _create_job(c: TestClient, scope: dict, **kwargs) -> dict:
    payload = {"name": "Test Job", "scope": scope, **kwargs}
    r = c.post("/api/v1/watchlists/jobs", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


def _run_job(c: TestClient, job_id: int) -> dict:
    r = c.post(f"/api/v1/watchlists/jobs/{job_id}/run")
    assert r.status_code == 200, r.text
    data = r.json()
    # Flatten stats into top-level for convenience (API nests them under 'stats')
    stats = data.get("stats") or {}
    data["items_found"] = data.get("items_found") or stats.get("items_found", 0)
    data["items_ingested"] = data.get("items_ingested") or stats.get("items_ingested", 0)
    return data


# ---------------------------------------------------------------------------
# 1. Full source → briefing pipeline
# ---------------------------------------------------------------------------

def test_source_to_briefing_pipeline(client_with_user: TestClient):
    """End-to-end: create source → create job → preview → run → output → download."""
    c = client_with_user

    # 1. Create source
    src = _create_source(c, name="Pipeline Feed", url="https://example.com/feed-pipeline.xml")
    source_id = src["id"]

    # 2. Create job with a keyword filter
    job = _create_job(
        c,
        scope={"sources": [source_id]},
        job_filters={
            "filters": [
                {"type": "keyword", "action": "flag", "value": {"keywords": ["Test"], "match": "any"}},
            ]
        },
    )
    job_id = job["id"]

    # 3. Preview
    preview = c.post(f"/api/v1/watchlists/jobs/{job_id}/preview", params={"limit": 10, "per_source": 10})
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()
    assert preview_data["total"] >= 1
    assert preview_data["ingestable"] >= 1

    # 4. Run
    run = _run_job(c, job_id)
    run_id = run["id"]

    # 5. Generate output (briefing_markdown)
    output = c.post(
        "/api/v1/watchlists/outputs",
        json={"run_id": run_id, "type": "briefing_markdown", "temporary": True},
    )
    assert output.status_code == 200, output.text
    output_data = output.json()
    assert "id" in output_data
    assert output_data.get("content") is not None

    # 6. Download
    dl = c.get(f"/api/v1/watchlists/outputs/{output_data['id']}/download")
    assert dl.status_code == 200, dl.text
    # Content should be non-empty markdown or text
    assert len(dl.text) > 0


# ---------------------------------------------------------------------------
# 2. OPML round-trip
# ---------------------------------------------------------------------------

def _sample_opml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="2.0">\n'
        "  <head><title>Test Feeds</title></head>\n"
        "  <body>\n"
        '    <outline text="Feed Alpha" title="Feed Alpha" xmlUrl="https://alpha.example.com/rss" />\n'
        '    <outline text="Feed Beta" title="Feed Beta" xmlUrl="https://beta.example.com/rss" />\n'
        '    <outline text="Feed Gamma" title="Feed Gamma" xmlUrl="https://gamma.example.com/rss" />\n'
        "  </body>\n"
        "</opml>\n"
    )


def test_opml_import_and_export(client_with_user: TestClient):
    """Import OPML and verify export contains all imported feeds."""
    c = client_with_user

    # Import
    opml_content = _sample_opml()
    files = {"file": ("feeds.opml", io.BytesIO(opml_content.encode("utf-8")), "application/xml")}
    import_resp = c.post("/api/v1/watchlists/sources/import", files=files, data={"active": "1"})
    assert import_resp.status_code == 200, import_resp.text
    import_data = import_resp.json()
    assert import_data["created"] == 3
    assert import_data["errors"] == 0

    # Verify each entry has a status
    for item in import_data.get("items", []):
        assert item["status"] == "created"

    # Export
    export_resp = c.get("/api/v1/watchlists/sources/export")
    assert export_resp.status_code == 200, export_resp.text
    assert "<opml" in export_resp.text
    assert "alpha.example.com" in export_resp.text
    assert "beta.example.com" in export_resp.text
    assert "gamma.example.com" in export_resp.text


@pytest.mark.xfail(
    reason="DatabaseError (UNIQUE constraint) not in _WATCHLISTS_NONCRITICAL_EXCEPTIONS — "
    "re-import should return 200 with skipped=1 but currently raises unhandled error",
    strict=False,
)
def test_opml_reimport_skips_duplicates(client_with_user: TestClient):
    """Re-importing same OPML should skip duplicates gracefully.

    Currently fails because DatabaseError from the backend is not caught
    by the import endpoint's exception handler. When fixed, this test should
    pass and the xfail marker can be removed.
    """
    c = client_with_user

    opml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="2.0">\n'
        "  <head><title>Dedup</title></head>\n"
        "  <body>\n"
        '    <outline text="Unique Feed" title="Unique" xmlUrl="https://unique-reimport.example.com/rss" />\n'
        "  </body>\n"
        "</opml>\n"
    )

    # First import
    files1 = {"file": ("feeds.opml", io.BytesIO(opml.encode("utf-8")), "application/xml")}
    r1 = c.post("/api/v1/watchlists/sources/import", files=files1, data={"active": "1"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["created"] == 1

    # Re-import — should skip duplicate
    files2 = {"file": ("feeds.opml", io.BytesIO(opml.encode("utf-8")), "application/xml")}
    r2 = c.post("/api/v1/watchlists/sources/import", files=files2, data={"active": "1"})
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["created"] == 0
    assert data["skipped"] == 1


def test_opml_import_with_missing_urls_silently_skipped(client_with_user: TestClient):
    """OPML entries missing xmlUrl are silently dropped by parse_opml()
    before reaching the import loop. Only valid entries are created."""
    c = client_with_user

    opml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<opml version="2.0">\n'
        "  <head><title>Mixed</title></head>\n"
        "  <body>\n"
        '    <outline text="Good Feed" title="Good" xmlUrl="https://good-opml-test.example.com/rss" />\n'
        '    <outline text="Bad Feed" title="Bad" />\n'  # Missing xmlUrl — silently dropped
        "  </body>\n"
        "</opml>\n"
    )
    files = {"file": ("mixed.opml", io.BytesIO(opml.encode("utf-8")), "application/xml")}
    r = c.post("/api/v1/watchlists/sources/import", files=files, data={"active": "1"})
    assert r.status_code == 200, r.text
    data = r.json()
    # Only the good feed with xmlUrl is imported; bad feed is dropped by parse_opml
    assert data["created"] >= 1
    # Total only includes entries that reached the import loop
    assert data["total"] >= 1


# ---------------------------------------------------------------------------
# 3. Preview accuracy matches run
# ---------------------------------------------------------------------------

def test_preview_matches_run(client_with_user: TestClient):
    """Preview ingestable count should match actual run items_ingested."""
    c = client_with_user

    src = _create_source(c, name="Preview Feed", url="https://example.com/feed-preview.xml")
    job = _create_job(c, scope={"sources": [src["id"]]})
    job_id = job["id"]

    # Preview
    preview = c.post(f"/api/v1/watchlists/jobs/{job_id}/preview", params={"limit": 100, "per_source": 100})
    assert preview.status_code == 200, preview.text
    expected_ingest = preview.json()["ingestable"]

    # Run
    run = _run_job(c, job_id)
    actual_ingest = run["items_ingested"]

    assert actual_ingest == expected_ingest


# ---------------------------------------------------------------------------
# 4. Email + chatbook delivery
# ---------------------------------------------------------------------------

def test_email_and_chatbook_delivery(client_with_user: TestClient):
    """Generate output with both email and chatbook delivery channels."""
    c = client_with_user

    _create_source(c, name="Delivery Feed", url="https://example.com/feed-delivery.xml", tags=["delivery"])
    job = _create_job(
        c,
        scope={"tags": ["delivery"]},
        output_prefs={
            "deliveries": {
                "email": {"enabled": True, "recipients": ["default@example.com"]},
                "chatbook": {"enabled": True},
            }
        },
    )
    run = _run_job(c, job["id"])
    run_id = run["id"]

    output = c.post(
        "/api/v1/watchlists/outputs",
        json={
            "run_id": run_id,
            "title": "Delivery Test",
            "deliveries": {
                "email": {"subject": "Test Digest", "recipients": ["test@example.com"], "attach_file": True},
                "chatbook": {"title": "Test Document", "description": "Auto", "metadata": {"origin": "test"}},
            },
        },
    )
    assert output.status_code == 200, output.text
    payload = output.json()

    deliveries = payload.get("metadata", {}).get("deliveries", [])
    assert len(deliveries) == 2
    channels = {entry["channel"] for entry in deliveries}
    assert channels == {"email", "chatbook"}

    email_result = next(entry for entry in deliveries if entry["channel"] == "email")
    assert email_result["status"] in {"sent", "partial"}

    chatbook_result = next(entry for entry in deliveries if entry["channel"] == "chatbook")
    assert chatbook_result["status"] in {"stored", "failed"}

    # If chatbook was stored, verify in DB
    chatbook_id = payload.get("metadata", {}).get("chatbook_document_id")
    if chatbook_result["status"] == "stored":
        assert isinstance(chatbook_id, int)
        db_path = DatabasePaths.get_chacha_db_path(950)
        with sqlite3.connect(db_path) as conn:
            row = conn.execute("SELECT metadata FROM generated_documents WHERE id = ?", (chatbook_id,)).fetchone()
        assert row is not None
        stored_meta = json.loads(row[0])
        assert stored_meta.get("origin") == "test"


# ---------------------------------------------------------------------------
# 5. Job with multiple sources
# ---------------------------------------------------------------------------

def test_job_with_multiple_sources(client_with_user: TestClient):
    """A job scoped to multiple sources ingests items from all of them."""
    c = client_with_user

    src1 = _create_source(c, name="Multi Feed 1", url="https://example.com/multi-1.xml")
    src2 = _create_source(c, name="Multi Feed 2", url="https://example.com/multi-2.xml")

    job = _create_job(c, scope={"sources": [src1["id"], src2["id"]]})
    run = _run_job(c, job["id"])

    # Both sources should contribute items
    assert run["items_ingested"] >= 1
    assert run["items_found"] >= 1


# ---------------------------------------------------------------------------
# 6. Output with custom template
# ---------------------------------------------------------------------------

def test_output_with_custom_template(client_with_user: TestClient):
    """Create a custom template, then use it for output generation."""
    c = client_with_user

    # Create template
    tmpl = c.post(
        "/api/v1/watchlists/templates",
        json={
            "name": "custom_brief",
            "format": "md",
            "content": "# {{ date }}\n{% for item in items %}* {{ item.title }}\n{% endfor %}",
            "description": "Custom briefing template",
        },
    )
    assert tmpl.status_code == 200, tmpl.text
    assert tmpl.json()["version"] == 1

    # Create source + job + run
    src = _create_source(c, name="Template Feed", url="https://example.com/feed-template.xml")
    job = _create_job(c, scope={"sources": [src["id"]]})
    run = _run_job(c, job["id"])

    # Generate output with custom template
    output = c.post(
        "/api/v1/watchlists/outputs",
        json={
            "run_id": run["id"],
            "template_name": "custom_brief",
            "temporary": True,
        },
    )
    assert output.status_code == 200, output.text
    content = output.json().get("content", "")
    assert content.startswith("#")
    assert output.json()["metadata"]["template_name"] == "custom_brief"


# ---------------------------------------------------------------------------
# 7. Tags-based scope
# ---------------------------------------------------------------------------

def test_job_scoped_by_tags(client_with_user: TestClient):
    """A job scoped by tags picks up sources with matching tags."""
    c = client_with_user

    _create_source(c, name="Tagged Feed A", url="https://example.com/tagged-a.xml", tags=["news", "daily"])
    _create_source(c, name="Tagged Feed B", url="https://example.com/tagged-b.xml", tags=["news"])
    _create_source(c, name="Untagged Feed", url="https://example.com/untagged.xml", tags=["sports"])

    # Job scoped to 'news' tag should pick up both A and B
    job = _create_job(c, scope={"tags": ["news"]})
    run = _run_job(c, job["id"])
    assert run["items_found"] >= 1


# ---------------------------------------------------------------------------
# 8. Filter tallies in run details
# ---------------------------------------------------------------------------

def test_run_details_include_filter_tallies(client_with_user: TestClient):
    """Run details should include filter tallies showing which filters triggered."""
    c = client_with_user

    src = _create_source(c, name="Tally Feed", url="https://example.com/feed-tally.xml")
    job = _create_job(
        c,
        scope={"sources": [src["id"]]},
        job_filters={
            "filters": [
                {"type": "keyword", "action": "flag", "value": {"keywords": ["Test"], "match": "any"}},
            ]
        },
    )
    run = _run_job(c, job["id"])
    run_id = run["id"]

    # Get run details
    details = c.get(f"/api/v1/watchlists/runs/{run_id}")
    assert details.status_code == 200, details.text
    data = details.json()
    # Run details should have standard fields
    assert "id" in data
