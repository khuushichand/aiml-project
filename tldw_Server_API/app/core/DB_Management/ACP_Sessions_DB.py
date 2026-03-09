"""SQLite-backed ACP session persistence.

Provides durable storage for ACP session records. Returns plain dicts
to avoid circular imports with the in-memory session store layer.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger

_SCHEMA_VERSION = 2

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    agent_type TEXT NOT NULL DEFAULT 'custom',
    name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    cwd TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_activity_at TEXT,
    message_count INTEGER NOT NULL DEFAULT 0,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    bootstrap_ready INTEGER NOT NULL DEFAULT 1,
    needs_bootstrap INTEGER NOT NULL DEFAULT 0,
    forked_from TEXT,
    tags TEXT NOT NULL DEFAULT '[]',
    mcp_servers TEXT NOT NULL DEFAULT '[]',
    persona_id TEXT,
    workspace_id TEXT,
    workspace_group_id TEXT,
    scope_snapshot_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_forked ON sessions(forked_from);

CREATE TABLE IF NOT EXISTS session_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    message_index INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    raw_data TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_session_idx
    ON session_messages(session_id, message_index);

CREATE TABLE IF NOT EXISTS agent_registry (
    agent_type TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    command TEXT NOT NULL DEFAULT '',
    args TEXT NOT NULL DEFAULT '[]',
    env TEXT NOT NULL DEFAULT '{}',
    requires_api_key TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    install_instructions TEXT NOT NULL DEFAULT '[]',
    docs_url TEXT,
    source TEXT NOT NULL DEFAULT 'api',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Columns that are stored as INTEGER 0/1 but should be returned as bool
_BOOL_FIELDS = frozenset({"bootstrap_ready", "needs_bootstrap"})

# Columns that are stored as JSON TEXT but should be returned as parsed objects
_JSON_FIELDS = frozenset({"tags", "mcp_servers"})


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ACPSessionsDB:
    """SQLite-backed ACP session store."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "..", "Databases", "acp_sessions.db",
            )
        self._db_path = os.path.abspath(db_path)
        self._conn_local = threading.local()
        self._initialized = False
        self._init_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local SQLite connection."""
        conn: sqlite3.Connection | None = getattr(self._conn_local, "conn", None)
        if conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._conn_local.conn = conn
        self._ensure_schema()
        return conn

    def _ensure_schema(self) -> None:
        """Create tables if needed (idempotent, double-checked locking)."""
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            conn: sqlite3.Connection | None = getattr(self._conn_local, "conn", None)
            if conn is None:
                return  # _get_conn will call us again after creating conn
            conn.executescript(_SCHEMA_SQL)
            # Migrate from v1 -> v2: ensure agent_registry table exists
            current_version = conn.execute("PRAGMA user_version").fetchone()[0]
            if current_version < _SCHEMA_VERSION:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS agent_registry (
                        agent_type TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        command TEXT NOT NULL DEFAULT '',
                        args TEXT NOT NULL DEFAULT '[]',
                        env TEXT NOT NULL DEFAULT '{}',
                        requires_api_key TEXT,
                        is_default INTEGER NOT NULL DEFAULT 0,
                        install_instructions TEXT NOT NULL DEFAULT '[]',
                        docs_url TEXT,
                        source TEXT NOT NULL DEFAULT 'api',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
            conn.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            conn.commit()
            self._initialized = True
            logger.debug("ACP Sessions DB schema initialized at {}", self._db_path)

    # ------------------------------------------------------------------
    # Row conversion
    # ------------------------------------------------------------------

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict with deserialized fields."""
        d: dict[str, Any] = dict(row)
        for field in _BOOL_FIELDS:
            if field in d:
                d[field] = bool(d[field])
        for field in _JSON_FIELDS:
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        return d

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def register_session(
        self,
        session_id: str,
        user_id: int,
        agent_type: str = "custom",
        name: str = "",
        cwd: str = "",
        tags: list[str] | None = None,
        mcp_servers: list[dict[str, Any]] | None = None,
        persona_id: str | None = None,
        workspace_id: str | None = None,
        workspace_group_id: str | None = None,
        scope_snapshot_id: str | None = None,
        forked_from: str | None = None,
        needs_bootstrap: bool = False,
    ) -> dict[str, Any]:
        """Insert a new session record and return it as a dict."""
        conn = self._get_conn()
        now = _utcnow_iso()
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, user_id, agent_type, name, status, cwd,
                created_at, last_activity_at,
                tags, mcp_servers,
                persona_id, workspace_id, workspace_group_id, scope_snapshot_id,
                forked_from, needs_bootstrap
            ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id, user_id, agent_type, name, cwd,
                now, now,
                json.dumps(tags or []),
                json.dumps(mcp_servers or []),
                persona_id, workspace_id, workspace_group_id, scope_snapshot_id,
                forked_from, int(needs_bootstrap),
            ),
        )
        conn.commit()
        return self.get_session(session_id)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Fetch a single session by ID, or None if not found."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def close_session(self, session_id: str) -> None:
        """Mark a session as closed."""
        self.set_session_status(session_id, "closed")

    def set_session_status(self, session_id: str, status: str) -> None:
        """Update the status of a session."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET status = ?, last_activity_at = ? WHERE session_id = ?",
            (status, _utcnow_iso(), session_id),
        )
        conn.commit()

    def update_activity(self, session_id: str) -> None:
        """Touch the last_activity_at timestamp."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET last_activity_at = ? WHERE session_id = ?",
            (_utcnow_iso(), session_id),
        )
        conn.commit()

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if a row was actually removed."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_sessions(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List sessions with optional filters. Returns (rows, total_count)."""
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if agent_type is not None:
            conditions.append("agent_type = ?")
            params.append(agent_type)

        where = " AND ".join(conditions) if conditions else "1=1"

        # Total count
        count_row = conn.execute(
            f"SELECT COUNT(*) FROM sessions WHERE {where}", params
        ).fetchone()
        total = count_row[0] if count_row else 0

        # Paginated results
        rows = conn.execute(
            f"SELECT * FROM sessions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        return [self._row_to_dict(r) for r in rows], total

    # ------------------------------------------------------------------
    # Text normalization (local helper — no external imports)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text_content(value: Any) -> str | None:
        """Extract plain text from various content representations.

        Handles:
        - str: return stripped (or None if empty)
        - list: join text parts from content block lists
        - dict with type in (text, input_text, output_text): return text field
        - dict with content/text keys: recurse
        """
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    t = item.get("type", "")
                    if t in ("text", "input_text", "output_text"):
                        txt = item.get("text", "")
                        if txt:
                            parts.append(str(txt))
                    else:
                        # Try content/text keys
                        for key in ("content", "text"):
                            if key in item:
                                resolved = ACPSessionsDB._normalize_text_content(item[key])
                                if resolved:
                                    parts.append(resolved)
                                break
            return "\n".join(parts) if parts else None
        if isinstance(value, dict):
            d = value
            t = d.get("type", "")
            if t in ("text", "input_text", "output_text"):
                txt = d.get("text", "")
                return str(txt).strip() if txt else None
            for key in ("content", "text"):
                if key in d:
                    return ACPSessionsDB._normalize_text_content(d[key])
        return str(value).strip() or None

    # ------------------------------------------------------------------
    # Message recording
    # ------------------------------------------------------------------

    def record_prompt(
        self,
        session_id: str,
        prompt: list[dict[str, Any]],
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Record a prompt+response exchange and update token counters.

        Returns a dict with prompt_tokens, completion_tokens, total_tokens
        for this exchange, or None if the session does not exist.
        """
        conn = self._get_conn()
        session = self.get_session(session_id)
        if session is None:
            return None

        now = _utcnow_iso()

        # Determine current max message_index for this session
        row = conn.execute(
            "SELECT COALESCE(MAX(message_index), -1) FROM session_messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        next_idx: int = row[0] + 1 if row else 0

        inserted = 0
        # Insert user messages from prompt
        for msg in prompt:
            role = msg.get("role", "user")
            content = self._normalize_text_content(msg.get("content")) or ""
            conn.execute(
                "INSERT INTO session_messages (session_id, message_index, role, content, timestamp, raw_data)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, next_idx, role, content, now, json.dumps(msg)),
            )
            next_idx += 1
            inserted += 1

        # Insert assistant response
        assistant_text = self._normalize_text_content(result.get("content")) or ""
        conn.execute(
            "INSERT INTO session_messages (session_id, message_index, role, content, timestamp, raw_data)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, next_idx, "assistant", assistant_text, now, json.dumps(result)),
        )
        inserted += 1

        # Extract token usage
        usage = result.get("usage") or {}
        p_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        c_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        t_tokens = p_tokens + c_tokens

        # Update session counters
        conn.execute(
            """
            UPDATE sessions SET
                message_count = message_count + ?,
                prompt_tokens = prompt_tokens + ?,
                completion_tokens = completion_tokens + ?,
                total_tokens = total_tokens + ?,
                last_activity_at = ?
            WHERE session_id = ?
            """,
            (inserted, p_tokens, c_tokens, t_tokens, now, session_id),
        )
        conn.commit()

        return {
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
            "total_tokens": t_tokens,
        }

    def get_messages(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return messages for a session ordered by message_index."""
        conn = self._get_conn()
        sql = (
            "SELECT role, content, timestamp, raw_data FROM session_messages"
            " WHERE session_id = ? ORDER BY message_index"
        )
        params: list[Any] = [session_id]
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            sql += " LIMIT -1 OFFSET ?"
            params.append(offset)

        rows = conn.execute(sql, params).fetchall()
        results: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if d.get("raw_data"):
                try:
                    d["raw_data"] = json.loads(d["raw_data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    def update_token_usage(
        self,
        session_id: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Directly increment token counters for a session."""
        conn = self._get_conn()
        total = prompt_tokens + completion_tokens
        conn.execute(
            """
            UPDATE sessions SET
                prompt_tokens = prompt_tokens + ?,
                completion_tokens = completion_tokens + ?,
                total_tokens = total_tokens + ?,
                last_activity_at = ?
            WHERE session_id = ?
            """,
            (prompt_tokens, completion_tokens, total, _utcnow_iso(), session_id),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Fork
    # ------------------------------------------------------------------

    def fork_session(
        self,
        source_session_id: str,
        new_session_id: str,
        message_index: int,
        user_id: int,
        name: str | None = None,
    ) -> dict[str, Any] | None:
        """Fork a session, copying messages up to *message_index* (inclusive).

        Returns the new session dict, or None if the source does not exist
        or is not owned by *user_id*.
        """
        source = self.get_session(source_session_id)
        if source is None or source["user_id"] != user_id:
            return None

        # Create new session copying key fields from source
        self.register_session(
            session_id=new_session_id,
            user_id=user_id,
            agent_type=source.get("agent_type", "custom"),
            name=name or source.get("name", ""),
            cwd=source.get("cwd", ""),
            tags=source.get("tags"),
            mcp_servers=source.get("mcp_servers"),
            persona_id=source.get("persona_id"),
            workspace_id=source.get("workspace_id"),
            workspace_group_id=source.get("workspace_group_id"),
            scope_snapshot_id=source.get("scope_snapshot_id"),
            forked_from=source_session_id,
            needs_bootstrap=True,
        )

        # Copy messages from source up to message_index (inclusive)
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT message_index, role, content, timestamp, raw_data"
            " FROM session_messages WHERE session_id = ? AND message_index <= ?"
            " ORDER BY message_index",
            (source_session_id, message_index),
        ).fetchall()

        for r in rows:
            conn.execute(
                "INSERT INTO session_messages (session_id, message_index, role, content, timestamp, raw_data)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (new_session_id, r["message_index"], r["role"], r["content"],
                 r["timestamp"], r["raw_data"]),
            )

        # Update message_count on the new session
        if rows:
            conn.execute(
                "UPDATE sessions SET message_count = ? WHERE session_id = ?",
                (len(rows), new_session_id),
            )
            conn.commit()

        return self.get_session(new_session_id)

    def get_fork_lineage(
        self,
        session_id: str,
        *,
        max_depth: int = 50,
    ) -> list[str]:
        """Walk the forked_from chain and return ancestor IDs (oldest first)."""
        conn = self._get_conn()
        ancestors: list[str] = []
        seen: set[str] = {session_id}
        current = session_id

        for _ in range(max_depth):
            row = conn.execute(
                "SELECT forked_from FROM sessions WHERE session_id = ?",
                (current,),
            ).fetchone()
            if row is None or row["forked_from"] is None:
                break
            parent = row["forked_from"]
            if parent in seen:
                break  # cycle guard
            seen.add(parent)
            ancestors.append(parent)
            current = parent

        ancestors.reverse()
        return ancestors

    # ------------------------------------------------------------------
    # Quota configuration
    # ------------------------------------------------------------------

    def configure_quotas(
        self,
        *,
        max_concurrent_per_user: int = 5,
        max_tokens_per_session: int = 1_000_000,
        session_ttl_seconds: int = 86400,
        max_session_duration_seconds: int = 14400,
    ) -> None:
        """Store quota limits as instance attributes (from server config)."""
        self._max_concurrent_per_user = max_concurrent_per_user
        self._max_tokens_per_session = max_tokens_per_session
        self._session_ttl_seconds = session_ttl_seconds
        self._max_session_duration_seconds = max_session_duration_seconds

    def check_session_quota(self, user_id: int) -> dict[str, Any] | None:
        """Check if user has reached the concurrent session limit.

        Returns an error dict if quota exceeded, None otherwise.
        """
        limit = getattr(self, "_max_concurrent_per_user", 5)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()
        count = row[0] if row else 0
        if count >= limit:
            return {
                "code": "quota_exceeded",
                "message": f"Max concurrent sessions ({limit}) exceeded",
                "current": count,
                "limit": limit,
            }
        return None

    def check_token_quota(self, session_id: str) -> dict[str, Any] | None:
        """Check if session has exceeded the token limit.

        Returns an error dict if quota exceeded, None if under limit
        or session not found.
        """
        limit = getattr(self, "_max_tokens_per_session", 1_000_000)
        conn = self._get_conn()
        row = conn.execute(
            "SELECT total_tokens FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        if row[0] >= limit:
            return {
                "code": "token_quota_exceeded",
                "message": f"Session token limit ({limit}) exceeded",
                "current": row[0],
                "limit": limit,
            }
        return None

    def get_quota_status(
        self, user_id: int, session_id: str | None = None
    ) -> dict[str, Any]:
        """Return current quota usage stats."""
        conn = self._get_conn()
        concurrent_limit = getattr(self, "_max_concurrent_per_user", 5)
        row = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()
        active_count = row[0] if row else 0

        result: dict[str, Any] = {
            "concurrent_sessions": {
                "current": active_count,
                "limit": concurrent_limit,
            },
        }

        if session_id is not None:
            token_limit = getattr(self, "_max_tokens_per_session", 1_000_000)
            sess_row = conn.execute(
                "SELECT total_tokens FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            total = sess_row[0] if sess_row else 0
            result["session_tokens"] = {
                "current": total,
                "limit": token_limit,
            }

        return result

    def evict_expired_sessions(self) -> int:
        """Close active sessions that have exceeded TTL or max duration.

        Returns the number of sessions evicted.
        """
        ttl = getattr(self, "_session_ttl_seconds", 86400)
        max_dur = getattr(self, "_max_session_duration_seconds", 14400)
        # Use the smaller of the two as the effective cutoff
        cutoff_seconds = min(ttl, max_dur)

        conn = self._get_conn()
        now = datetime.now(timezone.utc)

        # Fetch active sessions and check expiry in Python
        rows = conn.execute(
            "SELECT session_id, created_at FROM sessions WHERE status = 'active'"
        ).fetchall()

        expired_ids: list[str] = []
        for r in rows:
            try:
                created = datetime.fromisoformat(r["created_at"])
            except (ValueError, TypeError):
                continue
            age = (now - created).total_seconds()
            if age >= cutoff_seconds:
                expired_ids.append(r["session_id"])

        if not expired_ids:
            return 0

        now_iso = _utcnow_iso()
        for sid in expired_ids:
            conn.execute(
                "UPDATE sessions SET status = 'closed', last_activity_at = ? WHERE session_id = ?",
                (now_iso, sid),
            )
        conn.commit()
        logger.info("Evicted {} expired ACP sessions", len(expired_ids))
        return len(expired_ids)

    # ------------------------------------------------------------------
    # Agent Registry CRUD
    # ------------------------------------------------------------------

    def save_agent_entry(self, entry_dict: dict[str, Any]) -> dict[str, Any]:
        """Insert or replace an agent registry entry. Returns the saved entry."""
        conn = self._get_conn()
        now = _utcnow_iso()
        agent_type = entry_dict.get("agent_type", "")
        name = entry_dict.get("name", "")
        description = entry_dict.get("description", "")
        command = entry_dict.get("command", "")
        args = entry_dict.get("args", "[]")
        env = entry_dict.get("env", "{}")
        requires_api_key = entry_dict.get("requires_api_key")
        is_default = int(entry_dict.get("is_default", 0))
        install_instructions = entry_dict.get("install_instructions", "[]")
        docs_url = entry_dict.get("docs_url")
        source = entry_dict.get("source", "api")

        conn.execute(
            """
            INSERT OR REPLACE INTO agent_registry (
                agent_type, name, description, command, args, env,
                requires_api_key, is_default, install_instructions, docs_url,
                source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_type, name, description, command, args, env,
                requires_api_key, is_default, install_instructions, docs_url,
                source, now, now,
            ),
        )
        conn.commit()
        return self.get_agent_entry(agent_type)  # type: ignore[return-value]

    def delete_agent_entry(self, agent_type: str) -> bool:
        """Delete an agent entry. Returns True if a row was removed."""
        conn = self._get_conn()
        cursor = conn.execute(
            "DELETE FROM agent_registry WHERE agent_type = ?", (agent_type,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def list_agent_entries(self, source: str | None = None) -> list[dict[str, Any]]:
        """List agent entries, optionally filtered by source."""
        conn = self._get_conn()
        if source is not None:
            rows = conn.execute(
                "SELECT * FROM agent_registry WHERE source = ? ORDER BY name",
                (source,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_registry ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_agent_entry(self, agent_type: str) -> dict[str, Any] | None:
        """Fetch a single agent entry by type, or None."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM agent_registry WHERE agent_type = ?", (agent_type,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the thread-local connection."""
        conn: sqlite3.Connection | None = getattr(self._conn_local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            self._conn_local.conn = None
