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
def test_reading_highlights_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]
    quote_text = f"highlight phrase {suffix}"
    content_text = f"Intro text. {quote_text} with more context to anchor."

    save_resp = page.request.post(
        "/api/v1/reading/save",
        headers=headers,
        json={
            "url": f"{server_url}/reading/highlights/{suffix}",
            "title": f"Reading Highlight {suffix}",
            "tags": [f"highlight-{suffix}"],
            "content": content_text,
        },
    )
    _require_ok(save_resp, "save reading item")
    item_id = save_resp.json()["id"]

    highlight_resp = page.request.post(
        f"/api/v1/reading/items/{item_id}/highlight",
        headers=headers,
        json={
            "item_id": item_id,
            "quote": quote_text,
            "color": "yellow",
            "note": "Initial highlight note.",
            "anchor_strategy": "fuzzy_quote",
        },
    )
    _require_ok(highlight_resp, "create highlight")
    highlight_payload = highlight_resp.json()
    highlight_id = highlight_payload["id"]
    assert highlight_payload["item_id"] == item_id

    list_resp = page.request.get(
        f"/api/v1/reading/items/{item_id}/highlights",
        headers=headers,
    )
    _require_ok(list_resp, "list highlights")
    list_payload = list_resp.json()
    assert any(item.get("id") == highlight_id for item in list_payload)

    update_resp = page.request.patch(
        f"/api/v1/reading/highlights/{highlight_id}",
        headers=headers,
        json={"note": "Updated highlight note.", "color": "orange"},
    )
    _require_ok(update_resp, "update highlight")
    updated_payload = update_resp.json()
    assert updated_payload["note"] == "Updated highlight note."
    assert updated_payload["color"] == "orange"

    list_after_resp = page.request.get(
        f"/api/v1/reading/items/{item_id}/highlights",
        headers=headers,
    )
    _require_ok(list_after_resp, "list highlights after update")
    assert any(item.get("id") == highlight_id for item in list_after_resp.json())

    delete_highlight_resp = page.request.delete(
        f"/api/v1/reading/highlights/{highlight_id}",
        headers=headers,
    )
    _require_ok(delete_highlight_resp, "delete highlight")
    assert delete_highlight_resp.json().get("success") is True

    delete_item_resp = page.request.delete(
        f"/api/v1/reading/items/{item_id}",
        headers=headers,
        params={"hard": "true"},
    )
    _require_ok(delete_item_resp, "delete reading item")
