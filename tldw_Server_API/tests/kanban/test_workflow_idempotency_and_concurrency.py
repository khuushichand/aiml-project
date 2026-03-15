"""Workflow idempotency and optimistic-concurrency regression tests."""

from __future__ import annotations

from typing import Any

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB


def test_reused_transition_idempotency_key_replays_without_duplicate_event(
    kanban_db: KanbanDB,
    sample_board: dict[str, Any],
    sample_card: dict[str, Any],
) -> None:
    """Reusing transition idempotency key should replay state and avoid duplicate events."""
    kanban_db.upsert_workflow_policy(
        board_id=sample_board["id"],
        statuses=[
            {"status_key": "todo", "display_name": "To Do", "sort_order": 0},
            {"status_key": "impl", "display_name": "Implement", "sort_order": 1},
        ],
        transitions=[
            {
                "from_status_key": "todo",
                "to_status_key": "impl",
                "requires_claim": False,
                "requires_approval": False,
            }
        ],
    )

    initial_state = kanban_db.get_card_workflow_state(sample_card["id"])
    transitioned = kanban_db.transition_card_workflow(
        card_id=sample_card["id"],
        to_status_key="impl",
        actor="builder",
        expected_version=initial_state["version"],
        idempotency_key="idempotent-transition-1",
        correlation_id="corr-idempotent-transition-1",
        reason="start implementation",
    )
    assert transitioned["workflow_status_key"] == "impl"

    replayed = kanban_db.transition_card_workflow(
        card_id=sample_card["id"],
        to_status_key="impl",
        actor="builder",
        expected_version=initial_state["version"],
        idempotency_key="idempotent-transition-1",
        correlation_id="corr-idempotent-transition-1",
        reason="start implementation",
    )
    assert replayed["version"] == transitioned["version"]
    assert replayed["workflow_status_key"] == transitioned["workflow_status_key"]

    events = kanban_db.list_card_workflow_events(card_id=sample_card["id"])
    transition_events = [event for event in events if event["event_type"] == "workflow_transitioned"]
    assert len(transition_events) == 1
