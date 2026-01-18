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
def test_flashcards_deck_review_export_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    deck_resp = page.request.post(
        "/api/v1/flashcards/decks",
        headers=headers,
        json={
            "name": f"E2E Deck {suffix}",
            "description": "Deck for flashcards workflow test",
        },
    )
    _require_ok(deck_resp, "create deck")
    deck = deck_resp.json()
    deck_id = deck["id"]

    decks_resp = page.request.get("/api/v1/flashcards/decks", headers=headers)
    _require_ok(decks_resp, "list decks")
    deck_ids = [d["id"] for d in decks_resp.json()]
    assert deck_id in deck_ids

    card_resp = page.request.post(
        "/api/v1/flashcards",
        headers=headers,
        json={
            "deck_id": deck_id,
            "front": f"What is {suffix}?",
            "back": "An E2E flashcard.",
            "tags": [f"e2e-{suffix}", "workflow"],
        },
    )
    _require_ok(card_resp, "create flashcard")
    card = card_resp.json()
    card_uuid = card["uuid"]
    card_version = card["version"]

    get_card = page.request.get(f"/api/v1/flashcards/id/{card_uuid}", headers=headers)
    _require_ok(get_card, "get flashcard")
    fetched = get_card.json()
    assert fetched["front"] == f"What is {suffix}?"

    update_resp = page.request.patch(
        f"/api/v1/flashcards/{card_uuid}",
        headers=headers,
        json={
            "front": f"Define {suffix}.",
            "expected_version": card_version,
            "tags": ["updated", f"e2e-{suffix}"],
        },
    )
    _require_ok(update_resp, "update flashcard")
    updated = update_resp.json()

    tags_resp = page.request.put(
        f"/api/v1/flashcards/{card_uuid}/tags",
        headers=headers,
        json={"tags": ["spaced", "review"]},
    )
    _require_ok(tags_resp, "set flashcard tags")
    tags_version = tags_resp.json()["version"]

    tags_list_resp = page.request.get(
        f"/api/v1/flashcards/{card_uuid}/tags",
        headers=headers,
    )
    _require_ok(tags_list_resp, "get flashcard tags")
    tags_items = [t.get("keyword") for t in tags_list_resp.json().get("items", [])]
    assert "spaced" in tags_items

    review_resp = page.request.post(
        "/api/v1/flashcards/review",
        headers=headers,
        json={
            "card_uuid": card_uuid,
            "rating": 4,
            "answer_time_ms": 1200,
        },
    )
    _require_ok(review_resp, "review flashcard")
    review_payload = review_resp.json()
    assert review_payload["uuid"] == card_uuid
    assert review_payload["repetitions"] >= 1

    list_resp = page.request.get(
        "/api/v1/flashcards",
        headers=headers,
        params={"deck_id": str(deck_id), "limit": "50"},
    )
    _require_ok(list_resp, "list flashcards")
    listed = [item["uuid"] for item in list_resp.json().get("items", [])]
    assert card_uuid in listed

    export_resp = page.request.get(
        "/api/v1/flashcards/export",
        headers=headers,
        params={
            "deck_id": str(deck_id),
            "format": "csv",
            "include_header": "true",
            "delimiter": ",",
        },
    )
    _require_ok(export_resp, "export flashcards")
    export_text = export_resp.body().decode("utf-8")
    assert f"Define {suffix}." in export_text

    delete_resp = page.request.delete(
        f"/api/v1/flashcards/{card_uuid}",
        headers=headers,
        params={"expected_version": str(tags_version)},
    )
    _require_ok(delete_resp, "delete flashcard")

    missing = page.request.get(f"/api/v1/flashcards/id/{card_uuid}", headers=headers)
    assert missing.status == 404
