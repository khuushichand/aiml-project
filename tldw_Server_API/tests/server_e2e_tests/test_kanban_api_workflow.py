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
def test_kanban_board_list_card_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    board_resp = page.request.post(
        "/api/v1/kanban/boards",
        headers=headers,
        json={
            "name": f"E2E Board {suffix}",
            "description": "E2E kanban workflow board",
            "client_id": f"board-{suffix}",
        },
    )
    _require_ok(board_resp, "create board")
    board = board_resp.json()
    board_id = board["id"]

    list_a_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        headers=headers,
        json={
            "name": "Backlog",
            "client_id": f"list-a-{suffix}",
        },
    )
    _require_ok(list_a_resp, "create list A")
    list_a = list_a_resp.json()

    list_b_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        headers=headers,
        json={
            "name": "In Progress",
            "client_id": f"list-b-{suffix}",
        },
    )
    _require_ok(list_b_resp, "create list B")
    list_b = list_b_resp.json()

    card_resp = page.request.post(
        f"/api/v1/kanban/lists/{list_a['id']}/cards",
        headers=headers,
        json={
            "title": f"Card {suffix}",
            "description": "Track the e2e workflow steps.",
            "client_id": f"card-{suffix}",
            "priority": "medium",
        },
    )
    _require_ok(card_resp, "create card")
    card = card_resp.json()
    card_id = card["id"]

    update_resp = page.request.patch(
        f"/api/v1/kanban/cards/{card_id}",
        headers={**headers, "X-Expected-Version": str(card["version"])},
        json={
            "title": f"Card {suffix} (updated)",
            "priority": "high",
        },
    )
    _require_ok(update_resp, "update card")
    updated_card = update_resp.json()
    assert updated_card["priority"] == "high"

    move_resp = page.request.post(
        f"/api/v1/kanban/cards/{card_id}/move",
        headers=headers,
        json={
            "target_list_id": list_b["id"],
        },
    )
    _require_ok(move_resp, "move card")
    moved_card = move_resp.json()
    assert moved_card["list_id"] == list_b["id"]

    archive_resp = page.request.post(
        f"/api/v1/kanban/cards/{card_id}/archive",
        headers=headers,
    )
    _require_ok(archive_resp, "archive card")
    assert archive_resp.json()["archived"] is True

    unarchive_resp = page.request.post(
        f"/api/v1/kanban/cards/{card_id}/unarchive",
        headers=headers,
    )
    _require_ok(unarchive_resp, "unarchive card")
    assert unarchive_resp.json()["archived"] is False

    board_get_resp = page.request.get(
        f"/api/v1/kanban/boards/{board_id}",
        headers=headers,
        params={"include_lists": "true", "include_cards": "true"},
    )
    _require_ok(board_get_resp, "get board with lists")
    board_payload = board_get_resp.json()
    found = False
    for lst in board_payload.get("lists", []):
        if lst.get("id") == list_b["id"]:
            found = any(c.get("id") == card_id for c in lst.get("cards", []))
            break
    assert found

    delete_card_resp = page.request.delete(
        f"/api/v1/kanban/cards/{card_id}",
        headers=headers,
    )
    _require_ok(delete_card_resp, "delete card")

    missing_card = page.request.get(f"/api/v1/kanban/cards/{card_id}", headers=headers)
    assert missing_card.status == 404

    delete_board_resp = page.request.delete(
        f"/api/v1/kanban/boards/{board_id}",
        headers=headers,
    )
    _require_ok(delete_board_resp, "delete board")

    missing_board = page.request.get(f"/api/v1/kanban/boards/{board_id}", headers=headers)
    assert missing_board.status == 404
