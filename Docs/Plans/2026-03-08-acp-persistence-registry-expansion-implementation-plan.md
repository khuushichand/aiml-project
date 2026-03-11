# ACP Persistence & Agent Registry Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist ACP sessions to shared SQLite, orchestration to per-user SQLite, unify agent config, add dynamic registration and health monitoring.

**Architecture:** Two new DB modules (`ACP_Sessions_DB.py` for shared session data, `Orchestration_DB.py` for per-user project/task/run data), extended agent registry with setup-guide fields and DB-backed dynamic registration, and a background health monitor.

**Tech Stack:** SQLite (WAL mode), Python dataclasses, FastAPI, pytest, PyYAML

**Design doc:** `Docs/Plans/2026-03-08-acp-persistence-registry-expansion-design.md`

---

## Task 1: ACP Sessions DB — Schema and Core CRUD

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py`

**Step 1: Write the failing test**

```python
# test_acp_sessions_db.py
"""Tests for ACP Sessions SQLite persistence."""
import os
import tempfile
import pytest
from tldw_Server_API.app.core.DB_Management.ACP_Sessions_DB import ACPSessionsDB


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "acp_sessions.db")
        instance = ACPSessionsDB(db_path=path)
        yield instance
        instance.close()


class TestSessionCRUD:
    def test_register_and_get_session(self, db):
        db.register_session(
            session_id="s1",
            user_id=1,
            agent_type="claude_code",
            name="Test Session",
            cwd="/tmp/work",
        )
        rec = db.get_session("s1")
        assert rec is not None
        assert rec.session_id == "s1"
        assert rec.user_id == 1
        assert rec.agent_type == "claude_code"
        assert rec.name == "Test Session"
        assert rec.status == "active"

    def test_get_session_not_found(self, db):
        assert db.get_session("nonexistent") is None

    def test_close_session(self, db):
        db.register_session(session_id="s1", user_id=1)
        db.close_session("s1")
        rec = db.get_session("s1")
        assert rec.status == "closed"

    def test_list_sessions_filters(self, db):
        db.register_session(session_id="s1", user_id=1, agent_type="claude_code")
        db.register_session(session_id="s2", user_id=2, agent_type="codex")
        db.register_session(session_id="s3", user_id=1, agent_type="claude_code")
        db.close_session("s3")

        # Filter by user
        sessions, total = db.list_sessions(user_id=1)
        assert total == 2
        assert len(sessions) == 2

        # Filter by status
        sessions, total = db.list_sessions(user_id=1, status="active")
        assert total == 1
        assert sessions[0].session_id == "s1"

    def test_register_session_with_tags_and_mcp(self, db):
        db.register_session(
            session_id="s1", user_id=1,
            tags=["workflow", "test"],
            mcp_servers=[{"name": "fs", "type": "stdio"}],
        )
        rec = db.get_session("s1")
        assert rec.tags == ["workflow", "test"]
        assert rec.mcp_servers == [{"name": "fs", "type": "stdio"}]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py -x -v`
Expected: FAIL — `ImportError: cannot import name 'ACPSessionsDB'`

**Step 3: Write the implementation**

Create `ACP_Sessions_DB.py` following the `ACP_Audit_DB` pattern. Key structure:

```python
"""SQLite-backed ACP session persistence.

Stores session metadata, messages, agent configs, and permission policies
in a shared database at Databases/acp_sessions.db.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger

# Import SessionRecord and SessionTokenUsage from the existing module
# to preserve the API contract
from tldw_Server_API.app.services.admin_acp_sessions_service import (
    SessionRecord,
    SessionTokenUsage,
)

_SCHEMA_VERSION = 1

_SCHEMA_SQL = """
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
"""


class ACPSessionsDB:
    """SQLite-backed session store."""

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

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._conn_local, "conn", None)
        if conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._conn_local.conn = conn
        return conn

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            conn = self._get_conn()
            conn.executescript(_SCHEMA_SQL)
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            conn.commit()
            self._initialized = True

    def register_session(
        self,
        *,
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
    ) -> SessionRecord:
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO sessions
               (session_id, user_id, agent_type, name, cwd, created_at,
                last_activity_at, tags, mcp_servers, persona_id, workspace_id,
                workspace_group_id, scope_snapshot_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, agent_type, name, cwd, now, now,
             json.dumps(tags or []), json.dumps(mcp_servers or []),
             persona_id, workspace_id, workspace_group_id, scope_snapshot_id),
        )
        conn.commit()
        return self.get_session(session_id)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> SessionRecord | None:
        self._ensure_schema()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def close_session(self, session_id: str) -> None:
        self._ensure_schema()
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE sessions SET status = 'closed', last_activity_at = ? WHERE session_id = ?",
            (now, session_id),
        )
        conn.commit()

    def list_sessions(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        agent_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SessionRecord], int]:
        self._ensure_schema()
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[Any] = []
        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if agent_type:
            conditions.append("agent_type = ?")
            params.append(agent_type)
        where = " AND ".join(conditions) if conditions else "1=1"

        count_row = conn.execute(
            f"SELECT COUNT(*) FROM sessions WHERE {where}", params
        ).fetchone()
        total = count_row[0] if count_row else 0

        rows = conn.execute(
            f"SELECT * FROM sessions WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [self._row_to_record(r) for r in rows], total

    def _row_to_record(self, row: sqlite3.Row) -> SessionRecord:
        usage = SessionTokenUsage(
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            total_tokens=row["total_tokens"],
        )
        return SessionRecord(
            session_id=row["session_id"],
            user_id=row["user_id"],
            agent_type=row["agent_type"],
            name=row["name"],
            status=row["status"],
            cwd=row["cwd"],
            created_at=row["created_at"],
            last_activity_at=row["last_activity_at"],
            message_count=row["message_count"],
            usage=usage,
            tags=json.loads(row["tags"]) if row["tags"] else [],
            mcp_servers=json.loads(row["mcp_servers"]) if row["mcp_servers"] else [],
            persona_id=row["persona_id"],
            workspace_id=row["workspace_id"],
            workspace_group_id=row["workspace_group_id"],
            scope_snapshot_id=row["scope_snapshot_id"],
            bootstrap_ready=bool(row["bootstrap_ready"]),
            needs_bootstrap=bool(row["needs_bootstrap"]),
            forked_from=row["forked_from"],
        )

    def close(self) -> None:
        conn = getattr(self._conn_local, "conn", None)
        if conn:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            self._conn_local.conn = None
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py -x -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py
git commit -m "feat(acp): add ACP Sessions DB with schema and core CRUD"
```

---

## Task 2: ACP Sessions DB — Messages, Token Usage, Fork

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py`

**Step 1: Write the failing tests**

Add to `test_acp_sessions_db.py`:

```python
class TestSessionMessages:
    def test_record_prompt_stores_messages(self, db):
        db.register_session(session_id="s1", user_id=1)
        prompt = [{"role": "user", "content": "Hello"}]
        result = {"content": [{"text": "Hi there"}], "usage": {"input_tokens": 10, "output_tokens": 5}}
        usage = db.record_prompt("s1", prompt, result)
        assert usage is not None
        assert usage.prompt_tokens == 10
        assert usage.completion_tokens == 5

        rec = db.get_session("s1")
        assert rec.message_count == 2
        assert rec.usage.total_tokens == 15

    def test_record_prompt_nonexistent_session(self, db):
        assert db.record_prompt("nope", [], {}) is None

    def test_get_messages(self, db):
        db.register_session(session_id="s1", user_id=1)
        prompt = [{"role": "user", "content": "Hello"}]
        result = {"content": [{"text": "Hi"}], "usage": {}}
        db.record_prompt("s1", prompt, result)
        messages = db.get_messages("s1")
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    def test_get_messages_with_limit(self, db):
        db.register_session(session_id="s1", user_id=1)
        for i in range(5):
            db.record_prompt(
                "s1",
                [{"role": "user", "content": f"msg {i}"}],
                {"content": [{"text": f"reply {i}"}], "usage": {}},
            )
        messages = db.get_messages("s1", limit=4)
        assert len(messages) == 4


class TestForkSession:
    def test_fork_copies_messages(self, db):
        db.register_session(session_id="s1", user_id=1, agent_type="claude_code")
        db.record_prompt(
            "s1",
            [{"role": "user", "content": "Hello"}],
            {"content": [{"text": "Hi"}], "usage": {}},
        )
        db.record_prompt(
            "s1",
            [{"role": "user", "content": "Next"}],
            {"content": [{"text": "OK"}], "usage": {}},
        )
        forked = db.fork_session("s1", "s2", message_index=1, user_id=1)
        assert forked is not None
        assert forked.forked_from == "s1"
        assert forked.agent_type == "claude_code"
        messages = db.get_messages("s2")
        assert len(messages) == 2  # messages 0 and 1

    def test_fork_nonexistent_source(self, db):
        assert db.fork_session("nope", "s2", message_index=0, user_id=1) is None

    def test_get_fork_lineage(self, db):
        db.register_session(session_id="s1", user_id=1)
        db.fork_session("s1", "s2", message_index=-1, user_id=1)
        db.fork_session("s2", "s3", message_index=-1, user_id=1)
        lineage = db.get_fork_lineage("s3")
        assert lineage == ["s1", "s2"]

    def test_get_fork_lineage_no_fork(self, db):
        db.register_session(session_id="s1", user_id=1)
        assert db.get_fork_lineage("s1") == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py::TestSessionMessages -x -v`
Expected: FAIL — `AttributeError: 'ACPSessionsDB' has no attribute 'record_prompt'`

**Step 3: Add methods to `ACPSessionsDB`**

Add `record_prompt`, `get_messages`, `fork_session`, `get_fork_lineage` methods. Key implementation notes:
- `record_prompt` inserts user messages + assistant response into `session_messages`, updates token columns on `sessions`
- Use `_normalize_text_content` and `_normalize_prompt_messages` from existing `admin_acp_sessions_service.py` (import them)
- `fork_session` copies messages up to `message_index` (inclusive), creates new session with `forked_from`
- `get_fork_lineage` walks `forked_from` chain via SQL queries with cycle guard

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py -x -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py \
       tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py
git commit -m "feat(acp): add session messages, token tracking, and fork to Sessions DB"
```

---

## Task 3: ACP Sessions DB — Quota Checks and Cleanup

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_sessions_db.py`

**Step 1: Write the failing tests**

```python
class TestQuotasAndCleanup:
    def test_check_session_quota_under_limit(self, db):
        db.configure_quotas(max_concurrent_per_user=3)
        db.register_session(session_id="s1", user_id=1)
        assert db.check_session_quota(1) is None

    def test_check_session_quota_exceeded(self, db):
        db.configure_quotas(max_concurrent_per_user=1)
        db.register_session(session_id="s1", user_id=1)
        error = db.check_session_quota(1)
        assert error is not None
        assert error["code"] == "quota_exceeded"

    def test_check_token_quota_exceeded(self, db):
        db.configure_quotas(max_tokens_per_session=100)
        db.register_session(session_id="s1", user_id=1)
        # Simulate token usage by direct update
        conn = db._get_conn()
        conn.execute("UPDATE sessions SET total_tokens = 150 WHERE session_id = 's1'")
        conn.commit()
        error = db.check_token_quota("s1")
        assert error is not None
        assert error["code"] == "token_quota_exceeded"

    def test_evict_expired_sessions(self, db):
        db.configure_quotas(session_ttl_seconds=0)  # Immediate expiry
        db.register_session(session_id="s1", user_id=1)
        evicted = db.evict_expired_sessions()
        assert evicted == 1
        rec = db.get_session("s1")
        assert rec.status == "closed"
```

**Step 2-5:** Implement `configure_quotas`, `check_session_quota`, `check_token_quota`, `evict_expired_sessions`. These use SQL queries against the sessions table (e.g., `SELECT COUNT(*) FROM sessions WHERE user_id=? AND status='active'`). Run tests, commit.

```bash
git commit -m "feat(acp): add quota checks and TTL cleanup to Sessions DB"
```

---

## Task 4: Wire ACPSessionStore to use ACPSessionsDB

**Files:**
- Modify: `tldw_Server_API/app/services/admin_acp_sessions_service.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py` (existing)

**Step 1: Read existing tests**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py -x -v`
Expected: All existing tests PASS (baseline)

**Step 2: Refactor `ACPSessionStore` internals**

Replace `self._sessions: dict[str, SessionRecord]` with `self._db: ACPSessionsDB`. Each public method delegates to the DB:
- `register_session` → `self._db.register_session(...)`
- `get_session` → `self._db.get_session(...)`
- `list_sessions` → `self._db.list_sessions(...)`
- `close_session` → `self._db.close_session(...)`
- `record_prompt` → `self._db.record_prompt(...)`
- `fork_session` → `self._db.fork_session(...)`
- `get_fork_lineage` → `self._db.get_fork_lineage(...)`
- Quota methods → `self._db.check_session_quota(...)`, etc.

Keep the `asyncio.Lock` for compatibility (SQLite handles its own locking, but the lock prevents redundant concurrent queries).

**Step 3: Run existing tests**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_session_store.py -x -v`
Expected: PASS

**Step 4: Run full ACP test suite**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/ -x -v`
Expected: All 146+ tests PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_acp_sessions_service.py
git commit -m "refactor(acp): wire ACPSessionStore to SQLite backend"
```

---

## Task 5: Orchestration DB — Schema and CRUD

**Files:**
- Create: `tldw_Server_API/app/core/DB_Management/Orchestration_DB.py`
- Test: `tldw_Server_API/tests/Agent_Orchestration/test_orchestration_db.py`

**Step 1: Write the failing tests**

```python
"""Tests for Orchestration SQLite persistence."""
import os
import tempfile
import pytest
from tldw_Server_API.app.core.DB_Management.Orchestration_DB import OrchestrationDB
from tldw_Server_API.app.core.Agent_Orchestration.models import TaskStatus, RunStatus


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        instance = OrchestrationDB(user_id=1, db_dir=tmp)
        yield instance
        instance.close()


class TestProjectCRUD:
    def test_create_and_get_project(self, db):
        project = db.create_project(name="Test Project", description="A test")
        assert project.id > 0
        assert project.name == "Test Project"
        fetched = db.get_project(project.id)
        assert fetched is not None
        assert fetched.name == "Test Project"

    def test_list_projects(self, db):
        db.create_project(name="P1")
        db.create_project(name="P2")
        projects = db.list_projects()
        assert len(projects) == 2

    def test_delete_project_cascades(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1")
        db.create_run(t.id)
        assert db.delete_project(p.id) is True
        assert db.get_project(p.id) is None
        assert db.get_task(t.id) is None


class TestTaskCRUD:
    def test_create_task_with_dependency(self, db):
        p = db.create_project(name="P1")
        t1 = db.create_task(p.id, title="T1")
        t2 = db.create_task(p.id, title="T2", dependency_id=t1.id)
        assert t2.dependency_id == t1.id

    def test_cycle_detection(self, db):
        p = db.create_project(name="P1")
        t1 = db.create_task(p.id, title="T1")
        t2 = db.create_task(p.id, title="T2", dependency_id=t1.id)
        with pytest.raises(ValueError, match="cycle"):
            db.create_task(p.id, title="T3", dependency_id=t2.id)
            # After T3 exists with dep on T2, try to make T1 depend on T3
            # Actually: direct cycle test
        # Better cycle test: A->B, try B->A
        p2 = db.create_project(name="P2")
        ta = db.create_task(p2.id, title="A")
        tb = db.create_task(p2.id, title="B", dependency_id=ta.id)
        # Can't create C that depends on B then make A depend on C
        # But with single-link deps, cycle is: try to set A.dep = B when B.dep = A
        # This needs the cycle detection to work at create time

    def test_transition_task(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1")
        updated = db.transition_task(t.id, TaskStatus.IN_PROGRESS)
        assert updated.status == TaskStatus.IN_PROGRESS

    def test_invalid_transition_raises(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1")
        with pytest.raises(ValueError, match="Invalid transition"):
            db.transition_task(t.id, TaskStatus.COMPLETE)  # todo -> complete not allowed

    def test_check_dependency_ready(self, db):
        p = db.create_project(name="P1")
        t1 = db.create_task(p.id, title="T1")
        t2 = db.create_task(p.id, title="T2", dependency_id=t1.id)
        assert db.check_dependency_ready(t2.id) is False
        db.transition_task(t1.id, TaskStatus.IN_PROGRESS)
        db.transition_task(t1.id, TaskStatus.REVIEW)
        db.transition_task(t1.id, TaskStatus.COMPLETE)
        assert db.check_dependency_ready(t2.id) is True


class TestRunCRUD:
    def test_create_and_complete_run(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1")
        run = db.create_run(t.id, agent_type="claude_code", session_id="sess-1")
        assert run.status == RunStatus.RUNNING
        completed = db.complete_run(run.id, result_summary="done", token_usage={"input_tokens": 100})
        assert completed.status == RunStatus.COMPLETED

    def test_fail_run(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1")
        run = db.create_run(t.id)
        failed = db.fail_run(run.id, error="something broke")
        assert failed.status == RunStatus.FAILED
        assert failed.error == "something broke"

    def test_list_runs(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1")
        db.create_run(t.id)
        db.create_run(t.id)
        runs = db.list_runs(t.id)
        assert len(runs) == 2


class TestReviewerGate:
    def test_submit_review_approved(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1", reviewer_agent_type="reviewer")
        db.transition_task(t.id, TaskStatus.IN_PROGRESS)
        db.transition_task(t.id, TaskStatus.REVIEW)
        result = db.submit_review(t.id, approved=True, feedback="LGTM")
        assert result.status == TaskStatus.COMPLETE
        reviews = db.list_reviews(t.id)
        assert len(reviews) == 1
        assert reviews[0]["feedback"] == "LGTM"

    def test_submit_review_rejected_triage(self, db):
        p = db.create_project(name="P1")
        t = db.create_task(p.id, title="T1", max_review_attempts=1)
        db.transition_task(t.id, TaskStatus.IN_PROGRESS)
        db.transition_task(t.id, TaskStatus.REVIEW)
        result = db.submit_review(t.id, approved=False, feedback="Needs work")
        assert result.status == TaskStatus.TRIAGE
```

**Step 2-5:** Implement `OrchestrationDB` with all CRUD methods. Constructor takes `user_id` and optional `db_dir`, resolves path to `{db_dir}/{user_id}/orchestration.db` (or uses `get_user_base_directory` in production). Run tests, commit.

```bash
git commit -m "feat(acp): add Orchestration DB with projects, tasks, runs, reviews"
```

---

## Task 6: Wire Orchestration Endpoints to DB

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_orchestration.py`
- Modify: `tldw_Server_API/app/core/Agent_Orchestration/orchestration_service.py`
- Test: `tldw_Server_API/tests/Agent_Orchestration/test_orchestration_api.py` (existing)

**Step 1: Run baseline**

Run: `python -m pytest tldw_Server_API/tests/Agent_Orchestration/ -x -v`
Expected: All existing tests PASS

**Step 2: Add `get_orchestration_db` factory**

Add to `orchestration_service.py`:

```python
import functools
from tldw_Server_API.app.core.DB_Management.Orchestration_DB import OrchestrationDB

@functools.lru_cache(maxsize=64)
def get_orchestration_db(user_id: int) -> OrchestrationDB:
    """Get or create per-user OrchestrationDB instance."""
    return OrchestrationDB(user_id=user_id)
```

**Step 3: Update endpoints**

Replace all `svc = await get_orchestration_service()` calls with `db = get_orchestration_db(int(user.id))`. Remove user_id ownership checks (per-user DB handles scoping). The `OrchestrationDB` methods are sync (SQLite), so no `await` needed.

**Step 4: Update tests to use DB-backed service**

Update test fixtures to use temporary DB directories. Ensure all 10 orchestration API tests pass.

**Step 5: Run full test suite**

Run: `python -m pytest tldw_Server_API/tests/Agent_Orchestration/ -x -v`
Expected: PASS

**Step 6: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/agent_orchestration.py \
       tldw_Server_API/app/core/Agent_Orchestration/orchestration_service.py \
       tldw_Server_API/tests/Agent_Orchestration/
git commit -m "refactor(acp): wire orchestration endpoints to per-user SQLite"
```

---

## Task 7: Unify Agent Registry — Extend YAML Schema

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py`
- Modify: `tldw_Server_API/Config_Files/agents.yaml`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_agent_registry.py`

**Step 1: Write the failing tests**

Add to `test_acp_agent_registry.py`:

```python
EXTENDED_REGISTRY = """
agents:
  - type: claude_code
    name: Claude Code
    command: nonexistent_xyz
    requires_api_key: ANTHROPIC_API_KEY
    default: true
    install_instructions:
      - "npm install -g @anthropic-ai/claude-code"
    docs_url: "https://docs.anthropic.com/claude-code"
  - type: aider
    name: Aider
    command: aider
    requires_api_key: null
    install_instructions:
      - "pip install aider-chat"
    docs_url: "https://aider.chat"
"""

def test_registry_entry_has_install_instructions(registry_file_extended):
    registry = AgentRegistry(yaml_path=registry_file_extended)
    entry = registry.get_entry("claude_code")
    assert entry is not None
    assert entry.install_instructions == ["npm install -g @anthropic-ai/claude-code"]
    assert entry.docs_url == "https://docs.anthropic.com/claude-code"

def test_registry_entry_defaults_empty_install(registry_file):
    registry = AgentRegistry(yaml_path=registry_file)
    entry = registry.get_entry("claude_code")
    assert entry.install_instructions == []
    assert entry.docs_url is None
```

**Step 2: Run test to verify it fails**

Expected: FAIL — `AgentRegistryEntry has no attribute 'install_instructions'`

**Step 3: Extend `AgentRegistryEntry` and `load()`**

Add fields to the dataclass:
```python
install_instructions: list[str] = field(default_factory=list)
docs_url: str | None = None
```

Update `load()` to parse these from YAML:
```python
entry = AgentRegistryEntry(
    ...
    install_instructions=list(item.get("install_instructions", [])),
    docs_url=item.get("docs_url"),
)
```

**Step 4: Update `agents.yaml`**

Add `install_instructions` and `docs_url` to existing entries. Add new agents: `aider`, `goose`, `continue_dev`.

**Step 5: Run tests, commit**

```bash
git commit -m "feat(acp): extend agent registry with install instructions and new agent types"
```

---

## Task 8: Unify Agent Registry — Replace Hardcoded Setup Guides

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_health.py`

**Step 1: Run baseline health/setup tests**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_health.py -x -v`
Expected: PASS

**Step 2: Replace `_AGENT_SETUP_GUIDES` with registry**

In `agent_client_protocol.py`:
- Delete the `_AGENT_SETUP_GUIDES` dict (~30 lines)
- Rewrite `_check_agent_availability(agent_type)` to use `get_agent_registry().get_entry(agent_type).check_availability()` with fallback for unknown types
- Update `acp_health()` to iterate `get_agent_registry().entries` instead of `_AGENT_SETUP_GUIDES`
- Update `acp_setup_guide()` to read `install_instructions` and `docs_url` from registry entries

**Step 3: Run tests**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/test_acp_health.py -x -v`
Expected: PASS (may need test updates if tests relied on hardcoded agent types)

**Step 4: Run full ACP suite**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/ -x -v`
Expected: PASS

**Step 5: Commit**

```bash
git commit -m "refactor(acp): replace hardcoded setup guides with unified agent registry"
```

---

## Task 9: Dynamic Agent Registration API

**Files:**
- Modify: `tldw_Server_API/app/core/Agent_Client_Protocol/agent_registry.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/agent_client_protocol.py`
- Modify: `tldw_Server_API/Config_Files/privilege_catalog.yaml`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_agent_registry.py`

**Step 1: Write the failing tests**

```python
class TestDynamicRegistration:
    def test_register_agent(self, db_registry):
        registry = db_registry  # fixture provides registry backed by temp SQLite
        entry = registry.register_agent(
            type="my_agent",
            name="My Agent",
            command="my-agent-cli",
        )
        assert entry.type == "my_agent"
        assert registry.get_entry("my_agent") is not None

    def test_deregister_agent(self, db_registry):
        db_registry.register_agent(type="tmp", name="Tmp", command="tmp")
        assert db_registry.deregister_agent("tmp") is True
        assert db_registry.get_entry("tmp") is None

    def test_yaml_entries_preserved_after_register(self, db_registry):
        # YAML entries should still be present
        assert db_registry.get_entry("claude_code") is not None
        db_registry.register_agent(type="new", name="New", command="new")
        assert db_registry.get_entry("claude_code") is not None
```

**Step 2-3: Implement**

1. Add `agent_registry` table to `ACP_Sessions_DB` schema
2. Add `threading.RLock` to `AgentRegistry`
3. Add `register_agent()`, `deregister_agent()`, `update_agent()` methods
4. Modify `entries` property to merge YAML + DB entries (DB overrides YAML for same type)
5. Add endpoints: `POST /acp/agents/register`, `DELETE /acp/agents/{agent_type}`, `PUT /acp/agents/{agent_type}`
6. Add `ACPAgentRegisterRequest` schema
7. Add privilege scopes: `acp.agents.register`, `acp.agents.manage`

**Step 4-5: Run tests, commit**

```bash
git commit -m "feat(acp): add dynamic agent registration API with DB persistence"
```

---

## Task 10: Agent Health Monitoring

**Files:**
- Create: `tldw_Server_API/app/core/Agent_Client_Protocol/health_monitor.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/agent_client_protocol.py`
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_health_monitor.py`

**Step 1: Write the failing tests**

```python
"""Tests for agent health monitoring."""
import pytest
from unittest.mock import MagicMock
from tldw_Server_API.app.core.Agent_Client_Protocol.health_monitor import (
    AgentHealthMonitor,
    AgentHealthStatus,
)


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    entry1 = MagicMock()
    entry1.type = "claude_code"
    entry1.check_availability.return_value = {"status": "available", "is_configured": True}
    entry2 = MagicMock()
    entry2.type = "codex"
    entry2.check_availability.return_value = {"status": "unavailable", "is_configured": False}
    registry.entries = [entry1, entry2]
    return registry


def test_check_all_agents(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    status = monitor.get_status("claude_code")
    assert status is not None
    assert status.health == "healthy"


def test_consecutive_failures_disable(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=2)
    monitor.check_all()
    monitor.check_all()  # 2nd consecutive failure for codex
    status = monitor.get_status("codex")
    assert status.health == "unavailable"
    assert status.consecutive_failures == 2


def test_recovery_re_enables(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry, failure_threshold=1)
    monitor.check_all()  # codex fails
    status = monitor.get_status("codex")
    assert status.health == "unavailable"
    # Now codex becomes available
    mock_registry.entries[1].check_availability.return_value = {"status": "available", "is_configured": True}
    monitor.check_all()
    status = monitor.get_status("codex")
    assert status.health == "healthy"
    assert status.consecutive_failures == 0


def test_get_all_statuses(mock_registry):
    monitor = AgentHealthMonitor(registry=mock_registry)
    monitor.check_all()
    all_status = monitor.get_all_statuses()
    assert len(all_status) == 2
```

**Step 2-3: Implement**

Create `health_monitor.py`:

```python
@dataclass
class AgentHealthStatus:
    agent_type: str
    health: str  # healthy | degraded | unavailable | unknown
    consecutive_failures: int = 0
    last_check: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

class AgentHealthMonitor:
    def __init__(self, registry, check_interval=60, failure_threshold=3):
        ...
    def check_all(self): ...
    def get_status(self, agent_type) -> AgentHealthStatus | None: ...
    def get_all_statuses(self) -> list[AgentHealthStatus]: ...
    async def start(self): ...
    async def stop(self): ...
```

Add `agent_health_history` table to `ACP_Sessions_DB`. Add `GET /acp/agents/health` endpoint.

**Step 4-5: Run tests, commit**

```bash
git commit -m "feat(acp): add agent health monitoring with auto-disable and recovery"
```

---

## Task 11: Integration Testing and Cleanup

**Files:**
- Test: `tldw_Server_API/tests/Agent_Client_Protocol/test_acp_integration_persistence.py`

**Step 1: Write integration tests**

Test the full flow end-to-end:
1. Create session via store → verify persisted to SQLite
2. Record prompts → verify messages in DB
3. Fork session → verify fork lineage in DB
4. Create project/task/run via orchestration → verify in per-user DB
5. Submit review → verify review stored
6. Health monitor check → verify health history recorded

**Step 2: Run full test suite**

Run: `python -m pytest tldw_Server_API/tests/Agent_Client_Protocol/ tldw_Server_API/tests/Agent_Orchestration/ -x -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git commit -m "test(acp): add integration tests for persistence and registry"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Sessions DB schema + CRUD | `ACP_Sessions_DB.py` |
| 2 | Messages, tokens, fork | `ACP_Sessions_DB.py` |
| 3 | Quotas and cleanup | `ACP_Sessions_DB.py` |
| 4 | Wire SessionStore to DB | `admin_acp_sessions_service.py` |
| 5 | Orchestration DB schema + CRUD | `Orchestration_DB.py` |
| 6 | Wire orchestration endpoints | `agent_orchestration.py` |
| 7 | Extend YAML registry schema | `agent_registry.py`, `agents.yaml` |
| 8 | Replace hardcoded setup guides | `agent_client_protocol.py` |
| 9 | Dynamic registration API | Registry + endpoints |
| 10 | Health monitoring | `health_monitor.py` |
| 11 | Integration tests | Full flow validation |
