"""SQLite-backed persistence for Agent Orchestration (per-user).

Stores projects, tasks, runs, and reviews with full state-machine
enforcement and cycle-safe dependency tracking.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from tldw_Server_API.app.core.DB_Management.sqlite_policy import configure_sqlite_connection

from tldw_Server_API.app.core.Agent_Orchestration.models import (
    AgentProject,
    AgentRun,
    AgentTask,
    RunStatus,
    TaskStatus,
    is_valid_transition,
)

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class OrchestrationNotFoundError(ValueError):
    """Raised when a project, task, or run is not found."""


class InvalidTransitionError(ValueError):
    """Raised when a task state transition is not allowed."""


_SCHEMA_VERSION = 1

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    user_id INTEGER NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'todo',
    agent_type TEXT,
    dependency_id INTEGER,
    reviewer_agent_type TEXT,
    max_review_attempts INTEGER NOT NULL DEFAULT 3,
    review_count INTEGER NOT NULL DEFAULT 0,
    success_criteria TEXT NOT NULL DEFAULT '',
    user_id INTEGER NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    FOREIGN KEY (dependency_id) REFERENCES tasks(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_dependency ON tasks(dependency_id);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    session_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    agent_type TEXT,
    started_at TEXT,
    completed_at TEXT,
    result_summary TEXT NOT NULL DEFAULT '',
    error TEXT,
    token_usage TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_runs_task ON runs(task_id);
CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    approved INTEGER NOT NULL,
    feedback TEXT NOT NULL DEFAULT '',
    reviewer TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reviews_task ON reviews(task_id);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


class OrchestrationDB:
    """Per-user SQLite store for orchestration projects, tasks, runs, reviews."""

    def __init__(self, user_id: int, db_dir: str | None = None) -> None:
        self._user_id = user_id
        if db_dir is None:
            from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
            db_dir = DatabasePaths.get_user_base_directory(user_id)
        self._db_path = os.path.join(db_dir, "orchestration.db")
        self._conn_local = threading.local()
        self._initialized = False
        self._init_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._conn_local, "conn", None)
        if conn is None:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            configure_sqlite_connection(conn)
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
            conn.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
            conn.commit()
            self._initialized = True

    # ------------------------------------------------------------------
    # Row -> dataclass helpers
    # ------------------------------------------------------------------

    def _row_to_project(self, row: sqlite3.Row) -> AgentProject:
        return AgentProject(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_parse_json(row["metadata"]),
        )

    def _row_to_task(self, row: sqlite3.Row) -> AgentTask:
        return AgentTask(
            id=row["id"],
            project_id=row["project_id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            agent_type=row["agent_type"],
            dependency_id=row["dependency_id"],
            reviewer_agent_type=row["reviewer_agent_type"],
            max_review_attempts=row["max_review_attempts"],
            review_count=row["review_count"],
            success_criteria=row["success_criteria"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=_parse_json(row["metadata"]),
        )

    def _row_to_run(self, row: sqlite3.Row) -> AgentRun:
        return AgentRun(
            id=row["id"],
            task_id=row["task_id"],
            session_id=row["session_id"],
            status=RunStatus(row["status"]),
            agent_type=row["agent_type"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            result_summary=row["result_summary"],
            error=row["error"],
            token_usage=_parse_json(row["token_usage"]),
        )

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def create_project(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentProject:
        self._ensure_schema()
        conn = self._get_conn()
        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO projects (name, description, user_id, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, description, self._user_id, json.dumps(metadata or {}), now),
        )
        conn.commit()
        return AgentProject(
            id=cur.lastrowid,
            name=name,
            description=description,
            user_id=self._user_id,
            created_at=now,
            metadata=dict(metadata or {}),
        )

    def get_project(self, project_id: int) -> AgentProject | None:
        self._ensure_schema()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    def list_projects(self) -> list[AgentProject]:
        self._ensure_schema()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (self._user_id,),
        ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def delete_project(self, project_id: int) -> bool:
        self._ensure_schema()
        conn = self._get_conn()
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return cur.rowcount > 0

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def create_task(
        self,
        project_id: int,
        title: str,
        description: str = "",
        agent_type: str | None = None,
        dependency_id: int | None = None,
        reviewer_agent_type: str | None = None,
        max_review_attempts: int = 3,
        success_criteria: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentTask:
        self._ensure_schema()
        conn = self._get_conn()

        # Validate project exists
        if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
            raise OrchestrationNotFoundError(f"Project {project_id} not found")

        # Validate dependency exists
        if dependency_id is not None:
            if conn.execute("SELECT 1 FROM tasks WHERE id = ?", (dependency_id,)).fetchone() is None:
                raise OrchestrationNotFoundError(f"Dependency task {dependency_id} not found")
            # Cycle detection is not meaningful at creation since the new task
            # doesn't have an id yet, but we keep the helper for potential
            # future use when updating dependencies.

        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO tasks "
            "(project_id, title, description, status, agent_type, dependency_id, "
            " reviewer_agent_type, max_review_attempts, review_count, success_criteria, "
            " user_id, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
            (
                project_id, title, description, TaskStatus.TODO.value,
                agent_type, dependency_id, reviewer_agent_type,
                max_review_attempts, success_criteria,
                self._user_id, json.dumps(metadata or {}), now,
            ),
        )
        conn.commit()
        return AgentTask(
            id=cur.lastrowid,
            project_id=project_id,
            title=title,
            description=description,
            status=TaskStatus.TODO,
            agent_type=agent_type,
            dependency_id=dependency_id,
            reviewer_agent_type=reviewer_agent_type,
            max_review_attempts=max_review_attempts,
            review_count=0,
            success_criteria=success_criteria,
            user_id=self._user_id,
            created_at=now,
            metadata=dict(metadata or {}),
        )

    def get_task(self, task_id: int) -> AgentTask | None:
        self._ensure_schema()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def list_tasks(
        self,
        project_id: int,
        status: TaskStatus | None = None,
    ) -> list[AgentTask]:
        self._ensure_schema()
        conn = self._get_conn()
        if status is not None:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY created_at",
                (project_id, status.value),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def transition_task(self, task_id: int, new_status: TaskStatus) -> AgentTask:
        self._ensure_schema()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise OrchestrationNotFoundError(f"Task {task_id} not found")

        current = TaskStatus(row["status"])
        if not is_valid_transition(current, new_status):
            raise InvalidTransitionError(
                f"Invalid transition from {current.value} to {new_status.value}"
            )

        now = _now_iso()
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (new_status.value, now, task_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(updated)

    def check_dependency_ready(self, task_id: int) -> bool:
        self._ensure_schema()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT dependency_id FROM tasks WHERE id = ?", (task_id,),
        ).fetchone()
        if row is None:
            raise OrchestrationNotFoundError(f"Task {task_id} not found")
        dep_id = row["dependency_id"]
        if dep_id is None:
            return True
        dep_row = conn.execute(
            "SELECT status FROM tasks WHERE id = ?", (dep_id,),
        ).fetchone()
        if dep_row is None:
            return True  # dependency deleted
        return TaskStatus(dep_row["status"]) == TaskStatus.COMPLETE

    def _detect_cycle(self, task_id: int, dependency_id: int) -> bool:
        """Walk dependency chain from dependency_id; True if it reaches task_id."""
        self._ensure_schema()
        conn = self._get_conn()
        visited: set[int] = set()
        current = dependency_id
        while current is not None:
            if current == task_id:
                return True
            if current in visited:
                return True  # already a cycle in the chain
            visited.add(current)
            row = conn.execute(
                "SELECT dependency_id FROM tasks WHERE id = ?", (current,),
            ).fetchone()
            if row is None:
                break
            current = row["dependency_id"]
        return False

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        task_id: int,
        agent_type: str | None = None,
        session_id: str | None = None,
    ) -> AgentRun:
        self._ensure_schema()
        conn = self._get_conn()
        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO runs (task_id, session_id, status, agent_type, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, session_id, RunStatus.RUNNING.value, agent_type, now),
        )
        conn.commit()
        return AgentRun(
            id=cur.lastrowid,
            task_id=task_id,
            session_id=session_id,
            status=RunStatus.RUNNING,
            agent_type=agent_type,
            started_at=now,
        )

    def complete_run(
        self,
        run_id: int,
        result_summary: str = "",
        token_usage: dict[str, Any] | None = None,
    ) -> AgentRun:
        self._ensure_schema()
        conn = self._get_conn()
        now = _now_iso()
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = ?, result_summary = ?, token_usage = ? "
            "WHERE id = ?",
            (
                RunStatus.COMPLETED.value, now, result_summary,
                json.dumps(token_usage or {}), run_id,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row)

    def fail_run(self, run_id: int, error: str = "") -> AgentRun:
        self._ensure_schema()
        conn = self._get_conn()
        now = _now_iso()
        conn.execute(
            "UPDATE runs SET status = ?, completed_at = ?, error = ? WHERE id = ?",
            (RunStatus.FAILED.value, now, error, run_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return self._row_to_run(row)

    def list_runs(self, task_id: int) -> list[AgentRun]:
        self._ensure_schema()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM runs WHERE task_id = ? ORDER BY started_at DESC",
            (task_id,),
        ).fetchall()
        return [self._row_to_run(r) for r in rows]

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def submit_review(
        self,
        task_id: int,
        approved: bool,
        feedback: str = "",
        reviewer: str | None = None,
    ) -> AgentTask:
        self._ensure_schema()
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise OrchestrationNotFoundError(f"Task {task_id} not found")
        if TaskStatus(row["status"]) != TaskStatus.REVIEW:
            raise InvalidTransitionError(f"Task {task_id} is not in review status")

        now = _now_iso()
        new_review_count = row["review_count"] + 1

        # Determine new status
        if approved:
            new_status = TaskStatus.COMPLETE
        elif new_review_count >= row["max_review_attempts"]:
            new_status = TaskStatus.TRIAGE
        else:
            new_status = TaskStatus.IN_PROGRESS

        conn.execute(
            "UPDATE tasks SET status = ?, review_count = ?, updated_at = ? WHERE id = ?",
            (new_status.value, new_review_count, now, task_id),
        )
        conn.execute(
            "INSERT INTO reviews (task_id, approved, feedback, reviewer, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, int(approved), feedback, reviewer, now),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(updated)

    def list_reviews(self, task_id: int) -> list[dict[str, Any]]:
        self._ensure_schema()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM reviews WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "task_id": r["task_id"],
                "approved": bool(r["approved"]),
                "feedback": r["feedback"],
                "reviewer": r["reviewer"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def get_project_summary(self, project_id: int) -> dict[str, Any]:
        self._ensure_schema()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks WHERE project_id = ? GROUP BY status",
            (project_id,),
        ).fetchall()
        status_counts: dict[str, int] = {}
        total = 0
        for r in rows:
            status_counts[r["status"]] = r["cnt"]
            total += r["cnt"]
        return {
            "project_id": project_id,
            "total_tasks": total,
            "status_counts": status_counts,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        conn: sqlite3.Connection | None = getattr(self._conn_local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
            self._conn_local.conn = None
