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
def test_kanban_bulk_ops_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    board_resp = page.request.post(
        "/api/v1/kanban/boards",
        headers=headers,
        json={
            "name": f"E2E Bulk Board {suffix}",
            "description": "Board for bulk operations",
            "client_id": f"board-bulk-{suffix}",
        },
    )
    _require_ok(board_resp, "create board")
    board_id = board_resp.json()["id"]

    list_a_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        headers=headers,
        json={"name": "Todo", "client_id": f"list-a-{suffix}"},
    )
    _require_ok(list_a_resp, "create list A")
    list_a_id = list_a_resp.json()["id"]

    list_b_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        headers=headers,
        json={"name": "Done", "client_id": f"list-b-{suffix}"},
    )
    _require_ok(list_b_resp, "create list B")
    list_b_id = list_b_resp.json()["id"]

    label_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/labels",
        headers=headers,
        json={"name": f"Bulk {suffix}", "color": "purple"},
    )
    _require_ok(label_resp, "create label")
    label_id = label_resp.json()["id"]

    card_ids = []
    for idx in range(3):
        card_resp = page.request.post(
            f"/api/v1/kanban/lists/{list_a_id}/cards",
            headers=headers,
            json={
                "title": f"Bulk Card {suffix}-{idx}",
                "description": "Card for bulk ops",
                "client_id": f"card-{suffix}-{idx}",
            },
        )
        _require_ok(card_resp, f"create card {idx}")
        card_ids.append(card_resp.json()["id"])

    bulk_label = page.request.post(
        "/api/v1/kanban/cards/bulk-label",
        headers=headers,
        json={"card_ids": card_ids, "add_label_ids": [label_id]},
    )
    _require_ok(bulk_label, "bulk label cards")
    assert bulk_label.json()["updated_count"] == len(card_ids)

    filtered = page.request.get(
        f"/api/v1/kanban/boards/{board_id}/cards",
        headers=headers,
        params={"label_ids": str(label_id), "per_page": "50"},
    )
    _require_ok(filtered, "filter cards by label")
    filtered_ids = {c["id"] for c in filtered.json().get("cards", [])}
    assert set(card_ids).issubset(filtered_ids)

    remove_label = page.request.post(
        "/api/v1/kanban/cards/bulk-label",
        headers=headers,
        json={"card_ids": card_ids, "remove_label_ids": [label_id]},
    )
    _require_ok(remove_label, "bulk remove labels")

    filtered_after = page.request.get(
        f"/api/v1/kanban/boards/{board_id}/cards",
        headers=headers,
        params={"label_ids": str(label_id), "per_page": "50"},
    )
    _require_ok(filtered_after, "filter after remove label")
    assert filtered_after.json().get("cards") == []

    bulk_move = page.request.post(
        "/api/v1/kanban/cards/bulk-move",
        headers=headers,
        json={"card_ids": card_ids, "target_list_id": list_b_id},
    )
    _require_ok(bulk_move, "bulk move cards")
    moved_cards = bulk_move.json().get("cards", [])
    assert all(card["list_id"] == list_b_id for card in moved_cards)

    bulk_archive = page.request.post(
        "/api/v1/kanban/cards/bulk-archive",
        headers=headers,
        json={"card_ids": card_ids},
    )
    _require_ok(bulk_archive, "bulk archive cards")
    assert bulk_archive.json()["archived_count"] == len(card_ids)

    list_archived = page.request.get(
        f"/api/v1/kanban/lists/{list_b_id}/cards",
        headers=headers,
        params={"include_archived": "true"},
    )
    _require_ok(list_archived, "list archived cards")
    archived_cards = [c for c in list_archived.json().get("cards", []) if c["id"] in card_ids]
    assert all(card["archived"] is True for card in archived_cards)

    bulk_unarchive = page.request.post(
        "/api/v1/kanban/cards/bulk-unarchive",
        headers=headers,
        json={"card_ids": card_ids},
    )
    _require_ok(bulk_unarchive, "bulk unarchive cards")
    assert bulk_unarchive.json()["unarchived_count"] == len(card_ids)

    list_unarchived = page.request.get(
        f"/api/v1/kanban/lists/{list_b_id}/cards",
        headers=headers,
        params={"include_archived": "true"},
    )
    _require_ok(list_unarchived, "list unarchived cards")
    unarchived_cards = [c for c in list_unarchived.json().get("cards", []) if c["id"] in card_ids]
    assert all(card["archived"] is False for card in unarchived_cards)

    bulk_delete = page.request.post(
        "/api/v1/kanban/cards/bulk-delete",
        headers=headers,
        json={"card_ids": card_ids},
    )
    _require_ok(bulk_delete, "bulk delete cards")
    assert bulk_delete.json()["deleted_count"] == len(card_ids)

    list_after_delete = page.request.get(
        f"/api/v1/kanban/lists/{list_b_id}/cards",
        headers=headers,
    )
    _require_ok(list_after_delete, "list cards after delete")
    remaining = {c["id"] for c in list_after_delete.json().get("cards", [])}
    assert not (set(card_ids) & remaining)

    delete_board = page.request.delete(
        f"/api/v1/kanban/boards/{board_id}",
        headers=headers,
    )
    _require_ok(delete_board, "delete board")
