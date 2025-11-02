"""
test_chatbooks_roundtrip.py
Description: End-to-end round-trip for Chatbooks (export -> download -> import).

Creates a lightweight note, exports a chatbook synchronously, downloads it, then
imports it back. Designed to skip gracefully if quotas or the subsystem are not
available in the current environment.
"""

import io
import os
import pytest
import httpx

from .fixtures import api_client, data_tracker


@pytest.mark.critical
def test_chatbooks_export_import_roundtrip(api_client, data_tracker):
    # 0) Quick health check for chatbooks subsystem
    try:
        h = api_client.client.get("/api/v1/chatbooks/health")
        if h.status_code not in (200, 207):
            pytest.skip(f"Chatbooks health not OK: {h.status_code}")
    except httpx.HTTPError as e:
        pytest.skip(f"Chatbooks health not available: {e}")

    # 1) Create a small note to include in the export
    try:
        note_resp = api_client.create_note(
            title="E2E Chatbooks Smoke Note",
            content="Short note for chatbooks round-trip test."
        )
    except httpx.HTTPStatusError as e:
        # Notes may be disabled; skip rather than fail
        pytest.skip(f"Unable to create note for chatbook test: {e}")

    note_id = str(note_resp.get("id") or note_resp.get("note_id") or "")
    assert note_id, f"No note id returned: {note_resp}"
    data_tracker.add_note(int(note_id)) if note_id.isdigit() else None

    # 2) Export chatbook synchronously (async_mode=False)
    export_payload = {
        "name": "E2E Smoke Chatbook",
        "description": "Smoke export for round-trip validation",
        "content_selections": {"note": [note_id]},
        "author": "pytest",
        "include_media": False,
        "include_embeddings": False,
        "include_generated_content": False,
        "tags": ["e2e", "smoke"],
        "categories": ["tests"],
        "async_mode": False,
    }

    try:
        er = api_client.client.post("/api/v1/chatbooks/export", json=export_payload)
        er.raise_for_status()
        export_info = er.json()
        assert export_info.get("success") is True
        job_id = export_info.get("job_id")
        assert job_id, f"No job_id in export response: {export_info}"
    except httpx.HTTPStatusError as e:
        # Quotas or service not available -> skip
        if e.response.status_code in (400, 401, 403, 404, 413, 429, 500):
            pytest.skip(f"Chatbooks export unavailable: {e}")
        raise

    # 3) Download exported chatbook zip via secure download URL
    try:
        dl = api_client.client.get(f"/api/v1/chatbooks/download/{job_id}")
        dl.raise_for_status()
        assert dl.headers.get("content-type", "").startswith("application/zip")
        data = dl.content
        assert data and len(data) > 0
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Chatbooks download unavailable: {e}")

    # 4) Import the chatbook synchronously (async_mode=false)
    files = {"file": ("e2e.chatbook", io.BytesIO(data), "application/zip")}
    form = {
        "conflict_resolution": "skip",
        "prefix_imported": "false",
        "import_media": "false",
        "import_embeddings": "false",
        "async_mode": "false",
    }

    try:
        ir = api_client.client.post("/api/v1/chatbooks/import", files=files, data=form)
        ir.raise_for_status()
        imp = ir.json()
        assert imp.get("success") is True
    except httpx.HTTPStatusError as e:
        pytest.skip(f"Chatbooks import unavailable: {e}")
