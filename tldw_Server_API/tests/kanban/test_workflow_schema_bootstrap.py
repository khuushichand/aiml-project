"""Workflow schema bootstrap tests for KanbanDB."""

import sqlite3

import pytest

from tldw_Server_API.app.core.DB_Management.Kanban_DB import KanbanDB


REQUIRED_WORKFLOW_TABLES = {
    "board_workflow_policies",
    "board_workflow_statuses",
    "board_workflow_transitions",
    "kanban_card_workflow_state",
    "kanban_card_workflow_events",
    "kanban_card_workflow_approvals",
}


def test_workflow_tables_exist_after_db_init(kanban_db: KanbanDB) -> None:
    """KanbanDB schema bootstrap should create workflow control tables."""
    conn = sqlite3.connect(kanban_db.db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    finally:
        conn.close()

    table_names = {row[0] for row in rows}
    missing_tables = REQUIRED_WORKFLOW_TABLES - table_names

    assert not missing_tables, f"Missing workflow tables: {sorted(missing_tables)}"  # nosec B101


def test_workflow_status_foreign_keys_enforced(
    kanban_db: KanbanDB,
    sample_board: dict[str, object],
    sample_card: dict[str, object],
) -> None:
    """Workflow status references must reject unknown status keys."""
    conn = sqlite3.connect(kanban_db.db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            "INSERT INTO board_workflow_policies (board_id) VALUES (?)",
            (sample_board["id"],),
        )
        policy_id = conn.execute(
            "SELECT id FROM board_workflow_policies WHERE board_id = ?",
            (sample_board["id"],),
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO board_workflow_statuses (policy_id, status_key, display_name) VALUES (?, ?, ?)",
            (policy_id, "todo", "To Do"),
        )
        conn.execute(
            "INSERT INTO board_workflow_statuses (policy_id, status_key, display_name) VALUES (?, ?, ?)",
            (policy_id, "impl", "Implement"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO board_workflow_transitions (policy_id, from_status_key, to_status_key) VALUES (?, ?, ?)",
                (policy_id, "todo", "missing"),
            )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO kanban_card_workflow_state (card_id, policy_id, workflow_status_key) VALUES (?, ?, ?)",
                (sample_card["id"], policy_id, "missing"),
            )

        conn.execute(
            "INSERT INTO board_workflow_transitions (policy_id, from_status_key, to_status_key) VALUES (?, ?, ?)",
            (policy_id, "todo", "impl"),
        )
        conn.execute(
            "INSERT INTO kanban_card_workflow_state (card_id, policy_id, workflow_status_key) VALUES (?, ?, ?)",
            (sample_card["id"], policy_id, "todo"),
        )
    finally:
        conn.close()
