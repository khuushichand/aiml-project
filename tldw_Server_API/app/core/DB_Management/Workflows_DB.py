"""
Workflows database adapter (SQLite by default).

Provides minimal persistence for workflow definitions, runs and events
to support v0.1 engine scaffolding.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


DEFAULT_DB_PATH = Path("Databases") / "workflows.db"


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


@dataclass
class WorkflowDefinition:
    id: int
    tenant_id: str
    name: str
    version: int
    owner_id: str
    visibility: str
    description: Optional[str]
    tags: Optional[str]
    definition_json: str
    created_at: str
    updated_at: str
    is_active: int


@dataclass
class WorkflowRun:
    run_id: str
    tenant_id: str
    workflow_id: Optional[int]
    status: str
    status_reason: Optional[str]
    user_id: str
    inputs_json: str
    outputs_json: Optional[str]
    error: Optional[str]
    duration_ms: Optional[int]
    created_at: str
    started_at: Optional[str]
    ended_at: Optional[str]
    definition_version: Optional[int]
    definition_snapshot_json: Optional[str]
    idempotency_key: Optional[str]
    session_id: Optional[str]
    cancel_requested: Optional[int] = 0


class WorkflowsDatabase:
    """Lightweight SQLite adapter for workflows data."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        # Honor DATABASE_URL_WORKFLOWS when pointing to SQLite; Postgres reserved for future
        url = os.getenv("DATABASE_URL_WORKFLOWS", "").strip()
        if not db_path and url:
            if url.startswith("sqlite://"):
                # sqlite:///./Databases/workflows.db or sqlite:////abs/path
                path = url.split("sqlite://", 1)[1]
                # Trim leading slashes for relative path formats
                if path.startswith("/") and not path.startswith("//"):
                    # keep absolute
                    resolved = path
                else:
                    resolved = path.lstrip("/")
                db_path = resolved or str(DEFAULT_DB_PATH)
            else:
                # Unsupported driver for now
                logger.warning("DATABASE_URL_WORKFLOWS is set but non-SQLite backends are not yet supported; falling back to SQLite")
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._enable_wal()
        self._create_schema()
        logger.debug(f"Workflows DB initialized at {self.db_path}")

    def _enable_wal(self) -> None:
        try:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception as e:
            logger.warning(f"Failed to enable WAL on workflows DB: {e}")

    def _create_schema(self) -> None:
        cur = self._conn.cursor()
        # Definitions
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                owner_id TEXT NOT NULL,
                visibility TEXT NOT NULL DEFAULT 'private',
                description TEXT,
                tags TEXT,
                definition_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                UNIQUE(tenant_id, name, version)
            );
            """
        )

        # Runs
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                workflow_id INTEGER,
                status TEXT NOT NULL,
                status_reason TEXT,
                user_id TEXT NOT NULL,
                inputs_json TEXT NOT NULL,
                outputs_json TEXT,
                error TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL,
                started_at TEXT,
                ended_at TEXT,
                definition_version INTEGER,
                definition_snapshot_json TEXT,
                idempotency_key TEXT,
                session_id TEXT,
                tokens_input INTEGER,
                tokens_output INTEGER,
                cost_usd REAL,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(workflow_id) REFERENCES workflows(id)
            );
            """
        )

        # Step runs (minimal, for human decisions later)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_step_runs (
                step_run_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                name TEXT,
                type TEXT,
                status TEXT,
                attempt INTEGER DEFAULT 0,
                started_at TEXT,
                ended_at TEXT,
                inputs_json TEXT,
                outputs_json TEXT,
                error TEXT,
                decision TEXT,
                approved_by TEXT,
                approved_at TEXT,
                review_comment TEXT,
                locked_by TEXT,
                locked_at TEXT,
                lock_expires_at TEXT,
                heartbeat_at TEXT,
                pid INTEGER,
                pgid INTEGER,
                workdir TEXT,
                stdout_path TEXT,
                stderr_path TEXT,
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
            );
            """
        )

        # Events
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                step_run_id TEXT,
                event_seq INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
            );
            """
        )

        # Indices
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workflows_owner ON workflows(owner_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_run_seq ON workflow_events(run_id, event_seq)")
        self._conn.commit()

        # Attempt to add newly introduced columns if missing (SQLite tolerant pattern)
        for alter in [
            "ALTER TABLE workflow_runs ADD COLUMN tokens_input INTEGER",
            "ALTER TABLE workflow_runs ADD COLUMN tokens_output INTEGER",
            "ALTER TABLE workflow_runs ADD COLUMN cost_usd REAL",
            "ALTER TABLE workflow_step_runs ADD COLUMN pid INTEGER",
            "ALTER TABLE workflow_step_runs ADD COLUMN pgid INTEGER",
            "ALTER TABLE workflow_step_runs ADD COLUMN workdir TEXT",
            "ALTER TABLE workflow_step_runs ADD COLUMN stdout_path TEXT",
            "ALTER TABLE workflow_step_runs ADD COLUMN stderr_path TEXT",
        ]:
            try:
                cur.execute(alter)
                self._conn.commit()
            except Exception:
                pass

        # Artifacts table (v0.2)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_artifacts (
                artifact_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                step_run_id TEXT,
                type TEXT,
                uri TEXT,
                size_bytes INTEGER,
                mime_type TEXT,
                checksum_sha256 TEXT,
                encryption TEXT,
                owned_by TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id)
            );
            """
        )
        self._conn.commit()

    # ---------- Definitions ----------
    def create_definition(
        self,
        tenant_id: str,
        name: str,
        version: int,
        owner_id: str,
        visibility: str,
        description: Optional[str],
        tags: Optional[List[str]],
        definition: Dict[str, Any],
        is_active: bool = True,
    ) -> int:
        cur = self._conn.cursor()
        now = _utcnow_iso()
        cur.execute(
            """
            INSERT INTO workflows(tenant_id, name, version, owner_id, visibility, description, tags, definition_json, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                name,
                version,
                owner_id,
                visibility,
                description,
                json.dumps(tags or []),
                json.dumps(definition),
                now,
                now,
                1 if is_active else 0,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_definition(self, workflow_id: int) -> Optional[WorkflowDefinition]:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
        if not row:
            return None
        return WorkflowDefinition(**dict(row))

    def list_definitions(
        self, tenant_id: Optional[str] = None, owner_id: Optional[str] = None, include_inactive: bool = False
    ) -> List[WorkflowDefinition]:
        sql = "SELECT * FROM workflows WHERE 1=1"
        params: List[Any] = []
        if tenant_id:
            sql += " AND tenant_id = ?"
            params.append(tenant_id)
        if owner_id:
            sql += " AND owner_id = ?"
            params.append(owner_id)
        if not include_inactive:
            sql += " AND is_active = 1"
        sql += " ORDER BY name, version DESC"
        rows = self._conn.cursor().execute(sql, params).fetchall()
        return [WorkflowDefinition(**dict(r)) for r in rows]

    def soft_delete_definition(self, workflow_id: int) -> bool:
        cur = self._conn.cursor()
        cur.execute("UPDATE workflows SET is_active = 0, updated_at = ? WHERE id = ?", (_utcnow_iso(), workflow_id))
        self._conn.commit()
        return cur.rowcount > 0

    # ---------- Runs ----------
    def create_run(
        self,
        run_id: str,
        tenant_id: str,
        user_id: str,
        inputs: Dict[str, Any],
        workflow_id: Optional[int] = None,
        definition_version: Optional[int] = None,
        definition_snapshot: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO workflow_runs(
                run_id, tenant_id, workflow_id, status, status_reason, user_id, inputs_json, outputs_json,
                error, duration_ms, created_at, started_at, ended_at, definition_version, definition_snapshot_json,
                idempotency_key, session_id
            ) VALUES (?, ?, ?, 'queued', NULL, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                run_id,
                tenant_id,
                workflow_id,
                user_id,
                json.dumps(inputs or {}),
                _utcnow_iso(),
                definition_version,
                json.dumps(definition_snapshot) if definition_snapshot else None,
                idempotency_key,
                session_id,
            ),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        row = self._conn.cursor().execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
        return WorkflowRun(**dict(row)) if row else None

    def update_run_status(
        self,
        run_id: str,
        status: str,
        status_reason: Optional[str] = None,
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        started_at: Optional[str] = None,
        ended_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
        tokens_input: Optional[int] = None,
        tokens_output: Optional[int] = None,
        cost_usd: Optional[float] = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE workflow_runs
            SET status = ?, status_reason = ?, outputs_json = ?, error = ?,
                started_at = COALESCE(?, started_at), ended_at = COALESCE(?, ended_at),
                duration_ms = COALESCE(?, duration_ms),
                tokens_input = COALESCE(?, tokens_input),
                tokens_output = COALESCE(?, tokens_output),
                cost_usd = COALESCE(?, cost_usd)
            WHERE run_id = ?
            """,
            (
                status,
                status_reason,
                json.dumps(outputs) if outputs is not None else None,
                error,
                started_at,
                ended_at,
                duration_ms,
                tokens_input,
                tokens_output,
                cost_usd,
                run_id,
            ),
        )
        self._conn.commit()

    # ---------- Run control ----------
    def set_cancel_requested(self, run_id: str, cancel: bool = True) -> None:
        self._conn.execute(
            "UPDATE workflow_runs SET cancel_requested = ? WHERE run_id = ?",
            (1 if cancel else 0, run_id),
        )
        self._conn.commit()

    def is_cancel_requested(self, run_id: str) -> bool:
        row = self._conn.cursor().execute(
            "SELECT cancel_requested FROM workflow_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        return bool(row[0]) if row else False

    # ---------- Events ----------
    def append_event(
        self,
        tenant_id: str,
        run_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        step_run_id: Optional[str] = None,
    ) -> int:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT COALESCE(MAX(event_seq), 0) as max_seq FROM workflow_events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        next_seq = int(row["max_seq"]) + 1
        cur.execute(
            """
            INSERT INTO workflow_events(tenant_id, run_id, step_run_id, event_seq, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                run_id,
                step_run_id,
                next_seq,
                event_type,
                json.dumps(payload or {}),
                _utcnow_iso(),
            ),
        )
        self._conn.commit()
        return next_seq

    def get_events(self, run_id: str, since: Optional[int] = None, limit: int = 500) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM workflow_events WHERE run_id = ?"
        params: List[Any] = [run_id]
        if since is not None:
            sql += " AND event_seq > ?"
            params.append(int(since))
        sql += " ORDER BY event_seq ASC LIMIT ?"
        params.append(int(limit))
        rows = self._conn.cursor().execute(sql, params).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["payload_json"] = json.loads(d.get("payload_json") or "{}")
            except Exception:
                pass
            out.append(d)
        return out

    # ---------- Step Runs ----------
    def create_step_run(
        self,
        *,
        step_run_id: str,
        run_id: str,
        step_id: str,
        name: str,
        step_type: str,
        status: str = "running",
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO workflow_step_runs(
                step_run_id, run_id, step_id, name, type, status, started_at, inputs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_run_id,
                run_id,
                step_id,
                name,
                step_type,
                status,
                _utcnow_iso(),
                json.dumps(inputs or {}),
            ),
        )
        self._conn.commit()

    def complete_step_run(
        self,
        *,
        step_run_id: str,
        status: str = "succeeded",
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE workflow_step_runs
            SET status = ?, ended_at = ?, outputs_json = ?, error = ?
            WHERE step_run_id = ?
            """,
            (
                status,
                _utcnow_iso(),
                json.dumps(outputs or {}),
                error,
                step_run_id,
            ),
        )
        self._conn.commit()

    def update_step_attempt(self, *, step_run_id: str, attempt: int) -> None:
        """Persist the current attempt count for a step run."""
        self._conn.execute(
            "UPDATE workflow_step_runs SET attempt = ? WHERE step_run_id = ?",
            (int(attempt), step_run_id),
        )
        self._conn.commit()

    def get_last_failed_step_id(self, run_id: str) -> Optional[str]:
        row = self._conn.cursor().execute(
            "SELECT step_id FROM workflow_step_runs WHERE run_id = ? AND status = 'failed' ORDER BY ended_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        return row[0] if row else None

    def get_run_by_idempotency(self, tenant_id: str, user_id: str, idempotency_key: str) -> Optional[WorkflowRun]:
        row = self._conn.cursor().execute(
            "SELECT * FROM workflow_runs WHERE tenant_id = ? AND user_id = ? AND idempotency_key = ?",
            (tenant_id, user_id, idempotency_key),
        ).fetchone()
        return WorkflowRun(**dict(row)) if row else None

    def update_step_lock_and_heartbeat(
        self,
        *,
        step_run_id: str,
        locked_by: Optional[str] = None,
        lock_ttl_seconds: Optional[int] = None,
    ) -> None:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        locked_at = now.isoformat()
        lock_expires_at = None
        if lock_ttl_seconds is not None:
            lock_expires_at = (now + __import__("datetime").timedelta(seconds=lock_ttl_seconds)).isoformat()
        self._conn.execute(
            """
            UPDATE workflow_step_runs
            SET locked_by = COALESCE(?, locked_by), locked_at = ?, lock_expires_at = COALESCE(?, lock_expires_at), heartbeat_at = ?
            WHERE step_run_id = ?
            """,
            (
                locked_by,
                locked_at,
                lock_expires_at,
                locked_at,
                step_run_id,
            ),
        )
        self._conn.commit()

    def find_orphan_step_runs(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        sql = (
            "SELECT * FROM workflow_step_runs WHERE status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < ?)"
        )
        rows = self._conn.cursor().execute(sql, (cutoff_iso,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- Subprocess tracking ----------
    def update_step_subprocess(
        self,
        *,
        step_run_id: str,
        pid: Optional[int] = None,
        pgid: Optional[int] = None,
        workdir: Optional[str] = None,
        stdout_path: Optional[str] = None,
        stderr_path: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            """
            UPDATE workflow_step_runs
            SET pid = COALESCE(?, pid), pgid = COALESCE(?, pgid), workdir = COALESCE(?, workdir),
                stdout_path = COALESCE(?, stdout_path), stderr_path = COALESCE(?, stderr_path)
            WHERE step_run_id = ?
            """,
            (
                pid,
                pgid,
                workdir,
                stdout_path,
                stderr_path,
                step_run_id,
            ),
        )
        self._conn.commit()

    def find_running_subprocesses_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        sql = (
            "SELECT step_run_id, pid, pgid, workdir, stdout_path, stderr_path FROM workflow_step_runs "
            "WHERE run_id = ? AND status = 'running' AND (pid IS NOT NULL OR pgid IS NOT NULL)"
        )
        rows = self._conn.cursor().execute(sql, (run_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------- Artifacts ----------
    def add_artifact(
        self,
        *,
        artifact_id: str,
        tenant_id: str,
        run_id: str,
        step_run_id: Optional[str],
        type: str,
        uri: str,
        size_bytes: Optional[int] = None,
        mime_type: Optional[str] = None,
        checksum_sha256: Optional[str] = None,
        encryption: Optional[str] = None,
        owned_by: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO workflow_artifacts(
                artifact_id, tenant_id, run_id, step_run_id, type, uri, size_bytes, mime_type, checksum_sha256,
                encryption, owned_by, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                tenant_id,
                run_id,
                step_run_id,
                type,
                uri,
                size_bytes,
                mime_type,
                checksum_sha256,
                encryption,
                owned_by,
                json.dumps(metadata or {}),
                _utcnow_iso(),
            ),
        )
        self._conn.commit()

    def list_artifacts_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.cursor().execute(
            "SELECT * FROM workflow_artifacts WHERE run_id = ? ORDER BY created_at ASC",
            (run_id,),
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["metadata_json"] = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                pass
            out.append(d)
        return out


__all__ = ["WorkflowsDatabase", "WorkflowDefinition", "WorkflowRun", "DEFAULT_DB_PATH"]
