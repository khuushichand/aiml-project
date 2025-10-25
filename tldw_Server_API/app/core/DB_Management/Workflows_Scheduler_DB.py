"""
Workflows Scheduler database adapter.

Persists recurring workflow schedules (cron-based) used by the
Workflows Scheduler service.

Backed by the same DB backend factory used by the content DB
(SQLite by default; PostgreSQL supported).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import os
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from .backends.base import BackendType, DatabaseBackend, DatabaseConfig, QueryResult
from .backends.factory import DatabaseBackendFactory


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


SCHED_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_schedules (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    workflow_id INTEGER,
    name TEXT,
    cron TEXT NOT NULL,
    timezone TEXT,
    inputs_json TEXT NOT NULL,
    run_mode TEXT DEFAULT 'async',
    validation_mode TEXT DEFAULT 'block',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    -- Presence gating (only run when user is online)
    require_online BOOLEAN NOT NULL DEFAULT FALSE,
    -- Scheduling behavior
    concurrency_mode TEXT NOT NULL DEFAULT 'skip', -- 'skip' or 'queue'
    misfire_grace_sec INTEGER DEFAULT 300,
    coalesce BOOLEAN NOT NULL DEFAULT TRUE,
    jitter_sec INTEGER NOT NULL DEFAULT 0,
    -- History
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_status TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wf_sched_tenant ON workflow_schedules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_wf_sched_user ON workflow_schedules(user_id);
"""

SCHED_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_schedules (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    workflow_id INTEGER,
    name TEXT,
    cron TEXT NOT NULL,
    timezone TEXT,
    inputs_json TEXT NOT NULL,
    run_mode TEXT DEFAULT 'async',
    validation_mode TEXT DEFAULT 'block',
    enabled INTEGER NOT NULL DEFAULT 1,
    -- Presence gating (only run when user is online)
    require_online INTEGER NOT NULL DEFAULT 0,
    -- Scheduling behavior
    concurrency_mode TEXT NOT NULL DEFAULT 'skip', -- 'skip' or 'queue'
    misfire_grace_sec INTEGER DEFAULT 300,
    coalesce INTEGER NOT NULL DEFAULT 1,
    jitter_sec INTEGER NOT NULL DEFAULT 0,
    -- History
    last_run_at TEXT,
    next_run_at TEXT,
    last_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wf_sched_tenant ON workflow_schedules(tenant_id);
CREATE INDEX IF NOT EXISTS idx_wf_sched_user ON workflow_schedules(user_id);
"""


@dataclass
class WorkflowSchedule:
    id: str
    tenant_id: str
    user_id: str
    workflow_id: Optional[int]
    name: Optional[str]
    cron: str
    timezone: Optional[str]
    inputs_json: str
    run_mode: str
    validation_mode: str
    enabled: bool
    require_online: bool
    concurrency_mode: str
    misfire_grace_sec: int
    coalesce: bool
    jitter_sec: int
    last_run_at: Optional[str]
    next_run_at: Optional[str]
    last_status: Optional[str]
    created_at: str
    updated_at: str


class WorkflowsSchedulerDB:
    def __init__(self, backend: Optional[DatabaseBackend] = None, *, user_id: Optional[int] = None) -> None:
        if backend is not None:
            self.backend = backend
        else:
            cfg = DatabaseConfig.from_env()
            effective_user = user_id if user_id is not None else DatabasePaths.get_single_user_id()
            default_path = DatabasePaths.get_workflows_scheduler_db_path(effective_user)

            # Allow dedicated scheduler database URL override
            custom_url = os.getenv("WORKFLOWS_SCHEDULER_DATABASE_URL")
            if custom_url:
                parsed = urlparse(custom_url)
                scheme = (parsed.scheme or "").lower()
                if scheme in {"sqlite", ""}:
                    cfg.backend_type = BackendType.SQLITE
                    raw_path = parsed.path or ""
                    if raw_path.startswith("/./"):
                        raw_path = raw_path[1:]
                    if raw_path.startswith("/") and raw_path != "/:memory:":
                        candidate = Path(raw_path)
                    else:
                        candidate = Path(raw_path or default_path.name)
                        candidate = default_path.parent / candidate
                    cfg.sqlite_path = str(candidate)
                elif scheme in {"postgres", "postgresql"}:
                    cfg = DatabaseConfig(
                        backend_type=BackendType.POSTGRESQL,
                        connection_string=custom_url,
                    )
                    cfg.pg_host = parsed.hostname or "localhost"
                    try:
                        cfg.pg_port = int(parsed.port or 5432)
                    except Exception:
                        cfg.pg_port = 5432
                    cfg.pg_database = (parsed.path or "/").lstrip("/") or None
                    cfg.pg_user = parsed.username or None
                    cfg.pg_password = parsed.password or None
                # Other schemes fall back to default cfg

            # Allow explicit sqlite path override
            custom_path = os.getenv("WORKFLOWS_SCHEDULER_SQLITE_PATH")
            if custom_path:
                cfg.backend_type = BackendType.SQLITE
                cfg.sqlite_path = custom_path

            if cfg.backend_type == BackendType.SQLITE:
                sqlite_path_str = (cfg.sqlite_path or "").strip()
                default_candidates = {
                    "",
                    "./Databases/workflows_scheduler.db",
                    "Databases/workflows_scheduler.db",
                    "workflows_scheduler.db",
                    "./Databases/workflows.db",
                    "Databases/workflows.db",
                    "workflows.db",
                }
                if sqlite_path_str in default_candidates:
                    sqlite_path = default_path
                else:
                    sqlite_path = Path(sqlite_path_str)
                    if not sqlite_path.is_absolute():
                        sqlite_path = (default_path.parent / sqlite_path).resolve()
                try:
                    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    logger.error(f"WorkflowsSchedulerDB: failed to create directory {sqlite_path.parent}: {e}")
                    raise
                cfg.sqlite_path = str(sqlite_path)
                logger.info(f"WorkflowsSchedulerDB using SQLite path: {cfg.sqlite_path}")

            self.backend = DatabaseBackendFactory.create_backend(cfg)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        try:
            cfg = getattr(self.backend, "config", None)
            spath = getattr(cfg, "sqlite_path", None)
            if spath:
                logger.info(f"WorkflowsSchedulerDB using SQLite path: {spath}")
        except Exception:
            pass
        with self.backend.transaction() as conn:
            # Heuristically detect backend type by a capability
            try:
                self.backend.create_tables(SCHED_POSTGRES_SCHEMA, connection=conn)
            except Exception:
                # Fallback to SQLite schema if PG path fails
                self.backend.create_tables(SCHED_SQLITE_SCHEMA, connection=conn)
            # Idempotent column ensures for forward-additions (both backends)
            # PostgreSQL
            try:
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS concurrency_mode TEXT DEFAULT 'skip'",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS misfire_grace_sec INTEGER DEFAULT 300",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS coalesce BOOLEAN DEFAULT TRUE",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS require_online BOOLEAN DEFAULT FALSE",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMPTZ",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE workflow_schedules ADD COLUMN IF NOT EXISTS last_status TEXT",
                    connection=conn,
                )
            except Exception:
                # SQLite path: ALTER TABLE ADD COLUMN without IF NOT EXISTS; ignore failures
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN concurrency_mode TEXT", connection=conn)
                except Exception:
                    pass
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN misfire_grace_sec INTEGER", connection=conn)
                except Exception:
                    pass
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN coalesce INTEGER", connection=conn)
                except Exception:
                    pass
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN require_online INTEGER", connection=conn)
                except Exception:
                    pass
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN last_run_at TEXT", connection=conn)
                except Exception:
                    pass
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN next_run_at TEXT", connection=conn)
                except Exception:
                    pass
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN last_status TEXT", connection=conn)
                except Exception:
                    pass
                # Forward-add jitter_sec for pre-existing tables
                try:
                    self.backend.execute("ALTER TABLE workflow_schedules ADD COLUMN jitter_sec INTEGER DEFAULT 0", connection=conn)
                except Exception:
                    pass

    def _rows(self, result: QueryResult) -> List[Dict[str, Any]]:
        cols = [c[0] for c in (result.description or [])]
        out: List[Dict[str, Any]] = []
        for row in (result.rows or []):
            if isinstance(row, dict):
                # Already a mapping from the backend
                out.append(row)
                continue
            try:
                # Sequence row -> map by description
                mapping: Dict[str, Any] = {}
                for i, col in enumerate(cols):
                    mapping[col] = row[i]
                out.append(mapping)
            except Exception:
                # Fallback: best-effort conversion
                try:
                    out.append(dict(row))  # type: ignore[arg-type]
                except Exception:
                    out.append({})
        return out

    def create_schedule(
        self,
        *,
        id: str,
        tenant_id: str,
        user_id: str,
        workflow_id: Optional[int],
        name: Optional[str],
        cron: str,
        timezone: Optional[str],
        inputs: Dict[str, Any],
        run_mode: str = "async",
        validation_mode: str = "block",
        enabled: bool = True,
        require_online: bool = False,
        concurrency_mode: str = "skip",
        misfire_grace_sec: int = 300,
        coalesce: bool = True,
    ) -> None:
        now = _utcnow_iso()
        params = (
            id,
            tenant_id,
            user_id,
            workflow_id,
            name,
            cron,
            timezone,
            json.dumps(inputs or {}),
            run_mode,
            validation_mode,
            1 if enabled else 0,
            1 if require_online else 0,
            concurrency_mode,
            int(misfire_grace_sec),
            1 if coalesce else 0,
            0,
            None,
            None,
            None,
            now,
            now,
        )
        sql = (
            "INSERT INTO workflow_schedules("
            "id,tenant_id,user_id,workflow_id,name,cron,timezone,inputs_json,run_mode,validation_mode,enabled,require_online,"
            "concurrency_mode,misfire_grace_sec,coalesce,jitter_sec,last_run_at,next_run_at,last_status,created_at,updated_at"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        )
        with self.backend.transaction() as conn:
            self.backend.execute(sql, params, connection=conn)

    def update_schedule(self, id: str, update: Dict[str, Any]) -> bool:
        if not update:
            return False
        fields = []
        params: List[Any] = []
        for k, v in update.items():
            if k == "inputs":
                fields.append("inputs_json = ?")
                params.append(json.dumps(v or {}))
            elif k == "enabled":
                fields.append("enabled = ?")
                params.append(1 if bool(v) else 0)
            elif k == "require_online":
                fields.append("require_online = ?")
                params.append(1 if bool(v) else 0)
            elif k == "coalesce":
                fields.append("coalesce = ?")
                params.append(1 if bool(v) else 0)
            else:
                fields.append(f"{k} = ?")
                params.append(v)
        fields.append("updated_at = ?")
        params.append(_utcnow_iso())
        params.append(id)
        sql = f"UPDATE workflow_schedules SET {', '.join(fields)} WHERE id = ?"
        with self.backend.transaction() as conn:
            res = self.backend.execute(sql, tuple(params), connection=conn)
        return (getattr(res, "rowcount", 0) or 0) > 0

    def delete_schedule(self, id: str) -> bool:
        with self.backend.transaction() as conn:
            res = self.backend.execute("DELETE FROM workflow_schedules WHERE id = ?", (id,), connection=conn)
        return (getattr(res, "rowcount", 0) or 0) > 0

    def get_schedule(self, id: str) -> Optional[WorkflowSchedule]:
        with self.backend.transaction() as conn:
            res = self.backend.execute("SELECT * FROM workflow_schedules WHERE id = ?", (id,), connection=conn)
        rows = self._rows(res)
        if not rows:
            return None
        r = rows[0]
        return WorkflowSchedule(
            id=r["id"], tenant_id=r["tenant_id"], user_id=r["user_id"], workflow_id=r.get("workflow_id"), name=r.get("name"),
            cron=r["cron"], timezone=r.get("timezone"), inputs_json=r["inputs_json"], run_mode=r.get("run_mode") or "async",
            validation_mode=r.get("validation_mode") or "block", enabled=bool(r.get("enabled") in (1, True, "1")),
            require_online=bool(r.get("require_online") in (1, True, "1")),
            concurrency_mode=(r.get("concurrency_mode") or "skip"), misfire_grace_sec=int(r.get("misfire_grace_sec") or 300),
            coalesce=bool(r.get("coalesce") in (1, True, "1")), jitter_sec=int(r.get("jitter_sec") or 0), last_run_at=r.get("last_run_at"), next_run_at=r.get("next_run_at"),
            last_status=r.get("last_status"), created_at=r.get("created_at"), updated_at=r.get("updated_at")
        )

    def list_schedules(
        self,
        *,
        tenant_id: str,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[WorkflowSchedule]:
        params: List[Any] = [tenant_id]
        sql = "SELECT * FROM workflow_schedules WHERE tenant_id = ?"
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self.backend.transaction() as conn:
            res = self.backend.execute(sql, tuple(params), connection=conn)
        out: List[WorkflowSchedule] = []
        for r in self._rows(res):
            out.append(
                WorkflowSchedule(
                    id=r["id"], tenant_id=r["tenant_id"], user_id=r["user_id"], workflow_id=r.get("workflow_id"), name=r.get("name"),
                    cron=r["cron"], timezone=r.get("timezone"), inputs_json=r["inputs_json"], run_mode=r.get("run_mode") or "async",
                    validation_mode=r.get("validation_mode") or "block", enabled=bool(r.get("enabled") in (1, True, "1")),
                    require_online=bool(r.get("require_online") in (1, True, "1")),
                    concurrency_mode=(r.get("concurrency_mode") or "skip"), misfire_grace_sec=int(r.get("misfire_grace_sec") or 300),
                    coalesce=bool(r.get("coalesce") in (1, True, "1")), jitter_sec=int(r.get("jitter_sec") or 0), last_run_at=r.get("last_run_at"), next_run_at=r.get("next_run_at"),
                    last_status=r.get("last_status"), created_at=r.get("created_at"), updated_at=r.get("updated_at")
                )
            )
        return out

    # Convenience helpers to mutate history
    def set_history(self, id: str, *, last_run_at: Optional[str] = None, next_run_at: Optional[str] = None, last_status: Optional[str] = None) -> None:
        update: Dict[str, Any] = {}
        if last_run_at is not None:
            update["last_run_at"] = last_run_at
        if next_run_at is not None:
            update["next_run_at"] = next_run_at
        if last_status is not None:
            update["last_status"] = last_status
        if not update:
            return
        self.update_schedule(id, update)
