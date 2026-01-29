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
def test_notes_tags_soft_delete_restore_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    title = f"E2E Tagged Note {suffix}"
    content = f"Tagged note content {suffix}."
    keywords = [f"tag-{suffix}", f"group-{suffix}"]

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

    keywords_resp = page.request.get(
        f"/api/v1/notes/{note_id}/keywords/",
        headers=headers,
    )
    _require_ok(keywords_resp, "get note keywords")
    keywords_payload = keywords_resp.json()
    kw_texts = {kw.get("keyword") for kw in keywords_payload.get("keywords", [])}
    for kw in keywords:
        assert kw in kw_texts

    kw_search_resp = page.request.get(
        "/api/v1/notes/keywords/search/",
        headers=headers,
        params={"query": keywords[0]},
    )
    _require_ok(kw_search_resp, "search keywords")
    kw_results = kw_search_resp.json()
    assert any(item.get("keyword") == keywords[0] for item in kw_results)

    search_resp = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": title, "include_keywords": "true"},
    )
    _require_ok(search_resp, "search notes")
    search_results = search_resp.json()
    assert any(item.get("id") == note_id for item in search_results)

    delete_resp = page.request.delete(
        f"/api/v1/notes/{note_id}",
        headers={**headers, "expected-version": str(version)},
    )
    assert delete_resp.status == 204

    missing_resp = page.request.get(f"/api/v1/notes/{note_id}", headers=headers)
    assert missing_resp.status == 404

    restored_title = f"{title} Restored"
    restore_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": restored_title,
            "content": content,
            "keywords": keywords,
        },
    )
    _require_ok(restore_resp, "restore note")
    restored = restore_resp.json()
    restored_id = restored["id"]
    restored_version = restored["version"]

    restored_search = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"query": restored_title},
    )
    _require_ok(restored_search, "search restored note")
    restored_results = restored_search.json()
    assert any(item.get("id") == restored_id for item in restored_results)

    cleanup_resp = page.request.delete(
        f"/api/v1/notes/{restored_id}",
        headers={**headers, "expected-version": str(restored_version)},
    )
    assert cleanup_resp.status == 204
