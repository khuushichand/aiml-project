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
def test_kanban_labels_checklists_comments_workflow(page, server_url):
    headers = _auth_headers()
    suffix = uuid4().hex[:8]

    board_resp = page.request.post(
        "/api/v1/kanban/boards",
        headers=headers,
        json={
            "name": f"E2E Board Labels {suffix}",
            "description": "Board for kanban labels/checklists workflow",
            "client_id": f"board-labels-{suffix}",
        },
    )
    _require_ok(board_resp, "create board")
    board = board_resp.json()
    board_id = board["id"]

    list_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/lists",
        headers=headers,
        json={"name": "Work", "client_id": f"list-{suffix}"},
    )
    _require_ok(list_resp, "create list")
    list_id = list_resp.json()["id"]

    card_resp = page.request.post(
        f"/api/v1/kanban/lists/{list_id}/cards",
        headers=headers,
        json={
            "title": f"Card {suffix}",
            "description": "Card for labels/checklists/comments",
            "client_id": f"card-{suffix}",
        },
    )
    _require_ok(card_resp, "create card")
    card_id = card_resp.json()["id"]

    label_resp = page.request.post(
        f"/api/v1/kanban/boards/{board_id}/labels",
        headers=headers,
        json={"name": f"Urgent {suffix}", "color": "blue"},
    )
    _require_ok(label_resp, "create label")
    label = label_resp.json()
    label_id = label["id"]

    assign_label = page.request.post(
        f"/api/v1/kanban/cards/{card_id}/labels/{label_id}",
        headers=headers,
    )
    _require_ok(assign_label, "assign label")

    card_labels = page.request.get(
        f"/api/v1/kanban/cards/{card_id}/labels",
        headers=headers,
    )
    _require_ok(card_labels, "get card labels")
    label_ids = [item["id"] for item in card_labels.json().get("labels", [])]
    assert label_id in label_ids

    update_label = page.request.patch(
        f"/api/v1/kanban/labels/{label_id}",
        headers=headers,
        json={"color": "green"},
    )
    _require_ok(update_label, "update label")
    assert update_label.json()["color"] == "green"

    remove_label = page.request.delete(
        f"/api/v1/kanban/cards/{card_id}/labels/{label_id}",
        headers=headers,
    )
    assert remove_label.status == 204

    checklist_resp = page.request.post(
        f"/api/v1/kanban/cards/{card_id}/checklists",
        headers=headers,
        json={"name": f"Checklist {suffix}"},
    )
    _require_ok(checklist_resp, "create checklist")
    checklist_id = checklist_resp.json()["id"]

    item_a = page.request.post(
        f"/api/v1/kanban/checklists/{checklist_id}/items",
        headers=headers,
        json={"name": "Step A"},
    )
    _require_ok(item_a, "create checklist item A")
    item_a_id = item_a.json()["id"]

    item_b = page.request.post(
        f"/api/v1/kanban/checklists/{checklist_id}/items",
        headers=headers,
        json={"name": "Step B"},
    )
    _require_ok(item_b, "create checklist item B")
    item_b_id = item_b.json()["id"]

    items_list = page.request.get(
        f"/api/v1/kanban/checklists/{checklist_id}/items",
        headers=headers,
    )
    _require_ok(items_list, "list checklist items")
    assert len(items_list.json().get("items", [])) == 2

    reorder_resp = page.request.post(
        f"/api/v1/kanban/checklists/{checklist_id}/items/reorder",
        headers=headers,
        json={"item_ids": [item_b_id, item_a_id]},
    )
    _require_ok(reorder_resp, "reorder checklist items")

    check_item = page.request.post(
        f"/api/v1/kanban/checklist-items/{item_a_id}/check",
        headers=headers,
    )
    _require_ok(check_item, "check checklist item")
    assert check_item.json()["checked"] is True

    toggle_all = page.request.post(
        f"/api/v1/kanban/checklists/{checklist_id}/toggle-all",
        headers=headers,
        json={"checked": True},
    )
    _require_ok(toggle_all, "toggle all checklist items")
    toggle_payload = toggle_all.json()
    assert toggle_payload["checked_items"] == toggle_payload["total_items"]

    comments_resp = page.request.post(
        f"/api/v1/kanban/cards/{card_id}/comments",
        headers=headers,
        json={"content": f"Comment {suffix}"},
    )
    _require_ok(comments_resp, "create comment")
    comment_id = comments_resp.json()["id"]

    list_comments = page.request.get(
        f"/api/v1/kanban/cards/{card_id}/comments",
        headers=headers,
    )
    _require_ok(list_comments, "list comments")
    comment_ids = [c["id"] for c in list_comments.json().get("comments", [])]
    assert comment_id in comment_ids

    update_comment = page.request.patch(
        f"/api/v1/kanban/comments/{comment_id}",
        headers=headers,
        json={"content": f"Comment updated {suffix}"},
    )
    _require_ok(update_comment, "update comment")
    assert "updated" in update_comment.json()["content"]

    delete_comment = page.request.delete(
        f"/api/v1/kanban/comments/{comment_id}",
        headers=headers,
    )
    assert delete_comment.status == 204

    missing_comment = page.request.get(
        f"/api/v1/kanban/comments/{comment_id}",
        headers=headers,
    )
    assert missing_comment.status == 404

    delete_checklist = page.request.delete(
        f"/api/v1/kanban/checklists/{checklist_id}",
        headers=headers,
    )
    assert delete_checklist.status == 204

    delete_label = page.request.delete(
        f"/api/v1/kanban/labels/{label_id}",
        headers=headers,
    )
    assert delete_label.status == 204

    delete_card = page.request.delete(
        f"/api/v1/kanban/cards/{card_id}",
        headers=headers,
    )
    _require_ok(delete_card, "delete card")

    delete_board = page.request.delete(
        f"/api/v1/kanban/boards/{board_id}",
        headers=headers,
    )
    _require_ok(delete_board, "delete board")
