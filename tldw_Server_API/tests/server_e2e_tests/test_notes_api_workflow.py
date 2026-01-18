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
def test_notes_keywords_export_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    title = f"E2E Note {suffix}"
    content = f"Seed content for note {suffix}."
    keywords = [f"alpha-{suffix}", f"beta-{suffix}"]

    create_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": title,
            "content": content,
            "keywords": keywords,
        },
    )
    _require_ok(create_resp, "create note")
    created = create_resp.json()
    note_id = created["id"]
    version = created["version"]
    assert created["title"] == title
    assert created["content"] == content
    if isinstance(created.get("keywords"), list):
        kw_texts = {kw.get("keyword") for kw in created["keywords"] if isinstance(kw, dict)}
        for kw in keywords:
            assert kw in kw_texts

    get_resp = page.request.get(f"/api/v1/notes/{note_id}", headers=headers)
    _require_ok(get_resp, "get note")
    fetched = get_resp.json()
    assert fetched["id"] == note_id
    assert fetched["title"] == title

    kw_search_resp = page.request.get(
        "/api/v1/notes/keywords/search/",
        headers=headers,
        params={"query": keywords[0]},
    )
    _require_ok(kw_search_resp, "search keywords")
    kw_results = kw_search_resp.json()
    assert any(kw.get("keyword") == keywords[0] for kw in kw_results)

    updated_content = f"Updated content for {suffix}."
    updated_keywords = [keywords[0], f"gamma-{suffix}"]
    update_resp = page.request.put(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
        json={
            "title": title,
            "content": updated_content,
            "keywords": updated_keywords,
        },
    )
    _require_ok(update_resp, "update note")
    updated = update_resp.json()
    updated_version = updated["version"]
    assert updated["content"] == updated_content
    assert updated_version == version + 1

    kw_for_note_resp = page.request.get(
        f"/api/v1/notes/{note_id}/keywords/",
        headers=headers,
    )
    _require_ok(kw_for_note_resp, "get keywords for note")
    kw_payload = kw_for_note_resp.json()
    kw_texts = {kw.get("keyword") for kw in kw_payload.get("keywords", [])}
    for kw in updated_keywords:
        assert kw in kw_texts

    search_resp = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": title, "include_keywords": "true"},
    )
    _require_ok(search_resp, "search notes")
    search_results = search_resp.json()
    assert any(item.get("id") == note_id for item in search_results)

    export_resp = page.request.post(
        "/api/v1/notes/export",
        headers=headers,
        json={
            "note_ids": [note_id],
            "include_keywords": True,
            "format": "json",
        },
    )
    _require_ok(export_resp, "export notes")
    export_payload = export_resp.json()
    exported_ids = [item.get("id") for item in export_payload.get("notes", [])]
    assert note_id in exported_ids

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(updated_version)},
    )
    assert delete_resp.status == 204

    missing_resp = page.request.get(f"/api/v1/notes/{note_id}", headers=headers)
    assert missing_resp.status == 404
