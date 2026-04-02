"""
Watchlist Alert Rules — Evaluation Engine

Evaluates user-defined alert rules against completed watchlist run statistics
and creates notifications when conditions are met.

Supported condition types:
- no_items: Run produced zero items
- error_rate_above: Error rate exceeds threshold (0.0–1.0)
- items_below: Total items below threshold
- items_above: Total items above threshold (unusual activity)
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class AlertRule:
    id: int
    user_id: str
    job_id: int | None  # None = applies to all jobs
    name: str
    enabled: bool
    condition_type: str
    condition_value: str  # JSON
    severity: str  # info, warning, error
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

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


def ensure_alert_rules_table(db_path: str) -> None:
    """Create the alert rules table if it doesn't exist."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ALERT_RULES_TABLE_SQL)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def list_alert_rules(db_path: str, user_id: str, job_id: int | None = None) -> list[AlertRule]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if job_id is not None:
            rows = conn.execute(
                "SELECT * FROM watchlist_alert_rules WHERE user_id = ? AND (job_id = ? OR job_id IS NULL) ORDER BY created_at DESC",
                (user_id, job_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM watchlist_alert_rules WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [_row_to_rule(r) for r in rows]


def create_alert_rule(
    db_path: str,
    user_id: str,
    name: str,
    condition_type: str,
    condition_value: dict[str, Any] | None = None,
    job_id: int | None = None,
    severity: str = "warning",
) -> AlertRule:
    now = datetime.now(timezone.utc).isoformat()
    cv = json.dumps(condition_value or {})
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO watchlist_alert_rules
               (user_id, job_id, name, enabled, condition_type, condition_value, severity, created_at, updated_at)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)""",
            (user_id, job_id, name, condition_type, cv, severity, now, now),
        )
        return AlertRule(
            id=cur.lastrowid or 0,
            user_id=user_id,
            job_id=job_id,
            name=name,
            enabled=True,
            condition_type=condition_type,
            condition_value=cv,
            severity=severity,
            created_at=now,
            updated_at=now,
        )


def update_alert_rule(db_path: str, rule_id: int, user_id: str, **fields: Any) -> bool:
    allowed = {"name", "enabled", "condition_type", "condition_value", "severity", "job_id"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return False
    if "condition_value" in updates and isinstance(updates["condition_value"], dict):
        updates["condition_value"] = json.dumps(updates["condition_value"])
    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            f"UPDATE watchlist_alert_rules SET {set_clause} WHERE id = ? AND user_id = ?",
            (*updates.values(), rule_id, user_id),
        )
        return cur.rowcount > 0


def delete_alert_rule(db_path: str, rule_id: int, user_id: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM watchlist_alert_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_rules_for_run(
    db_path: str,
    user_id: str,
    job_id: int,
    run_id: int,
    stats: dict[str, Any],
    status: str,
) -> list[dict[str, Any]]:
    """Evaluate all matching alert rules against a completed run.

    Returns a list of triggered alert dicts with:
    - rule: the AlertRule that triggered
    - notification_kwargs: dict ready to pass to create_user_notification()
    """
    rules = list_alert_rules(db_path, user_id, job_id=job_id)
    triggered: list[dict[str, Any]] = []

    items_found = stats.get("items_found", 0)
    items_ingested = stats.get("items_ingested", 0)
    error_rate = 1.0 - (items_ingested / items_found) if items_found > 0 else 0.0

    for rule in rules:
        if not rule.enabled:
            continue

        try:
            cv = json.loads(rule.condition_value)
        except (json.JSONDecodeError, TypeError):
            cv = {}

        match = False
        detail = ""

        if rule.condition_type == "no_items":
            match = items_ingested == 0
            detail = f"Run produced 0 items (found {items_found})"

        elif rule.condition_type == "error_rate_above":
            threshold = float(cv.get("threshold", 0.5))
            match = error_rate > threshold
            detail = f"Error rate {error_rate:.0%} exceeds {threshold:.0%} threshold"

        elif rule.condition_type == "items_below":
            threshold = int(cv.get("threshold", 1))
            match = items_ingested < threshold
            detail = f"Only {items_ingested} items ingested (threshold: {threshold})"

        elif rule.condition_type == "items_above":
            threshold = int(cv.get("threshold", 1000))
            match = items_ingested > threshold
            detail = f"{items_ingested} items ingested exceeds {threshold} threshold"

        elif rule.condition_type == "run_failed":
            match = status == "failed"
            detail = f"Run failed: {stats.get('error_msg', 'unknown error')}"

        if match:
            triggered.append({
                "rule": rule,
                "notification_kwargs": {
                    "kind": "watchlist_alert",
                    "title": f"Alert: {rule.name}",
                    "message": detail,
                    "severity": rule.severity,
                    "source_job_id": str(job_id),
                    "source_domain": "watchlists",
                    "source_job_type": "watchlist_run",
                    "link_type": "watchlist_run",
                    "link_id": str(run_id),
                    "dedupe_key": f"watchlist-alert:{rule.id}:{run_id}",
                },
            })

    return triggered


def _row_to_rule(row: sqlite3.Row) -> AlertRule:
    return AlertRule(
        id=row["id"],
        user_id=row["user_id"],
        job_id=row["job_id"],
        name=row["name"],
        enabled=bool(row["enabled"]),
        condition_type=row["condition_type"],
        condition_value=row["condition_value"],
        severity=row["severity"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
