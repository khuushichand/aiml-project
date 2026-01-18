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
def test_notes_bulk_keywords_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    suggest_resp = page.request.post(
        "/api/v1/notes/title/suggest",
        headers=headers,
        json={
            "content": f"Bulk note suggestion content {suffix}.",
            "title_strategy": "heuristic",
            "title_max_len": 120,
        },
    )
    _require_ok(suggest_resp, "suggest title")
    suggested_title = suggest_resp.json().get("title")
    assert suggested_title

    bulk_resp = page.request.post(
        "/api/v1/notes/bulk",
        headers=headers,
        json={
            "notes": [
                {
                    "title": f"Bulk Note A {suffix}",
                    "content": f"Bulk note A content {suffix}.",
                    "keywords": [f"kw-a-{suffix}", f"shared-{suffix}"],
                },
                {
                    "content": f"Bulk note B content {suffix}.",
                    "auto_title": True,
                    "title_strategy": "heuristic",
                    "keywords": f"kw-b-{suffix}, shared-{suffix}",
                },
            ]
        },
    )
    _require_ok(bulk_resp, "bulk create notes")
    bulk_payload = bulk_resp.json()
    created_notes = [
        item["note"]
        for item in bulk_payload.get("results", [])
        if item.get("success") and item.get("note")
    ]
    assert len(created_notes) == 2
    note_a = next(n for n in created_notes if n.get("title") == f"Bulk Note A {suffix}")
    note_b = next(n for n in created_notes if n.get("id") != note_a.get("id"))

    keyword_resp = page.request.post(
        "/api/v1/notes/keywords/",
        headers=headers,
        json={"keyword": f"bulk-link-{suffix}"},
    )
    _require_ok(keyword_resp, "create keyword")
    keyword_payload = keyword_resp.json()
    keyword_id = keyword_payload["id"]

    link_resp = page.request.post(
        f"/api/v1/notes/{note_a['id']}/keywords/{keyword_id}",
        headers=headers,
    )
    _require_ok(link_resp, "link note to keyword")

    search_resp = page.request.get(
        "/api/v1/notes/search",
        headers=headers,
        params={"tokens": [f"bulk-link-{suffix}"]},
    )
    _require_ok(search_resp, "search notes by keyword token")
    search_results = search_resp.json()
    assert any(item.get("id") == note_a["id"] for item in search_results)

    keywords_for_note = page.request.get(
        f"/api/v1/notes/{note_a['id']}/keywords/",
        headers=headers,
    )
    _require_ok(keywords_for_note, "get keywords for note")
    keyword_items = keywords_for_note.json().get("keywords", [])
    keyword_texts = {kw.get("keyword") for kw in keyword_items if isinstance(kw, dict)}
    assert f"bulk-link-{suffix}" in keyword_texts

    unlink_resp = page.request.delete(
        f"/api/v1/notes/{note_a['id']}/keywords/{keyword_id}",
        headers=headers,
    )
    _require_ok(unlink_resp, "unlink note from keyword")

    post_unlink = page.request.get(
        f"/api/v1/notes/{note_a['id']}/keywords/",
        headers=headers,
    )
    _require_ok(post_unlink, "get keywords after unlink")
    post_texts = {kw.get("keyword") for kw in post_unlink.json().get("keywords", [])}
    assert f"bulk-link-{suffix}" not in post_texts

    patch_resp = page.request.patch(
        f"/api/v1/notes/{note_b['id']}",
        headers=headers,
        json={"content": f"Bulk note B content updated {suffix}."},
    )
    _require_ok(patch_resp, "patch note")
    patched_note = patch_resp.json()

    export_resp = page.request.post(
        "/api/v1/notes/export.csv",
        headers=headers,
        json={
            "note_ids": [note_a["id"], note_b["id"]],
            "include_keywords": True,
            "format": "csv",
        },
    )
    _require_ok(export_resp, "export notes csv")
    export_csv = export_resp.body().decode("utf-8")
    assert f"Bulk Note A {suffix}" in export_csv

    keyword_get = page.request.get(
        f"/api/v1/notes/keywords/{keyword_id}",
        headers=headers,
    )
    _require_ok(keyword_get, "get keyword")
    keyword_version = keyword_get.json()["version"]

    delete_keyword = page.request.delete(
        f"/api/v1/notes/keywords/{keyword_id}",
        headers={**headers, "expected-version": str(keyword_version)},
    )
    assert delete_keyword.status == 204

    note_a_latest = page.request.get(f"/api/v1/notes/{note_a['id']}", headers=headers).json()
    note_b_latest = page.request.get(f"/api/v1/notes/{note_b['id']}", headers=headers).json()

    delete_a = page.request.delete(
        f"/api/v1/notes/{note_a['id']}",
        headers={**headers, "expected-version": str(note_a_latest["version"])},
    )
    assert delete_a.status == 204
    delete_b = page.request.delete(
        f"/api/v1/notes/{note_b['id']}",
        headers={**headers, "expected-version": str(note_b_latest["version"])},
    )
    assert delete_b.status == 204
