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
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class UsageEvent:
    user_id: str
    type: str
    resource_id: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    timestamp: str | None = None


@dataclass
class SemanticMemory:
    user_id: str
    content: str
    tags: list[str] | None = None
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
        except Exception as pragma_error:
            _ = pragma_error  # proceed with defaults if pragmas fail
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
                        proactive_enabled INTEGER NOT NULL DEFAULT 1,
                        proactive_frequency TEXT NOT NULL DEFAULT 'normal',
                        proactive_types TEXT,
                        quiet_hours_start TEXT,
                        quiet_hours_end TEXT,
                        response_style TEXT NOT NULL DEFAULT 'balanced',
                        preferred_format TEXT NOT NULL DEFAULT 'auto',
                        session_continuity_enabled INTEGER NOT NULL DEFAULT 1,
                        session_summaries_enabled INTEGER NOT NULL DEFAULT 1,
                        purged_at TEXT,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS usage_events (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        type TEXT NOT NULL,
                        resource_id TEXT,
                        tags TEXT,
                        metadata TEXT,
                        FOREIGN KEY (user_id) REFERENCES profiles(user_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_usage_user_ts ON usage_events(user_id, timestamp DESC);

                    CREATE TABLE IF NOT EXISTS semantic_memories (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT,
                        pinned INTEGER NOT NULL DEFAULT 0,
                        hidden INTEGER NOT NULL DEFAULT 0,
                        last_validated TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES profiles(user_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_semantic_user ON semantic_memories(user_id);

                    CREATE TABLE IF NOT EXISTS episodic_memories (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        event_id TEXT,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES profiles(user_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_episodic_user_ts ON episodic_memories(user_id, timestamp DESC);

                    CREATE TABLE IF NOT EXISTS topic_profiles (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        label TEXT NOT NULL,
                        score REAL NOT NULL DEFAULT 0,
                        centroid_embedding BLOB,
                        last_seen TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES profiles(user_id)
                    );
                    CREATE INDEX IF NOT EXISTS idx_topics_user ON topic_profiles(user_id);
                    CREATE INDEX IF NOT EXISTS idx_topics_score ON topic_profiles(user_id, score DESC);
                    """
                )
                conn.commit()
            finally:
                conn.close()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Add columns that may be missing in databases created before schema updates."""
        migrations: list[tuple[str, str, str]] = [
            # (table, column, column_def)
            ("profiles", "proactive_enabled", "INTEGER NOT NULL DEFAULT 1"),
            ("profiles", "proactive_frequency", "TEXT NOT NULL DEFAULT 'normal'"),
            ("profiles", "proactive_types", "TEXT"),
            ("profiles", "quiet_hours_start", "TEXT"),
            ("profiles", "quiet_hours_end", "TEXT"),
            ("profiles", "response_style", "TEXT NOT NULL DEFAULT 'balanced'"),
            ("profiles", "preferred_format", "TEXT NOT NULL DEFAULT 'auto'"),
            ("profiles", "session_continuity_enabled", "INTEGER NOT NULL DEFAULT 1"),
            ("profiles", "session_summaries_enabled", "INTEGER NOT NULL DEFAULT 1"),
            ("profiles", "purged_at", "TEXT"),
            ("semantic_memories", "hidden", "INTEGER NOT NULL DEFAULT 0"),
            ("semantic_memories", "last_validated", "TEXT"),
            ("topic_profiles", "centroid_embedding", "BLOB"),
        ]
        with self._lock:
            conn = self._connect()
            try:
                for table, column, col_def in migrations:
                    existing = {
                        row[1]
                        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                    }
                    if column not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
                conn.commit()
            finally:
                conn.close()

    # Profiles
    def get_or_create_profile(self, user_id: str) -> dict[str, Any]:
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

    def update_profile(self, user_id: str, **fields) -> dict[str, Any]:
        # Ensure row exists
        self.get_or_create_profile(user_id)
        if not fields:
            return self.get_or_create_profile(user_id)
        allowed = {
            "enabled", "alpha", "beta", "gamma", "recency_half_life_days",
            "proactive_enabled", "proactive_frequency", "proactive_types",
            "quiet_hours_start", "quiet_hours_end", "response_style",
            "preferred_format", "session_continuity_enabled",
            "session_summaries_enabled",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_or_create_profile(user_id)

        # Clamp weight fields to [0.0, 1.0]
        for wk in ("alpha", "beta", "gamma"):
            if wk in updates:
                updates[wk] = max(0.0, min(1.0, float(updates[wk])))
        # Normalize alpha+beta+gamma to sum <= 1.0
        weight_keys = [k for k in ("alpha", "beta", "gamma") if k in updates]
        if weight_keys:
            # Merge with existing to check total
            current = self.get_or_create_profile(user_id)
            a = float(updates.get("alpha", current.get("alpha", 0.2)))
            b = float(updates.get("beta", current.get("beta", 0.6)))
            g = float(updates.get("gamma", current.get("gamma", 0.2)))
            total = a + b + g
            if total > 1.0 and total > 0:
                a, b, g = a / total, b / total, g / total
                # When normalizing, write back all three to keep them consistent
                updates["alpha"] = a
                updates["beta"] = b
                updates["gamma"] = g
            else:
                # No normalization needed - write back only changed keys
                if "alpha" in updates:
                    updates["alpha"] = a
                if "beta" in updates:
                    updates["beta"] = b
                if "gamma" in updates:
                    updates["gamma"] = g

        # Clamp recency_half_life_days to [1, 365]
        if "recency_half_life_days" in updates:
            updates["recency_half_life_days"] = max(1, min(365, int(updates["recency_half_life_days"])))

        # Clear purged_at when re-enabling
        if updates.get("enabled") == 1:
            updates["purged_at"] = None

        updates["updated_at"] = _utcnow_iso()
        set_clause = ", ".join([f"{k} = ?" for k in updates])
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
        self.get_or_create_profile(evt.user_id)
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
        self.get_or_create_profile(mem.user_id)
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

    def delete_memory(self, memory_id: str, user_id: str) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "DELETE FROM semantic_memories WHERE id = ? AND user_id = ?",
                    (str(memory_id), str(user_id)),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def get_memory(self, memory_id: str, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT id, content, tags, pinned, hidden, created_at FROM semantic_memories WHERE id = ? AND user_id = ?",
                    (str(memory_id), str(user_id)),
                )
                r = cur.fetchone()
                if not r:
                    return None
                return {
                    "id": r["id"],
                    "type": "semantic",
                    "content": r["content"],
                    "pinned": bool(r["pinned"]),
                    "hidden": bool(r["hidden"]),
                    "tags": (json.loads(r["tags"]) if r["tags"] else None),
                    "timestamp": datetime.fromisoformat(r["created_at"]) if r["created_at"] else None,
                }
            finally:
                conn.close()

    def update_memory(self, memory_id: str, user_id: str, **fields) -> dict[str, Any] | None:
        allowed = {"content", "pinned", "hidden", "tags"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_memory(memory_id, user_id)
        # Serialize tags to JSON
        if "tags" in updates:
            updates["tags"] = json.dumps(updates["tags"]) if updates["tags"] is not None else None
        if "pinned" in updates:
            updates["pinned"] = int(bool(updates["pinned"]))
        if "hidden" in updates:
            updates["hidden"] = int(bool(updates["hidden"]))
        set_clause = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [str(memory_id), str(user_id)]
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    f"UPDATE semantic_memories SET {set_clause} WHERE id = ? AND user_id = ?",
                    params,
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
            finally:
                conn.close()
        return self.get_memory(memory_id, user_id)

    def validate_memories(self, user_id: str, memory_ids: list[str]) -> int:
        """Mark memories as validated by setting last_validated timestamp. Returns count updated."""
        if not memory_ids:
            return 0
        now = _utcnow_iso()
        placeholders = ", ".join(["?"] * len(memory_ids))
        params: list[Any] = [now, str(user_id)] + [str(mid) for mid in memory_ids]
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    f"UPDATE semantic_memories SET last_validated = ? WHERE user_id = ? AND id IN ({placeholders})",
                    params,
                )
                conn.commit()
                return cur.rowcount or 0
            finally:
                conn.close()

    def list_semantic_memories(
        self,
        user_id: str,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
        include_hidden: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses = ["user_id = ?"]
        params: list[Any] = [str(user_id)]
        if not include_hidden:
            clauses.append("hidden = 0")
        if q:
            clauses.append("content LIKE ?")
            params.append(f"%{q}%")
        where = " WHERE " + " AND ".join(clauses)
        sql = f"SELECT id, content, tags, pinned, hidden, created_at FROM semantic_memories{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params_page = params + [int(limit), int(offset)]
        count_sql = f"SELECT COUNT(*) as c FROM semantic_memories{where}"
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(sql, params_page)
                rows = cur.fetchall()
                items: list[dict[str, Any]] = []
                for r in rows:
                    items.append({
                        "id": r["id"],
                        "type": "semantic",
                        "content": r["content"],
                        "pinned": bool(r["pinned"]),
                        "hidden": bool(r["hidden"]),
                        "tags": (json.loads(r["tags"]) if r["tags"] else None),
                        "timestamp": datetime.fromisoformat(r["created_at"]) if r["created_at"] else None,
                    })
                total = int(conn.execute(count_sql, params).fetchone()[0])
                return items, total
            finally:
                conn.close()

    def export_all_memories(self, user_id: str) -> list[dict[str, Any]]:
        """Return all semantic memories for a user (for export)."""
        items, _ = self.list_semantic_memories(user_id, limit=10000, include_hidden=True)
        return items

    def bulk_add_memories(self, user_id: str, memories: list[dict[str, Any]]) -> int:
        """Bulk-insert semantic memories from import data. Returns count inserted."""
        import uuid
        self.get_or_create_profile(user_id)
        count = 0
        with self._lock:
            conn = self._connect()
            try:
                for mem in memories:
                    mid = uuid.uuid4().hex
                    tags_json = json.dumps(mem.get("tags")) if mem.get("tags") else None
                    conn.execute(
                        "INSERT INTO semantic_memories (id, user_id, content, tags, pinned, hidden, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            mid,
                            str(user_id),
                            str(mem.get("content", "")),
                            tags_json,
                            int(bool(mem.get("pinned", False))),
                            int(bool(mem.get("hidden", False))),
                            _utcnow_iso(),
                        ),
                    )
                    count += 1
                conn.commit()
                return count
            finally:
                conn.close()

    # Topics
    def upsert_topic(self, user_id: str, label: str, score: float, last_seen: str | None = None) -> None:
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

    def session_count(self, user_id: str) -> int:
        """Count distinct sessions (unique event timestamps with type containing 'session')."""
        with self._lock:
            conn = self._connect()
            try:
                r = conn.execute(
                    "SELECT COUNT(DISTINCT resource_id) FROM usage_events WHERE user_id = ? AND resource_id IS NOT NULL",
                    (str(user_id),),
                ).fetchone()
                return int(r[0] if r else 0)
            finally:
                conn.close()

    def list_recent_events(self, user_id: str, limit: int = 500) -> list[dict[str, Any]]:
        """Return recent usage events, thread-safe."""
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "SELECT id, timestamp, type, resource_id, tags FROM usage_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (str(user_id), int(limit)),
                )
                rows = cur.fetchall()
                out: list[dict[str, Any]] = []
                for r in rows:
                    tags = None
                    try:
                        tags = json.loads(r["tags"]) if r["tags"] else None
                    except Exception:
                        tags = None
                    out.append({
                        "id": r["id"],
                        "timestamp": r["timestamp"],
                        "type": r["type"],
                        "resource_id": r["resource_id"],
                        "tags": tags or [],
                    })
                return out
            finally:
                conn.close()

    def purge_user(self, user_id: str) -> dict[str, int]:
        with self._lock:
            conn = self._connect()
            try:
                counts: dict[str, int] = {}
                for table in ("usage_events", "semantic_memories", "episodic_memories", "topic_profiles"):
                    cur = conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (str(user_id),))
                    counts[table] = cur.rowcount or 0
                conn.commit()
                # Reset profile to disabled and stamp purged_at
                now = _utcnow_iso()
                conn.execute(
                    "UPDATE profiles SET enabled = 0, purged_at = ?, updated_at = ? WHERE user_id = ?",
                    (now, now, str(user_id)),
                )
                conn.commit()
                return counts
            finally:
                conn.close()
