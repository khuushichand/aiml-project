import os
from uuid import uuid4

import pytest


def _api_key() -> str:
    return os.environ.get("SINGLE_USER_API_KEY", "sk-test-1234567890-VALID")


def _auth_headers() -> dict:
    return {"X-API-KEY": _api_key()}


def _require_ok(resp, label: str) -> None:
    if not resp.ok:
        raise AssertionError(f"{label} failed: status={resp.status} body={resp.text()}")


@pytest.mark.e2e
def test_chatbooks_export_download_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    note_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"E2E Chatbook Note {suffix}",
            "content": f"Chatbook seed content {suffix}.",
        },
    )
    _require_ok(note_resp, "create note")
    note = note_resp.json()
    note_id = note["id"]
    note_version = note["version"]

    export_resp = page.request.post(
        "/api/v1/chatbooks/export",
        headers=headers,
        json={
            "name": f"E2E Chatbook {suffix}",
            "description": "Chatbook export workflow",
            "content_selections": {"note": [note_id]},
            "author": "e2e",
            "include_media": False,
            "media_quality": "compressed",
            "include_embeddings": False,
            "include_generated_content": True,
            "tags": ["e2e"],
            "categories": ["tests"],
            "async_mode": False,
        },
    )
    _require_ok(export_resp, "export chatbook")
    export_payload = export_resp.json()
    assert export_payload["success"] is True
    job_id = export_payload["job_id"]
    download_url = export_payload["download_url"]
    assert job_id
    assert download_url

    job_resp = page.request.get(f"/api/v1/chatbooks/export/jobs/{job_id}", headers=headers)
    _require_ok(job_resp, "get export job")
    job_payload = job_resp.json()
    assert job_payload["status"] == "completed"
    assert job_payload["download_url"]

    download_resp = page.request.get(download_url, headers=headers)
    _require_ok(download_resp, "download chatbook")
    assert download_resp.headers.get("content-type", "").startswith("application/zip")
    assert len(download_resp.body()) > 0

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(note_version)},
    )
    assert delete_resp.status == 204
