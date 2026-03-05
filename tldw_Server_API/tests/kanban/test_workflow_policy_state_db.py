"""Workflow policy/state DB method tests."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB


def test_upsert_and_get_workflow_policy_roundtrip(
    kanban_db: KanbanDB,
    sample_board: dict[str, Any],
) -> None:
    """Policy upsert should persist statuses/transitions and roundtrip cleanly."""
    saved = kanban_db.upsert_workflow_policy(
        board_id=sample_board["id"],
        statuses=[
            {"status_key": "todo", "display_name": "To Do", "sort_order": 0},
            {"status_key": "impl", "display_name": "Implement", "sort_order": 1},
            {"status_key": "done", "display_name": "Done", "sort_order": 2, "is_terminal": True},
        ],
        transitions=[
            {"from_status_key": "todo", "to_status_key": "impl", "requires_claim": True},
            {"from_status_key": "impl", "to_status_key": "done", "requires_claim": True},
        ],
        is_paused=False,
        is_draining=False,
        default_lease_ttl_sec=1200,
        strict_projection=True,
        metadata={"source": "test"},
    )

    assert saved["board_id"] == sample_board["id"]
    assert saved["default_lease_ttl_sec"] == 1200
    assert len(saved["statuses"]) == 3
    assert len(saved["transitions"]) == 2

    fetched = kanban_db.get_workflow_policy(sample_board["id"])
    assert fetched is not None
    assert fetched["id"] == saved["id"]
    assert fetched["metadata"] == {"source": "test"}

    statuses = kanban_db.list_workflow_statuses(sample_board["id"])
    assert [status["status_key"] for status in statuses] == ["todo", "impl", "done"]

    transitions = kanban_db.list_workflow_transitions(sample_board["id"])
    assert {(edge["from_status_key"], edge["to_status_key"]) for edge in transitions} == {
        ("todo", "impl"),
        ("impl", "done"),
    }


def test_get_and_patch_card_workflow_state_lazy_bootstrap(
    kanban_db: KanbanDB,
    sample_card: dict[str, Any],
) -> None:
    """Legacy cards should lazily get workflow state and allow versioned patches."""
    state = kanban_db.get_card_workflow_state(sample_card["id"])

    assert state["card_id"] == sample_card["id"]
    assert state["workflow_status_key"] == "todo"
    assert state["version"] == 1

    updated = kanban_db.patch_card_workflow_state(
        card_id=sample_card["id"],
        workflow_status_key="impl",
        expected_version=state["version"],
        lease_owner=None,
        idempotency_key="policy-state-test-1",
        last_actor="test-suite",
    )

    assert updated["workflow_status_key"] == "impl"
    assert updated["version"] == state["version"] + 1
