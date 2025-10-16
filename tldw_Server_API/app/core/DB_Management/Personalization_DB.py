from __future__ import annotations

"""
Personalization_DB

SQLite wrapper for per-user personalization data:
 - profiles
 - usage_events
 - semantic_memories
 - episodic_memories
 - topic_profiles

This module encapsulates raw SQL per project guidelines.
"""

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UsageEvent:
    user_id: str
    type: str
    resource_id: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


@dataclass
class SemanticMemory:
    user_id: str
    content: str
    tags: Optional[List[str]] = None
    pinned: bool = False


class PersonalizationDB:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
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
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS profiles (
                        user_id TEXT PRIMARY KEY,
                        enabled INTEGER NOT NULL DEFAULT 0,
                        alpha REAL NOT NULL DEFAULT 0.2,
                        beta REAL NOT NULL DEFAULT 0.6,
                        gamma REAL NOT NULL DEFAULT 0.2,
                        recency_half_life_days INTEGER NOT NULL DEFAULT 14,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS usage_events (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        type TEXT NOT NULL,
                        resource_id TEXT,
                        tags TEXT,
                        metadata TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON usage_events(user_id, timestamp DESC);

                    CREATE TABLE IF NOT EXISTS semantic_memories (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT,
                        pinned INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_semantic_user ON semantic_memories(user_id);

                    CREATE TABLE IF NOT EXISTS episodic_memories (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        event_id TEXT,
                        timestamp TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_episodic_user_ts ON episodic_memories(user_id, timestamp DESC);

                    CREATE TABLE IF NOT EXISTS topic_profiles (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        label TEXT NOT NULL,
                        score REAL NOT NULL DEFAULT 0,
                        last_seen TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_topics_user ON topic_profiles(user_id);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    # Profiles
    def get_or_create_profile(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (str(user_id),))
                row = cur.fetchone()
                if row:
                    return {k: row[k] for k in row.keys()}
                now = _utcnow_iso()
                conn.execute(
                    """
                    INSERT INTO profiles (user_id, enabled, alpha, beta, gamma, recency_half_life_days, updated_at)
                    VALUES (?, 0, 0.2, 0.6, 0.2, 14, ?)
                    """,
                    (str(user_id), now),
                )
                conn.commit()
                return {
                    "user_id": str(user_id),
                    "enabled": 0,
                    "alpha": 0.2,
                    "beta": 0.6,
                    "gamma": 0.2,
                    "recency_half_life_days": 14,
                    "updated_at": now,
                }
            finally:
                conn.close()

    def update_profile(self, user_id: str, **fields) -> Dict[str, Any]:
        # Ensure row exists
        self.get_or_create_profile(user_id)
        if not fields:
            return self.get_or_create_profile(user_id)
        allowed = {"enabled", "alpha", "beta", "gamma", "recency_half_life_days"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_or_create_profile(user_id)
        updates["updated_at"] = _utcnow_iso()
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        params = list(updates.values()) + [str(user_id)]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(f"UPDATE profiles SET {set_clause} WHERE user_id = ?", params)
                conn.commit()
            finally:
                conn.close()
        return self.get_or_create_profile(user_id)

    # Usage events
    def insert_usage_event(self, evt: UsageEvent) -> str:
        import uuid
        eid = uuid.uuid4().hex
        ts = evt.timestamp or _utcnow_iso()
        tags_json = json.dumps(evt.tags) if evt.tags else None
        meta_json = json.dumps(evt.metadata) if evt.metadata else None
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO usage_events (id, user_id, timestamp, type, resource_id, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        eid,
                        str(evt.user_id),
                        ts,
                        evt.type,
                        evt.resource_id,
                        tags_json,
                        meta_json,
                    ),
                )
                conn.commit()
                return eid
            finally:
                conn.close()

    # Memories
    def add_semantic_memory(self, mem: SemanticMemory) -> str:
        import uuid
        mid = uuid.uuid4().hex
        tags_json = json.dumps(mem.tags) if mem.tags else None
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO semantic_memories (id, user_id, content, tags, pinned, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (mid, str(mem.user_id), mem.content, tags_json, int(mem.pinned or 0), _utcnow_iso()),
                )
                conn.commit()
                return mid
            finally:
                conn.close()

    def delete_memory(self, memory_id: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute("DELETE FROM semantic_memories WHERE id = ?", (str(memory_id),))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def list_semantic_memories(self, user_id: str, q: Optional[str] = None, limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        clauses = ["user_id = ?"]
        params: List[Any] = [str(user_id)]
        if q:
            clauses.append("content LIKE ?")
            params.append(f"%{q}%")
        where = " WHERE " + " AND ".join(clauses)
        sql = f"SELECT id, content, tags, pinned, created_at FROM semantic_memories{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params_page = params + [int(limit), int(offset)]
        count_sql = f"SELECT COUNT(*) as c FROM semantic_memories{where}"
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, params_page)
                rows = cur.fetchall()
                items: List[Dict[str, Any]] = []
                for r in rows:
                    items.append({
                        "id": r["id"],
                        "type": "semantic",
                        "content": r["content"],
                        "pinned": bool(r["pinned"]),
                        "tags": (json.loads(r["tags"]) if r["tags"] else None),
                        "timestamp": r["created_at"],
                    })
                total = int(conn.execute(count_sql, params).fetchone()[0])
                return items, total
            finally:
                conn.close()

    # Topics
    def upsert_topic(self, user_id: str, label: str, score: float, last_seen: Optional[str] = None) -> None:
        import uuid
        last = last_seen or _utcnow_iso()
        with self._lock:
            conn = self._connect()
            try:
                # Try update first
                cur = conn.execute(
                    "UPDATE topic_profiles SET score = ?, last_seen = ? WHERE user_id = ? AND label = ?",
                    (float(score), last, str(user_id), label),
                )
                if cur.rowcount == 0:
                    conn.execute(
                        "INSERT INTO topic_profiles (id, user_id, label, score, last_seen) VALUES (?, ?, ?, ?, ?)",
                        (uuid.uuid4().hex, str(user_id), label, float(score), last),
                    )
                conn.commit()
            finally:
                conn.close()

    def topic_counts(self, user_id: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                r = conn.execute("SELECT COUNT(*) FROM topic_profiles WHERE user_id = ?", (str(user_id),)).fetchone()
                return int(r[0] if r else 0)
            finally:
                conn.close()

    def memory_counts(self, user_id: str) -> int:
        with self._lock:
            conn = self._connect()
            try:
                r = conn.execute("SELECT COUNT(*) FROM semantic_memories WHERE user_id = ?", (str(user_id),)).fetchone()
                return int(r[0] if r else 0)
            finally:
                conn.close()

    def purge_user(self, user_id: str) -> Dict[str, int]:
        with self._lock:
            conn = self._connect()
            try:
                counts = {}
                for table in ("usage_events", "semantic_memories", "episodic_memories", "topic_profiles"):
                    cur = conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (str(user_id),))
                    counts[table] = cur.rowcount or 0
                conn.commit()
                # Reset profile to disabled
                conn.execute(
                    "UPDATE profiles SET enabled = 0, updated_at = ? WHERE user_id = ?",
                    (_utcnow_iso(), str(user_id)),
                )
                conn.commit()
                return counts
            finally:
                conn.close()
