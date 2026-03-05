"""Workflow projection strictness regression tests."""

from __future__ import annotations

from typing import Any

import pytest

from tldw_Server_API.app.core.DB_Management.Kanban_DB import ConflictError, KanbanDB


def test_projection_fails_when_target_list_archived(
    kanban_db: KanbanDB,
    sample_board: dict[str, Any],
    sample_card: dict[str, Any],
) -> None:
    """Strict projection should block transition when mapped list target is archived."""
    target_list = kanban_db.create_list(
        board_id=sample_board["id"],
        name="Implementation List",
        client_id="impl-list-client-1",
    )
    kanban_db.archive_list(target_list["id"], archive=True)

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
                "auto_move_list_id": target_list["id"],
            }
        ],
        strict_projection=True,
    )

    state = kanban_db.get_card_workflow_state(sample_card["id"])
    with pytest.raises(ConflictError, match="projection_failed"):
        kanban_db.transition_card_workflow(
            card_id=sample_card["id"],
            to_status_key="impl",
            actor="builder",
            expected_version=state["version"],
            idempotency_key="projection-failure-1",
            correlation_id="corr-projection-failure-1",
            reason="attempt projected move to archived list",
        )
