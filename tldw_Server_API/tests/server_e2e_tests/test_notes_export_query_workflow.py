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
def test_notes_export_query_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    note_a_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"Export Note A {suffix}",
            "content": f"Export note A content {suffix}.",
            "keywords": [f"export-{suffix}"],
        },
    )
    _require_ok(note_a_resp, "create note A")
    note_a = note_a_resp.json()

    note_b_resp = page.request.post(
        "/api/v1/notes/",
        headers=headers,
        json={
            "title": f"Export Note B {suffix}",
            "content": f"Export note B content {suffix}.",
            "keywords": [f"other-{suffix}"],
        },
    )
    _require_ok(note_b_resp, "create note B")
    note_b = note_b_resp.json()

    export_json = page.request.get(
        "/api/v1/notes/export",
        headers=headers,
        params={"q": note_a["title"], "include_keywords": "true"},
    )
    _require_ok(export_json, "export notes json")
    export_payload = export_json.json()
    exported_titles = [item.get("title") for item in export_payload.get("notes", [])]
    assert note_a["title"] in exported_titles
    assert note_b["title"] not in exported_titles

    export_csv = page.request.get(
        "/api/v1/notes/export.csv",
        headers=headers,
        params={"q": note_a["title"], "include_keywords": "true"},
    )
    _require_ok(export_csv, "export notes csv")
    csv_text = export_csv.body().decode("utf-8")
    assert note_a["title"] in csv_text
    assert note_b["title"] not in csv_text

    delete_a = page.request.delete(
        f"/api/v1/notes/{note_a['id']}",
        headers={**headers, "expected-version": str(note_a["version"])},
    )
    assert delete_a.status == 204

    delete_b = page.request.delete(
        f"/api/v1/notes/{note_b['id']}",
        headers={**headers, "expected-version": str(note_b["version"])},
    )
    assert delete_b.status == 204
