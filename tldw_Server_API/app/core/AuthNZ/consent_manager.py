"""
GDPR Article 7 consent record management.

Tracks user consent for data processing with purpose, timestamp, and withdrawal.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from loguru import logger


CONSENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS consent_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    withdrawn_at TEXT,
    ip_address TEXT,
    user_agent TEXT,
    metadata TEXT,
    UNIQUE(user_id, purpose)
)
"""


class ConsentManager:
    """Manages GDPR consent records in a SQLite database."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the consent_records table if it does not exist."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(CONSENT_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def grant_consent(
        self,
        user_id: int,
        purpose: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        """Record that a user granted consent for a purpose.

        If consent was previously withdrawn for the same purpose, re-granting
        replaces the record (via INSERT OR REPLACE on the UNIQUE constraint).
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO consent_records "
                "(user_id, purpose, granted_at, withdrawn_at, ip_address, user_agent) "
                "VALUES (?, ?, ?, NULL, ?, ?)",
                (user_id, purpose, now, ip_address, user_agent),
            )
            conn.commit()
        finally:
            conn.close()
        logger.debug("Consent granted: user_id={}, purpose={}", user_id, purpose)
        return {"user_id": user_id, "purpose": purpose, "granted_at": now}

    def withdraw_consent(self, user_id: int, purpose: str) -> dict[str, Any] | None:
        """Record consent withdrawal.

        Returns the withdrawal record, or ``None`` if there was no active
        consent for the given user/purpose combination.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.execute(
                "UPDATE consent_records SET withdrawn_at = ? "
                "WHERE user_id = ? AND purpose = ? AND withdrawn_at IS NULL",
                (now, user_id, purpose),
            )
            conn.commit()
            changed = cursor.rowcount
        finally:
            conn.close()
        if changed == 0:
            return None
        logger.debug("Consent withdrawn: user_id={}, purpose={}", user_id, purpose)
        return {"user_id": user_id, "purpose": purpose, "withdrawn_at": now}

    def get_user_consents(self, user_id: int) -> list[dict[str, Any]]:
        """Get all consent records for a user, newest first."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM consent_records WHERE user_id = ? ORDER BY granted_at DESC",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def check_consent(self, user_id: int, purpose: str) -> bool:
        """Check if user has active (non-withdrawn) consent for a purpose."""
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT 1 FROM consent_records "
                "WHERE user_id = ? AND purpose = ? AND withdrawn_at IS NULL",
                (user_id, purpose),
            ).fetchone()
        finally:
            conn.close()
        return row is not None
