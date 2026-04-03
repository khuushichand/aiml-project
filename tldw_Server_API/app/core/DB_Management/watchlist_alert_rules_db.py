"""SQLite schema helpers for watchlist alert rules."""

from __future__ import annotations

import sqlite3


ALERT_RULES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS watchlist_alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    job_id INTEGER,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    condition_type TEXT NOT NULL,
    condition_value TEXT NOT NULL DEFAULT '{}',
    severity TEXT NOT NULL DEFAULT 'warning',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alert_rules_user_job
    ON watchlist_alert_rules(user_id, job_id);
"""


def ensure_watchlist_alert_rules_table(db_path: str) -> None:
    """Create the watchlist alert rules table if it does not exist."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ALERT_RULES_TABLE_SQL)
