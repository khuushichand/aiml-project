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

from loguru import logger

from .backends.base import DatabaseBackend, QueryResult
from .backends.factory import DatabaseBackendFactory
from .backends.base import DatabaseConfig


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
    created_at: str
    updated_at: str


class WorkflowsSchedulerDB:
    def __init__(self, backend: Optional[DatabaseBackend] = None) -> None:
        if backend is not None:
            self.backend = backend
        else:
            cfg = DatabaseConfig.from_env()
            self.backend = DatabaseBackendFactory.create_backend(cfg)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.backend.transaction() as conn:
            # Heuristically detect backend type by a capability
            try:
                self.backend.create_tables(SCHED_POSTGRES_SCHEMA, connection=conn)
            except Exception:
                # Fallback to SQLite schema if PG path fails
                self.backend.create_tables(SCHED_SQLITE_SCHEMA, connection=conn)

    def _rows(self, result: QueryResult) -> List[Dict[str, Any]]:
        cols = [c[0] for c in (result.description or [])]
        out: List[Dict[str, Any]] = []
        for row in (result.rows or []):
            mapping: Dict[str, Any] = {}
            for i, col in enumerate(cols):
                mapping[col] = row[i]
            out.append(mapping)
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
            now,
            now,
        )
        sql = (
            "INSERT INTO workflow_schedules(id,tenant_id,user_id,workflow_id,name,cron,timezone,inputs_json,run_mode,validation_mode,enabled,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)"
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
            created_at=r.get("created_at"), updated_at=r.get("updated_at")
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
                    created_at=r.get("created_at"), updated_at=r.get("updated_at")
                )
            )
        return out

