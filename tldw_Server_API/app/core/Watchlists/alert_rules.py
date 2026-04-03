"""
Watchlist Alert Rules — Evaluation Engine

Evaluates user-defined alert rules against completed watchlist run statistics
and creates notifications when conditions are met.

Supported condition types:
- no_items: Run produced zero items
- error_rate_above: Error rate exceeds threshold (0.0–1.0)
- items_below: Total items below threshold
- items_above: Total items above threshold (unusual activity)
- run_failed: Run ended with failed status
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.DB_Management.watchlist_alert_rules_db import (
    ensure_watchlist_alert_rules_table,
)


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

class AlertConditionType(str, Enum):
    NO_ITEMS = "no_items"
    ERROR_RATE_ABOVE = "error_rate_above"
    ITEMS_BELOW = "items_below"
    ITEMS_ABOVE = "items_above"
    RUN_FAILED = "run_failed"


ALERT_CONDITION_TYPE_VALUES = frozenset(condition.value for condition in AlertConditionType)
DEFAULT_ERROR_RATE_THRESHOLD = 0.5
DEFAULT_ITEMS_BELOW_THRESHOLD = 1
DEFAULT_ITEMS_ABOVE_THRESHOLD = 1000


def ensure_alert_rules_table(db_path: str) -> None:
    """Create the alert rules table if it doesn't exist."""
    ensure_watchlist_alert_rules_table(db_path)


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
    _validate_condition_type(condition_type)
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


def get_alert_rule(db_path: str, rule_id: int, user_id: str) -> AlertRule | None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM watchlist_alert_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        ).fetchone()
    if row is None:
        return None
    return _row_to_rule(row)


def update_alert_rule(db_path: str, rule_id: int, user_id: str, **fields: Any) -> AlertRule | None:
    current_rule = get_alert_rule(db_path, rule_id, user_id)
    if current_rule is None:
        return None

    updates = {key: value for key, value in fields.items() if value is not None}
    if not updates:
        return None

    if "condition_type" in updates:
        _validate_condition_type(str(updates["condition_type"]))
    if "condition_value" in updates and isinstance(updates["condition_value"], dict):
        updates["condition_value"] = json.dumps(updates["condition_value"])
    if "enabled" in updates:
        updates["enabled"] = 1 if updates["enabled"] else 0

    updated_at = datetime.now(timezone.utc).isoformat()
    merged_values = {
        "name": updates.get("name", current_rule.name),
        "enabled": updates.get("enabled", 1 if current_rule.enabled else 0),
        "condition_type": updates.get("condition_type", current_rule.condition_type),
        "condition_value": updates.get("condition_value", current_rule.condition_value),
        "severity": updates.get("severity", current_rule.severity),
        "job_id": updates.get("job_id", current_rule.job_id),
    }
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE watchlist_alert_rules
            SET name = ?, enabled = ?, condition_type = ?, condition_value = ?,
                severity = ?, job_id = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                merged_values["name"],
                merged_values["enabled"],
                merged_values["condition_type"],
                merged_values["condition_value"],
                merged_values["severity"],
                merged_values["job_id"],
                updated_at,
                rule_id,
                user_id,
            ),
        )
        if cur.rowcount <= 0:
            return None
    return get_alert_rule(db_path, rule_id, user_id)


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

        if rule.condition_type == AlertConditionType.NO_ITEMS.value:
            match = items_ingested == 0
            detail = f"Run produced 0 items (found {items_found})"

        elif rule.condition_type == AlertConditionType.ERROR_RATE_ABOVE.value:
            threshold = _coerce_threshold(
                cv.get("threshold", DEFAULT_ERROR_RATE_THRESHOLD),
                default=DEFAULT_ERROR_RATE_THRESHOLD,
                caster=float,
                rule=rule,
            )
            if threshold is None:
                detail = "Invalid threshold configured for error_rate_above"
                continue
            match = error_rate > threshold
            detail = f"Error rate {error_rate:.0%} exceeds {threshold:.0%} threshold"

        elif rule.condition_type == AlertConditionType.ITEMS_BELOW.value:
            threshold = _coerce_threshold(
                cv.get("threshold", DEFAULT_ITEMS_BELOW_THRESHOLD),
                default=DEFAULT_ITEMS_BELOW_THRESHOLD,
                caster=int,
                rule=rule,
            )
            if threshold is None:
                detail = "Invalid threshold configured for items_below"
                continue
            match = items_ingested < threshold
            detail = f"Only {items_ingested} items ingested (threshold: {threshold})"

        elif rule.condition_type == AlertConditionType.ITEMS_ABOVE.value:
            threshold = _coerce_threshold(
                cv.get("threshold", DEFAULT_ITEMS_ABOVE_THRESHOLD),
                default=DEFAULT_ITEMS_ABOVE_THRESHOLD,
                caster=int,
                rule=rule,
            )
            if threshold is None:
                detail = "Invalid threshold configured for items_above"
                continue
            match = items_ingested > threshold
            detail = f"{items_ingested} items ingested exceeds {threshold} threshold"

        elif rule.condition_type == AlertConditionType.RUN_FAILED.value:
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


def _validate_condition_type(condition_type: str) -> None:
    if condition_type not in ALERT_CONDITION_TYPE_VALUES:
        raise ValueError(
            f"Invalid condition_type. Must be one of: {', '.join(sorted(ALERT_CONDITION_TYPE_VALUES))}"
        )


def _coerce_threshold(
    raw_value: Any,
    *,
    default: float | int,
    caster: type[float] | type[int],
    rule: AlertRule,
) -> float | int | None:
    value = default if raw_value is None else raw_value
    try:
        return caster(value)
    except (TypeError, ValueError):
        logger.warning(
            "Skipping alert rule {} because threshold {!r} is invalid for condition_type={}",
            rule.id,
            raw_value,
            rule.condition_type,
        )
        return None
