"""
Billing event audit trail.

Records all billing-related events for finance team queryability.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from loguru import logger


BILLING_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id INTEGER,
    amount_cents INTEGER,
    currency TEXT DEFAULT 'usd',
    description TEXT,
    stripe_event_id TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
)
"""


class BillingAuditLogger:
    """Logs billing events to a SQLite-backed audit table."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the billing_audit_log table if it does not exist."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(BILLING_AUDIT_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def log_event(
        self,
        event_type: str,
        *,
        user_id: int | None = None,
        amount_cents: int = 0,
        currency: str = "usd",
        description: str = "",
        stripe_event_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Record a billing event and return the row id."""
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute(
                "INSERT INTO billing_audit_log "
                "(event_type, user_id, amount_cents, currency, description, "
                "stripe_event_id, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_type,
                    user_id,
                    amount_cents,
                    currency,
                    description,
                    stripe_event_id,
                    json.dumps(metadata) if metadata else None,
                    now,
                ),
            )
            conn.commit()
            row_id = cursor.lastrowid
        finally:
            conn.close()
        logger.debug("Billing audit event logged: type={}, row_id={}", event_type, row_id)
        return row_id  # type: ignore[return-value]

    def query_events(
        self,
        *,
        user_id: int | None = None,
        event_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query billing audit events with optional filters.

        Args:
            user_id: Filter by user.
            event_type: Filter by event type string.
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            List of event dicts, newest first.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            sql = "SELECT * FROM billing_audit_log WHERE 1=1"
            params: list[Any] = []
            if user_id is not None:
                sql += " AND user_id = ?"
                params.append(user_id)
            if event_type:
                sql += " AND event_type = ?"
                params.append(event_type)
            sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]
