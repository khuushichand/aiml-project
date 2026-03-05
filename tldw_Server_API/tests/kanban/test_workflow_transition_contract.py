"""Workflow transition safety-contract tests."""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from tldw_Server_API.app.core.DB_Management.Kanban_DB import ConflictError, KanbanDB


def test_transition_requires_lease_and_expected_version(
    kanban_db: KanbanDB,
    sample_board: dict[str, Any],
    sample_card: dict[str, Any],
) -> None:
    """Transitions should enforce lease ownership and optimistic versioning."""
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
                "requires_claim": True,
                "requires_approval": False,
            }
        ],
    )

    initial_state = kanban_db.get_card_workflow_state(sample_card["id"])

    with pytest.raises(ConflictError, match="lease_required"):
        kanban_db.transition_card_workflow(
            card_id=sample_card["id"],
            to_status_key="impl",
            actor="builder",
            expected_version=initial_state["version"],
            idempotency_key="transition-without-lease",
            reason="start implementation",
        )

    kanban_db.claim_card_workflow(
        card_id=sample_card["id"],
        owner="builder",
        lease_ttl_sec=300,
        idempotency_key="claim-builder",
    )

    with pytest.raises(ConflictError, match="version_conflict"):
        kanban_db.transition_card_workflow(
            card_id=sample_card["id"],
            to_status_key="impl",
            actor="builder",
            expected_version=initial_state["version"],
            idempotency_key="transition-wrong-version",
            reason="start implementation",
        )


def test_transition_approval_flow_and_decision(
    kanban_db: KanbanDB,
    sample_board: dict[str, Any],
    sample_card: dict[str, Any],
) -> None:
    """Approval-gated transitions should create pending approvals and route on decision."""
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
                "requires_approval": True,
                "approve_to_status_key": "impl",
                "reject_to_status_key": "todo",
            }
        ],
    )

    initial_state = kanban_db.get_card_workflow_state(sample_card["id"])
    pending_state = kanban_db.transition_card_workflow(
        card_id=sample_card["id"],
        to_status_key="impl",
        actor="planner",
        expected_version=initial_state["version"],
        idempotency_key="approval-request",
        reason="request plan review",
    )

    assert pending_state["workflow_status_key"] == "todo"
    assert pending_state["approval_state"] == "awaiting_approval"
    assert pending_state["pending_transition_id"] is not None

    decided_state = kanban_db.decide_card_workflow_approval(
        card_id=sample_card["id"],
        reviewer="critic",
        decision="approved",
        expected_version=pending_state["version"],
        idempotency_key="approval-decision",
        reason="looks good",
    )

    assert decided_state["workflow_status_key"] == "impl"
    assert decided_state["approval_state"] == "approved"
    assert decided_state["pending_transition_id"] is None

    events = kanban_db.list_card_workflow_events(card_id=sample_card["id"])
    event_types = {event["event_type"] for event in events}
    assert "workflow_approval_requested" in event_types
    assert "workflow_approval_decided" in event_types


def test_stale_claim_listing_and_force_reassign(
    kanban_db: KanbanDB,
    sample_card: dict[str, Any],
) -> None:
    """Stale claim listing should surface expired claims and support force reassign."""
    state = kanban_db.get_card_workflow_state(sample_card["id"])
    claimed = kanban_db.claim_card_workflow(
        card_id=sample_card["id"],
        owner="builder",
        lease_ttl_sec=300,
        idempotency_key="claim-for-stale-test",
    )
    assert claimed["lease_owner"] == "builder"

    conn = sqlite3.connect(kanban_db.db_path)
    try:
        conn.execute(
            "UPDATE kanban_card_workflow_state SET lease_expires_at = ? WHERE card_id = ?",
            ("2000-01-01 00:00:00", sample_card["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    stale_claims = kanban_db.list_stale_workflow_claims()
    stale_card_ids = {claim["card_id"] for claim in stale_claims}
    assert sample_card["id"] in stale_card_ids

    reassigned = kanban_db.force_reassign_workflow_claim(
        card_id=sample_card["id"],
        new_owner="inspector",
        idempotency_key="force-reassign-stale",
        reason="stale claim recovered",
    )
    assert reassigned["lease_owner"] == "inspector"
    assert reassigned["version"] > state["version"]
