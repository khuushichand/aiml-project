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
def test_reading_list_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    tag = f"reading-{suffix}"
    bulk_tag = f"bulk-{suffix}"

    url_one = f"{server_url}/reading/{suffix}"
    save_one_resp = page.request.post(
        "/api/v1/reading/save",
        headers=headers,
        json={
            "url": url_one,
            "title": f"Reading One {suffix}",
            "tags": [tag],
            "notes": "Seed note for reading item.",
            "content": f"Inline content for reading item {suffix}.",
        },
    )
    _require_ok(save_one_resp, "save reading item one")
    item_one = save_one_resp.json()
    item_one_id = item_one["id"]

    url_two = f"{server_url}/reading/{suffix}/second"
    save_two_resp = page.request.post(
        "/api/v1/reading/save",
        headers=headers,
        json={
            "url": url_two,
            "title": f"Reading Two {suffix}",
            "tags": [tag, "secondary"],
            "notes": "Second item notes.",
            "content": f"Second inline content {suffix}.",
        },
    )
    _require_ok(save_two_resp, "save reading item two")
    item_two_id = save_two_resp.json()["id"]

    list_resp = page.request.get(
        "/api/v1/reading/items",
        headers=headers,
        params={"tags": tag, "limit": 50, "offset": 0},
    )
    _require_ok(list_resp, "list reading items")
    list_payload = list_resp.json()
    listed_ids = {item.get("id") for item in list_payload.get("items", [])}
    assert item_one_id in listed_ids
    assert item_two_id in listed_ids

    detail_resp = page.request.get(f"/api/v1/reading/items/{item_one_id}", headers=headers)
    _require_ok(detail_resp, "get reading item detail")
    detail_payload = detail_resp.json()
    assert detail_payload["id"] == item_one_id
    assert detail_payload.get("title") == f"Reading One {suffix}"

    update_resp = page.request.patch(
        f"/api/v1/reading/items/{item_one_id}",
        headers=headers,
        json={"status": "read", "favorite": True, "tags": [tag, "updated"], "notes": "Updated notes."},
    )
    _require_ok(update_resp, "update reading item")
    update_payload = update_resp.json()
    assert update_payload.get("status") == "read"
    assert update_payload.get("favorite") is True

    bulk_resp = page.request.post(
        "/api/v1/reading/items/bulk",
        headers=headers,
        json={"item_ids": [item_one_id, item_two_id], "action": "add_tags", "tags": [bulk_tag]},
    )
    _require_ok(bulk_resp, "bulk update reading items")
    bulk_payload = bulk_resp.json()
    assert bulk_payload.get("succeeded") == 2
    assert bulk_payload.get("failed") == 0

    export_resp = page.request.get(
        "/api/v1/reading/export",
        headers=headers,
        params={"format": "jsonl", "tags": tag},
    )
    _require_ok(export_resp, "export reading items")
    export_body = export_resp.text()
    assert url_one in export_body
    assert url_two in export_body

    delete_one_resp = page.request.delete(
        f"/api/v1/reading/items/{item_one_id}",
        headers=headers,
        params={"hard": "true"},
    )
    _require_ok(delete_one_resp, "delete reading item one")
    delete_payload = delete_one_resp.json()
    assert delete_payload.get("hard") is True

    delete_two_resp = page.request.delete(
        f"/api/v1/reading/items/{item_two_id}",
        headers=headers,
        params={"hard": "true"},
    )
    _require_ok(delete_two_resp, "delete reading item two")

    missing_resp = page.request.get(f"/api/v1/reading/items/{item_one_id}", headers=headers)
    assert missing_resp.status == 404
