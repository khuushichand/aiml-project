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
def test_chatbooks_export_import_search_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    note_title = f"E2E Chatbook Note {suffix}"
    note_body = f"Chatbook roundtrip content {suffix}."

    note_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": note_title,
            "content": note_body,
            "keywords": [suffix, "chatbook"],
        },
    )
    _require_ok(note_resp, "create note")
    note_payload = note_resp.json()
    note_id = note_payload["id"]
    note_version = note_payload["version"]

    export_resp = page.request.post(
        "/api/v1/chatbooks/export",
        headers=headers,
        json={
            "name": f"E2E Chatbook {suffix}",
            "description": "Chatbook roundtrip export/import workflow",
            "content_selections": {"note": [note_id]},
            "author": "e2e",
            "include_media": False,
            "media_quality": "compressed",
            "include_embeddings": False,
            "include_generated_content": True,
            "tags": ["e2e", suffix],
            "categories": ["tests"],
            "async_mode": False,
        },
    )
    _require_ok(export_resp, "export chatbook")
    export_payload = export_resp.json()
    job_id = export_payload.get("job_id")
    download_url = export_payload.get("download_url")
    assert job_id
    assert download_url

    job_resp = page.request.get(f"/api/v1/chatbooks/export/jobs/{job_id}", headers=headers)
    _require_ok(job_resp, "get export job")
    job_payload = job_resp.json()
    assert job_payload.get("status") == "completed"

    download_resp = page.request.get(download_url, headers=headers)
    _require_ok(download_resp, "download chatbook")
    chatbook_bytes = download_resp.body()
    assert chatbook_bytes

    import_resp = page.request.post(
        "/api/v1/chatbooks/import",
        headers=headers,
        multipart={
            "file": {
                "name": f"chatbook_{suffix}.zip",
                "mimeType": "application/zip",
                "buffer": chatbook_bytes,
            },
            "conflict_resolution": "rename",
            "prefix_imported": "true",
            "import_media": "false",
            "import_embeddings": "false",
            "async_mode": "false",
        },
    )
    _require_ok(import_resp, "import chatbook")
    import_payload = import_resp.json()
    assert import_payload.get("success") is True

    search_resp = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": suffix, "include_keywords": "true"},
    )
    _require_ok(search_resp, "search imported notes")
    search_results = search_resp.json()
    imported_note = next(
        (item for item in search_results if str(item.get("title", "")).startswith("[Imported]")),
        None,
    )
    assert imported_note is not None

    delete_original = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(note_version)},
    )
    assert delete_original.status == 204

    imported_version = imported_note.get("version", 1)
    delete_imported = page.request.delete(
        f"/api/v1/notes/{imported_note['id']}",
        headers={**headers, "expected-version": str(imported_version)},
    )
    assert delete_imported.status == 204
