"""
Chat Workflows database adapter.

Provides dedicated persistence for chat workflow templates, runs, answers, and
run events. The initial implementation uses SQLite-backed storage matching the
per-user database layout used elsewhere in the project.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


class ChatWorkflowsDatabase:
    """SQLite persistence adapter for chat workflow state."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        client_id: str,
        backend: Any | None = None,
    ) -> None:
        self.client_id = client_id
        self.backend = backend
        self.db_path = str(db_path)

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._create_schema()

    @contextmanager
    def transaction(self):
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chat_workflow_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_workflow_template_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id INTEGER NOT NULL,
                step_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                label TEXT,
                base_question TEXT NOT NULL,
                question_mode TEXT NOT NULL DEFAULT 'stock',
                phrasing_instructions TEXT,
                context_refs_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (template_id) REFERENCES chat_workflow_templates(id) ON DELETE CASCADE,
                UNIQUE (template_id, step_index)
            );

            CREATE TABLE IF NOT EXISTS chat_workflow_runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                template_id INTEGER,
                template_version INTEGER NOT NULL,
                source_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                current_step_index INTEGER NOT NULL DEFAULT 0,
                template_snapshot_json TEXT NOT NULL,
                selected_context_refs_json TEXT NOT NULL DEFAULT '[]',
                resolved_context_snapshot_json TEXT NOT NULL DEFAULT '[]',
                question_renderer_model TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                canceled_at TEXT,
                free_chat_conversation_id TEXT,
                FOREIGN KEY (template_id) REFERENCES chat_workflow_templates(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS chat_workflow_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                displayed_question TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                question_generation_meta_json TEXT NOT NULL DEFAULT '{}',
                answered_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES chat_workflow_runs(run_id) ON DELETE CASCADE,
                UNIQUE (run_id, step_index)
            );

            CREATE TABLE IF NOT EXISTS chat_workflow_run_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES chat_workflow_runs(run_id) ON DELETE CASCADE,
                UNIQUE (run_id, seq)
            );

            CREATE INDEX IF NOT EXISTS idx_chat_workflow_templates_owner
            ON chat_workflow_templates(tenant_id, user_id, status);

            CREATE INDEX IF NOT EXISTS idx_chat_workflow_runs_owner
            ON chat_workflow_runs(tenant_id, user_id, status);

            CREATE INDEX IF NOT EXISTS idx_chat_workflow_answers_run
            ON chat_workflow_answers(run_id, step_index);
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def create_template(
        self,
        *,
        tenant_id: str,
        user_id: str,
        title: str,
        description: str | None,
        version: int,
        status: str = "active",
    ) -> int:
        now = _utcnow_iso()
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_workflow_templates (
                    tenant_id, user_id, title, description, status, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tenant_id, user_id, title, description, status, version, now, now),
            )
        return int(cursor.lastrowid)

    def replace_template_steps(self, template_id: int, steps: list[dict[str, Any]]) -> None:
        now = _utcnow_iso()
        with self.transaction() as conn:
            conn.execute(
                "DELETE FROM chat_workflow_template_steps WHERE template_id = ?",
                (template_id,),
            )
            for index, step in enumerate(steps):
                step_index = int(step.get("step_index", index))
                step_id = str(step.get("step_id") or step.get("id") or f"step-{step_index + 1}")
                context_refs = step.get("context_refs_json")
                if context_refs is None:
                    context_refs = step.get("context_refs", [])
                if not isinstance(context_refs, str):
                    context_refs = _json_dumps(context_refs)
                conn.execute(
                    """
                    INSERT INTO chat_workflow_template_steps (
                        template_id, step_id, step_index, label, base_question, question_mode,
                        phrasing_instructions, context_refs_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        step_id,
                        step_index,
                        step.get("label"),
                        step["base_question"],
                        step.get("question_mode", "stock"),
                        step.get("phrasing_instructions"),
                        context_refs,
                        now,
                        now,
                    ),
                )

    def list_template_steps(self, template_id: int) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            """
            SELECT id, template_id, step_id, step_index, label, base_question,
                   question_mode, phrasing_instructions, context_refs_json,
                   created_at, updated_at
            FROM chat_workflow_template_steps
            WHERE template_id = ?
            ORDER BY step_index ASC
            """,
            (template_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            """
            SELECT id, tenant_id, user_id, title, description, status, version,
                   created_at, updated_at
            FROM chat_workflow_templates
            WHERE id = ?
            """,
            (template_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        data = dict(row)
        data["steps"] = self.list_template_steps(template_id)
        return data

    def list_templates(
        self,
        *,
        tenant_id: str,
        user_id: str,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [tenant_id, user_id]
        query = """
            SELECT id, tenant_id, user_id, title, description, status, version,
                   created_at, updated_at
            FROM chat_workflow_templates
            WHERE tenant_id = ? AND user_id = ?
        """
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC, id DESC"
        cursor = self._conn.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def update_template(
        self,
        template_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        version: int | None = None,
    ) -> None:
        assignments: list[str] = []
        params: list[Any] = []
        if title is not None:
            assignments.append("title = ?")
            params.append(title)
        if description is not None:
            assignments.append("description = ?")
            params.append(description)
        if status is not None:
            assignments.append("status = ?")
            params.append(status)
        if version is not None:
            assignments.append("version = ?")
            params.append(version)
        assignments.append("updated_at = ?")
        params.append(_utcnow_iso())
        params.append(template_id)
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE chat_workflow_templates SET {', '.join(assignments)} WHERE id = ?",
                tuple(params),
            )

    def delete_template(self, template_id: int) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM chat_workflow_templates WHERE id = ?", (template_id,))

    def create_run(
        self,
        *,
        tenant_id: str,
        user_id: str,
        template_id: int | None,
        template_version: int,
        source_mode: str,
        status: str,
        template_snapshot: dict[str, Any],
        selected_context_refs: list[dict[str, Any]] | list[Any],
        resolved_context_snapshot: list[dict[str, Any]] | list[Any],
        run_id: str | None = None,
        current_step_index: int = 0,
        question_renderer_model: str | None = None,
    ) -> str:
        run_identifier = run_id or str(uuid4())
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO chat_workflow_runs (
                    run_id, tenant_id, user_id, template_id, template_version, source_mode, status,
                    current_step_index, template_snapshot_json, selected_context_refs_json,
                    resolved_context_snapshot_json, question_renderer_model, started_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_identifier,
                    tenant_id,
                    user_id,
                    template_id,
                    template_version,
                    source_mode,
                    status,
                    current_step_index,
                    _json_dumps(template_snapshot),
                    _json_dumps(selected_context_refs),
                    _json_dumps(resolved_context_snapshot),
                    question_renderer_model,
                    _utcnow_iso(),
                ),
            )
        return run_identifier

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            """
            SELECT run_id, tenant_id, user_id, template_id, template_version, source_mode, status,
                   current_step_index, template_snapshot_json, selected_context_refs_json,
                   resolved_context_snapshot_json, question_renderer_model, started_at,
                   completed_at, canceled_at, free_chat_conversation_id
            FROM chat_workflow_runs
            WHERE run_id = ?
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row is not None else None

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        current_step_index: int | None = None,
        completed_at: str | None = None,
        canceled_at: str | None = None,
        free_chat_conversation_id: str | None = None,
    ) -> None:
        assignments: list[str] = []
        params: list[Any] = []
        if status is not None:
            assignments.append("status = ?")
            params.append(status)
        if current_step_index is not None:
            assignments.append("current_step_index = ?")
            params.append(current_step_index)
        if completed_at is not None:
            assignments.append("completed_at = ?")
            params.append(completed_at)
        if canceled_at is not None:
            assignments.append("canceled_at = ?")
            params.append(canceled_at)
        if free_chat_conversation_id is not None:
            assignments.append("free_chat_conversation_id = ?")
            params.append(free_chat_conversation_id)
        if not assignments:
            return
        params.append(run_id)
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE chat_workflow_runs SET {', '.join(assignments)} WHERE run_id = ?",
                tuple(params),
            )

    def add_answer(
        self,
        *,
        run_id: str,
        step_id: str,
        step_index: int,
        displayed_question: str,
        answer_text: str,
        question_generation_meta: dict[str, Any],
    ) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_workflow_answers (
                    run_id, step_id, step_index, displayed_question, answer_text,
                    question_generation_meta_json, answered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_id,
                    step_index,
                    displayed_question,
                    answer_text,
                    _json_dumps(question_generation_meta),
                    _utcnow_iso(),
                ),
            )
        return int(cursor.lastrowid)

    def list_answers(self, run_id: str) -> list[dict[str, Any]]:
        cursor = self._conn.execute(
            """
            SELECT id, run_id, step_id, step_index, displayed_question, answer_text,
                   question_generation_meta_json, answered_at
            FROM chat_workflow_answers
            WHERE run_id = ?
            ORDER BY step_index ASC
            """,
            (run_id,),
        )
        return [dict(row) for row in cursor.fetchall()]

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        cursor = self._conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM chat_workflow_run_events WHERE run_id = ?",
            (run_id,),
        )
        row = cursor.fetchone()
        next_seq = int(row["next_seq"]) if row is not None else 1
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO chat_workflow_run_events (
                    run_id, seq, event_type, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, next_seq, event_type, _json_dumps(payload), _utcnow_iso()),
            )
        return next_seq

    def list_events(
        self,
        run_id: str,
        *,
        since: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [run_id]
        query = """
            SELECT id, run_id, seq, event_type, payload_json, created_at
            FROM chat_workflow_run_events
            WHERE run_id = ?
        """
        if since is not None:
            query += " AND seq > ?"
            params.append(since)
        query += " ORDER BY seq ASC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        cursor = self._conn.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]

    def __del__(self) -> None:  # pragma: no cover - defensive cleanup
        try:
            self.close()
        except Exception:
            logger.debug("Failed to close ChatWorkflowsDatabase cleanly")
