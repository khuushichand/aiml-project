from __future__ import annotations

"""
TopicMonitoring_DB
Lightweight SQLite wrapper for topic monitoring alerts.

Table: topic_alerts
Columns:
  - id INTEGER PRIMARY KEY AUTOINCREMENT
  - created_at TEXT (ISO 8601 UTC)
  - user_id TEXT
  - scope_type TEXT  -- 'user' | 'team' | 'org'
  - scope_id TEXT
  - source TEXT       -- 'chat.input' | 'chat.output' | 'ingestion' | 'notes' | 'rag'
  - watchlist_id TEXT
  - rule_category TEXT
  - rule_severity TEXT
  - pattern TEXT
  - text_snippet TEXT
  - metadata TEXT     -- JSON string
  - is_read INTEGER DEFAULT 0
  - read_at TEXT NULL

This module intentionally keeps SQL usage encapsulated within DB_Management, per project guidelines.
"""

import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TopicAlert:
    user_id: str
    scope_type: str
    scope_id: Optional[str]
    source: str
    watchlist_id: str
    rule_category: Optional[str]
    rule_severity: Optional[str]
    pattern: str
    text_snippet: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    is_read: int = 0
    read_at: Optional[str] = None


class TopicMonitoringDB:
    def __init__(self, db_path: str = "Databases/monitoring_alerts.db") -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        # Pragmas to improve robustness
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
        except Exception:
            pass
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS topic_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        user_id TEXT,
                        scope_type TEXT,
                        scope_id TEXT,
                        source TEXT,
                        watchlist_id TEXT,
                        rule_category TEXT,
                        rule_severity TEXT,
                        pattern TEXT,
                        text_snippet TEXT,
                        metadata TEXT,
                        is_read INTEGER DEFAULT 0,
                        read_at TEXT
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_alerts_created_at ON topic_alerts(created_at)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_alerts_user ON topic_alerts(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_topic_alerts_watch ON topic_alerts(watchlist_id)")
                conn.commit()
            finally:
                conn.close()

    def insert_alert(self, alert: TopicAlert) -> int:
        with self._lock:
            conn = self._connect()
            try:
                created_at = alert.created_at or _utcnow_iso()
                metadata_json = None
                if alert.metadata is not None:
                    try:
                        import json
                        metadata_json = json.dumps(alert.metadata, ensure_ascii=False)
                    except Exception:
                        metadata_json = None
                cur = conn.execute(
                    """
                    INSERT INTO topic_alerts (
                        created_at, user_id, scope_type, scope_id, source, watchlist_id,
                        rule_category, rule_severity, pattern, text_snippet, metadata, is_read, read_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        alert.user_id,
                        alert.scope_type,
                        alert.scope_id,
                        alert.source,
                        alert.watchlist_id,
                        alert.rule_category,
                        alert.rule_severity,
                        alert.pattern,
                        alert.text_snippet,
                        metadata_json,
                        int(alert.is_read or 0),
                        alert.read_at,
                    ),
                )
                conn.commit()
                return int(cur.lastrowid)
            finally:
                conn.close()

    def recent_duplicate_exists(
        self,
        user_id: str,
        watchlist_id: str,
        pattern: str,
        source: str,
        window_seconds: int = 300,
    ) -> bool:
        """Check if an alert for the same (user, watchlist, pattern, source) exists in recent window."""
        # Compute threshold timestamp
        threshold = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """
                    SELECT 1 FROM topic_alerts
                    WHERE user_id = ? AND watchlist_id = ? AND pattern = ? AND source = ?
                      AND created_at >= ?
                    LIMIT 1
                    """,
                    (str(user_id), str(watchlist_id), str(pattern), str(source), threshold),
                )
                row = cur.fetchone()
                return bool(row)
            finally:
                conn.close()

    def list_alerts(
        self,
        user_id: Optional[str] = None,
        since_iso: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(str(user_id))
        if since_iso:
            clauses.append("created_at >= ?")
            params.append(since_iso)
        if unread_only:
            clauses.append("is_read = 0")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"""
            SELECT id, created_at, user_id, scope_type, scope_id, source,
                   watchlist_id, rule_category, rule_severity, pattern, text_snippet, metadata, is_read, read_at
            FROM topic_alerts
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([int(limit), int(offset)])
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, params)
                rows = cur.fetchall()
                out: List[Dict[str, Any]] = []
                for r in rows:
                    item = {k: r[k] for k in r.keys()}
                    out.append(item)
                return out
            finally:
                conn.close()

    def mark_read(self, alert_id: int) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                now_iso = _utcnow_iso()
                cur = conn.execute(
                    "UPDATE topic_alerts SET is_read = 1, read_at = ? WHERE id = ?",
                    (now_iso, int(alert_id)),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()
