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
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from .backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseError as BackendDatabaseError,
    QueryResult,
)
from .backends.query_utils import (
    prepare_backend_many_statement,
    prepare_backend_statement,
)


class WorkflowsSchemaError(RuntimeError):
    """Raised when workflow schema initialization or migration fails."""

    pass


DEFAULT_DB_PATH = DatabasePaths.get_workflows_db_path(DatabasePaths.get_single_user_id())


WORKFLOWS_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT 'private',
    description TEXT,
    tags TEXT,
    definition_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (tenant_id, name, version)
);

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
        created_at TIMESTAMPTZ NOT NULL,
        started_at TIMESTAMPTZ,
        ended_at TIMESTAMPTZ,
        definition_version INTEGER,
        definition_snapshot_json TEXT,
        idempotency_key TEXT,
        session_id TEXT,
        validation_mode TEXT DEFAULT 'block',
        tokens_input INTEGER,
        tokens_output INTEGER,
        cost_usd DOUBLE PRECISION,
        cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    );

CREATE TABLE IF NOT EXISTS workflow_step_runs (
    step_run_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    name TEXT,
    type TEXT,
    status TEXT,
    attempt INTEGER DEFAULT 0,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    inputs_json TEXT,
    outputs_json TEXT,
    error TEXT,
    decision TEXT,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    review_comment TEXT,
    locked_by TEXT,
    locked_at TIMESTAMPTZ,
    lock_expires_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    pid INTEGER,
    pgid INTEGER,
    workdir TEXT,
    stdout_path TEXT,
    stderr_path TEXT,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflow_events (
    event_id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_run_id TEXT,
    event_seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workflow_artifacts (
    artifact_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_run_id TEXT,
    type TEXT,
    uri TEXT,
    size_bytes BIGINT,
    mime_type TEXT,
    checksum_sha256 TEXT,
    encryption TEXT,
    owned_by TEXT,
    metadata_json TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflows_owner ON workflows(owner_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status);
    CREATE INDEX IF NOT EXISTS idx_events_run_seq ON workflow_events(run_id, event_seq);

-- Ensure uniqueness of per-run event sequence
    CREATE UNIQUE INDEX IF NOT EXISTS ux_events_run_seq ON workflow_events(run_id, event_seq);

-- Partial indexes on hot statuses for faster lookups
    CREATE INDEX IF NOT EXISTS idx_runs_status_running ON workflow_runs(status) WHERE status = 'running';
    CREATE INDEX IF NOT EXISTS idx_runs_status_queued ON workflow_runs(status) WHERE status = 'queued';
    CREATE INDEX IF NOT EXISTS idx_runs_status_succeeded ON workflow_runs(status) WHERE status = 'succeeded';
    CREATE INDEX IF NOT EXISTS idx_runs_status_failed ON workflow_runs(status) WHERE status = 'failed';

-- Per-run event sequence counters (optional optimization)
    CREATE TABLE IF NOT EXISTS workflow_event_counters (
        run_id TEXT PRIMARY KEY,
        next_seq INTEGER NOT NULL
    );

    -- Dead-letter queue for webhook deliveries (optional retry worker)
    CREATE TABLE IF NOT EXISTS workflow_webhook_dlq (
        id BIGSERIAL PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        run_id TEXT NOT NULL,
        url TEXT NOT NULL,
        body_json TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TIMESTAMPTZ,
        last_error TEXT,
        created_at TIMESTAMPTZ NOT NULL
    );
"""


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


class WorkflowRowAdapter:
    """Row wrapper that mimics sqlite3.Row semantics for backend results."""

    __slots__ = ("_mapping", "_columns")

    def __init__(self, mapping: Dict[str, Any], columns: Tuple[str, ...]):
        self._mapping = mapping
        self._columns = columns

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            column = self._columns[key]
            return self._mapping.get(column)
        return self._mapping.get(key)

    def __iter__(self):
        return iter(self.items())

    def items(self):
        for column in self._columns:
            yield column, self._mapping.get(column)

    def keys(self) -> Tuple[str, ...]:
        return self._columns

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._mapping)


class WorkflowsBackendCursorAdapter:
    """Adapter that provides sqlite-like fetch methods for backend QueryResult."""

    def __init__(self, result: QueryResult):
        self._result = result
        self._rows = self._build_rows(result)
        self._index = 0
        self.description = result.description or []

    def _build_rows(self, result: QueryResult) -> List[WorkflowRowAdapter]:
        rows: List[WorkflowRowAdapter] = []
        columns: Tuple[str, ...] = tuple()
        if result.description:
            columns = tuple(desc[0] for desc in result.description if desc)
        for mapping in result.rows:
            mapping_dict = dict(mapping)
            if not columns:
                columns = tuple(mapping_dict.keys())
            rows.append(WorkflowRowAdapter(mapping_dict, columns))
        return rows

    def fetchone(self) -> Optional[WorkflowRowAdapter]:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> List[WorkflowRowAdapter]:
        if self._index >= len(self._rows):
            return []
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows

    def fetchmany(self, size: Optional[int] = None) -> List[WorkflowRowAdapter]:
        if size is None or size <= 0:
            size = len(self._rows) - self._index
        rows = self._rows[self._index : self._index + size]
        self._index += len(rows)
        return rows

    def close(self) -> None:
        self._rows = []
        self._index = 0


class WorkflowsBackendCursor:
    """Cursor wrapper that routes SQL through a DatabaseBackend."""

    def __init__(self, db: 'WorkflowsDatabase'):
        self._db = db
        self._adapter: Optional[WorkflowsBackendCursorAdapter] = None
        self.rowcount: int = -1
        self.lastrowid: Optional[int] = None
        self.description = None

    def _requires_returning(self, query: str) -> bool:
        stripped = query.lstrip().upper()
        return stripped.startswith("INSERT")

    def execute(self, query: str, params: Optional[Any] = None):
        backend = self._db.backend
        if backend is None:
            raise RuntimeError("Backend cursor cannot execute without a backend instance")

        ensure_returning = self._requires_returning(query)
        prepared_query, prepared_params = prepare_backend_statement(
            backend.backend_type,
            query,
            params,
            apply_default_transform=True,
            ensure_returning=ensure_returning,
        )

        conn = None
        try:
            conn = backend.get_pool().get_connection()
            result = backend.execute(prepared_query, prepared_params, connection=conn)
        finally:
            if conn is not None:
                backend.get_pool().return_connection(conn)

        self._adapter = WorkflowsBackendCursorAdapter(result)
        self.rowcount = result.rowcount
        self.lastrowid = result.lastrowid
        self.description = result.description
        return self

    def executemany(self, query: str, params_list: List[Any]):
        backend = self._db.backend
        if backend is None:
            raise RuntimeError("Backend cursor cannot execute without a backend instance")

        prepared_query, prepared_params_list = prepare_backend_many_statement(
            backend.backend_type,
            query,
            params_list,
            apply_default_transform=True,
        )

        conn = None
        try:
            conn = backend.get_pool().get_connection()
            result = backend.execute_many(prepared_query, prepared_params_list, connection=conn)
        finally:
            if conn is not None:
                backend.get_pool().return_connection(conn)

        self._adapter = WorkflowsBackendCursorAdapter(result)
        self.rowcount = result.rowcount
        self.lastrowid = result.lastrowid
        self.description = result.description
        return self

    def fetchone(self):
        if not self._adapter:
            return None
        return self._adapter.fetchone()

    def fetchall(self):
        if not self._adapter:
            return []
        return self._adapter.fetchall()

    def fetchmany(self, size: Optional[int] = None):
        if not self._adapter:
            return []
        return self._adapter.fetchmany(size)

    def close(self) -> None:
        if self._adapter:
            self._adapter.close()
        self._adapter = None
        self.rowcount = -1
        self.lastrowid = None
        self.description = None


class WorkflowsBackendConnection:
    """Connection shim exposing sqlite-style helpers for backend usage."""

    def __init__(self, db: 'WorkflowsDatabase') -> None:
        self._db = db
        self.row_factory = None  # compatibility shim

    def cursor(self) -> WorkflowsBackendCursor:
        return WorkflowsBackendCursor(self._db)

    def execute(self, query: str, params: Optional[Any] = None):
        cursor = self.cursor()
        return cursor.execute(query, params)

    def executemany(self, query: str, params_list: List[Any]):
        cursor = self.cursor()
        return cursor.executemany(query, params_list)

    def commit(self) -> None:  # pragma: no cover - compatibility
        return None

    def rollback(self) -> None:  # pragma: no cover - compatibility
        return None

    def close(self) -> None:  # pragma: no cover - compatibility
        return None


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
    # Accounting fields (nullable)
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: Optional[float] = None
    validation_mode: Optional[str] = "block"


class WorkflowsDatabase:
    _CURRENT_SCHEMA_VERSION = 4
    """Workflow persistence adapter supporting SQLite and DatabaseBackend instances."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        backend: Optional[DatabaseBackend] = None,
    ) -> None:
        self.backend: Optional[DatabaseBackend] = None
        self.backend_type: BackendType = BackendType.SQLITE

        if backend and backend.backend_type == BackendType.POSTGRESQL:
            self.backend = backend
            self.backend_type = backend.backend_type
            self.db_path = str(db_path or DEFAULT_DB_PATH)
            self._conn = WorkflowsBackendConnection(self)
            self._initialize_schema_backend()
            logger.debug("Workflows DB initialized using %s backend", self.backend_type.value)
            return

        # Fallback to SQLite path (default behaviour)
        url = os.getenv("DATABASE_URL_WORKFLOWS", "").strip()
        if not db_path and url:
            if url.startswith("sqlite://"):
                path = url.split("sqlite://", 1)[1]
                if path.startswith("/") and not path.startswith("//"):
                    resolved = path
                else:
                    resolved = path.lstrip("/")
                db_path = resolved or str(DEFAULT_DB_PATH)
            else:
                logger.warning(
                    "DATABASE_URL_WORKFLOWS=%s is not a supported SQLite URI; falling back to default path",
                    url,
                )

        self.db_path = str(db_path or DEFAULT_DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._enable_wal()
        self._create_schema()
        # Optional lightweight SQLite connection pool for high-churn operations
        try:
            pool_size = int(os.getenv("WORKFLOWS_SQLITE_POOL_SIZE", "0"))
        except Exception:
            pool_size = 0
        self._sqlite_pool: List[sqlite3.Connection] = []
        if pool_size and pool_size > 0:
            for _ in range(max(0, pool_size - 1)):
                c = sqlite3.connect(self.db_path, check_same_thread=False)
                c.row_factory = sqlite3.Row
                try:
                    c.execute("PRAGMA journal_mode=WAL;")
                    c.execute("PRAGMA synchronous=NORMAL;")
                    c.execute("PRAGMA foreign_keys=ON;")
                    c.execute("PRAGMA busy_timeout=5000;")
                    c.execute("PRAGMA wal_autocheckpoint=1000;")
                except Exception:
                    pass
                self._sqlite_pool.append(c)
        logger.debug(f"Workflows DB initialized at {self.db_path}")

    # ------------------------------------------------------------------
    # Backend helpers
    # ------------------------------------------------------------------

    def _using_backend(self) -> bool:
        return self.backend is not None and self.backend_type == BackendType.POSTGRESQL

    def _execute_backend(
        self,
        query: str,
        params: Optional[Any] = None,
        *,
        connection: Any = None,
        ensure_returning: bool = False,
    ) -> QueryResult:
        if not self.backend:
            raise RuntimeError("Backend execution requested without configured backend")

        prepared_query, prepared_params = prepare_backend_statement(
            self.backend.backend_type,
            query,
            params,
            apply_default_transform=True,
            ensure_returning=ensure_returning,
        )
        return self.backend.execute(
            prepared_query,
            prepared_params,
            connection=connection,
        )

    def _execute_backend_many(
        self,
        query: str,
        params_list: Sequence[Any],
        *,
        connection: Any = None,
    ) -> QueryResult:
        if not self.backend:
            raise RuntimeError("Backend execution requested without configured backend")

        prepared_query, prepared_params_list = prepare_backend_many_statement(
            self.backend.backend_type,
            query,
            params_list,
            apply_default_transform=True,
        )
        return self.backend.execute_many(
            prepared_query,
            prepared_params_list,
            connection=connection,
        )

    @staticmethod
    def _rows_from_result(result: QueryResult) -> List[WorkflowRowAdapter]:
        adapter = WorkflowsBackendCursorAdapter(result)
        rows = adapter.fetchall()
        adapter.close()
        return rows

    @staticmethod
    def _row_from_result(result: QueryResult) -> Optional[WorkflowRowAdapter]:
        adapter = WorkflowsBackendCursorAdapter(result)
        row = adapter.fetchone()
        adapter.close()
        return row

    @staticmethod
    def _row_to_dict(row: Any) -> Dict[str, Any]:
        if isinstance(row, WorkflowRowAdapter):
            return row.to_dict()
        return dict(row)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release database resources for both SQLite and backend modes."""
        if self._using_backend():
            if self.backend is not None:
                try:
                    pool = self.backend.get_pool()
                except Exception:  # noqa: BLE001 - defensive
                    return
                if hasattr(pool, "close_all"):
                    pool.close_all()
            return

        # Close pooled connections first
        if hasattr(self, "_sqlite_pool") and self._sqlite_pool:
            for c in self._sqlite_pool:
                try:
                    c.close()
                except Exception:
                    pass
            self._sqlite_pool = []
        if hasattr(self, "_conn") and self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    def close_connection(self) -> None:
        """Backward-compatible alias expected by older callers/tests."""
        self.close()

    def _enable_wal(self) -> None:
        try:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            # Reduce writer stalls and enable periodic checkpoints
            self._conn.execute("PRAGMA busy_timeout=5000;")
            self._conn.execute("PRAGMA wal_autocheckpoint=1000;")
        except Exception as e:
            logger.warning(f"Failed to enable WAL on workflows DB: {e}")

    def _get_backend_schema_version(self, conn) -> int:
        if not self.backend:
            return 0

        backend = self.backend
        ident = backend.escape_identifier

        backend.execute(
            f"CREATE TABLE IF NOT EXISTS {ident('workflow_schema_version')} (version INTEGER NOT NULL)",
            connection=conn,
        )

        result = backend.execute(
            f"SELECT version FROM {ident('workflow_schema_version')} LIMIT 1",
            connection=conn,
        )
        if not result.rows:
            backend.execute(
                f"INSERT INTO {ident('workflow_schema_version')} (version) VALUES (%s)",
                (0,),
                connection=conn,
            )
            return 0
        return int(result.scalar or 0)

    def _set_backend_schema_version(self, conn, version: int) -> None:
        if not self.backend:
            return

        backend = self.backend
        ident = backend.escape_identifier
        result = backend.execute(
            f"UPDATE {ident('workflow_schema_version')} SET version = %s",
            (int(version),),
            connection=conn,
        )
        if result.rowcount == 0:
            backend.execute(
                f"INSERT INTO {ident('workflow_schema_version')} (version) VALUES (%s)",
                (int(version),),
                connection=conn,
            )

    def _run_backend_migrations(self, conn, current_version: int, target_version: int) -> int:
        if not self.backend:
            return current_version

        migrations = self._get_backend_migrations()
        applied_version = current_version

        for version in sorted(migrations.keys()):
            if applied_version < version <= target_version:
                migrations[version](conn)
                self._set_backend_schema_version(conn, version)
                applied_version = version

        if applied_version < target_version:
            raise WorkflowsSchemaError(
                f"Incomplete migration path for workflows backend schema (reached {applied_version}, expected {target_version})."
            )

        return applied_version

    def _get_backend_migrations(self):
        return {
            1: self._backend_migrate_to_v1,
            2: self._backend_migrate_to_v2,
            3: self._backend_migrate_to_v3,
            4: self._backend_migrate_to_v4,
        }

    def _backend_migrate_to_v1(self, conn) -> None:
        if not self.backend:
            return

        backend = self.backend
        ident = backend.escape_identifier

        column_additions = [
            ("workflow_runs", "cancel_requested", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("workflow_runs", "tokens_input", "INTEGER"),
            ("workflow_runs", "tokens_output", "INTEGER"),
            ("workflow_runs", "cost_usd", "DOUBLE PRECISION"),
            ("workflow_step_runs", "pid", "INTEGER"),
            ("workflow_step_runs", "pgid", "INTEGER"),
            ("workflow_step_runs", "workdir", "TEXT"),
            ("workflow_step_runs", "stdout_path", "TEXT"),
            ("workflow_step_runs", "stderr_path", "TEXT"),
        ]

        for table, column, column_type in column_additions:
            backend.execute(
                f"ALTER TABLE {ident(table)} ADD COLUMN IF NOT EXISTS {ident(column)} {column_type}",
                connection=conn,
            )

        backend.execute(
            f"CREATE TABLE IF NOT EXISTS {ident('workflow_artifacts')} ("
            f"artifact_id TEXT PRIMARY KEY,"
            f"tenant_id TEXT NOT NULL,"
            f"run_id TEXT NOT NULL,"
            f"step_run_id TEXT,"
            f"type TEXT,"
            f"uri TEXT,"
            f"size_bytes BIGINT,"
            f"mime_type TEXT,"
            f"checksum_sha256 TEXT,"
            f"encryption TEXT,"
            f"owned_by TEXT,"
            f"metadata_json TEXT,"
            f"created_at TIMESTAMPTZ NOT NULL,"
            f"FOREIGN KEY ({ident('run_id')}) REFERENCES {ident('workflow_runs')}({ident('run_id')})"
            ")",
            connection=conn,
        )

        backend.execute(
            f"CREATE INDEX IF NOT EXISTS {ident('idx_workflows_owner')} ON {ident('workflows')} ({ident('owner_id')})",
            connection=conn,
        )
        backend.execute(
            f"CREATE INDEX IF NOT EXISTS {ident('idx_runs_status')} ON {ident('workflow_runs')} ({ident('status')})",
            connection=conn,
        )
        backend.execute(
            f"CREATE INDEX IF NOT EXISTS {ident('idx_events_run_seq')} ON {ident('workflow_events')} ({ident('run_id')}, {ident('event_seq')})",
            connection=conn,
        )

        # Ensure uniqueness of per-run event sequence (idempotent via unique index)
        backend.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {ident('ux_events_run_seq')} ON {ident('workflow_events')} ({ident('run_id')}, {ident('event_seq')})",
            connection=conn,
        )

        # Event counters table (idempotent)
        backend.execute(
            f"CREATE TABLE IF NOT EXISTS {ident('workflow_event_counters')} ("
            f"run_id TEXT PRIMARY KEY,"
            f"next_seq INTEGER NOT NULL"
            ")",
            connection=conn,
        )

    def _backend_migrate_to_v2(self, conn) -> None:
        if not self.backend:
            return
        backend = self.backend
        ident = backend.escape_identifier
        # Add validation_mode to workflow_runs
        backend.execute(
            f"ALTER TABLE {ident('workflow_runs')} ADD COLUMN IF NOT EXISTS {ident('validation_mode')} TEXT DEFAULT 'block'",
            connection=conn,
        )

    def _backend_migrate_to_v3(self, conn) -> None:
        if not self.backend:
            return
        backend = self.backend
        ident = backend.escape_identifier

        # Convert payload_json to JSONB if needed
        try:
            backend.execute(
                f"ALTER TABLE {ident('workflow_events')} "
                f"ALTER COLUMN {ident('payload_json')} TYPE JSONB USING {ident('payload_json')}::jsonb",
                connection=conn,
            )
        except Exception:
            pass

        # Add GIN index on JSONB payloads
        try:
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_events_payload_json_gin')} "
                f"ON {ident('workflow_events')} USING GIN ({ident('payload_json')})",
                connection=conn,
            )
        except Exception:
            pass

        # Recreate FK constraints to cascade on run delete
        for table in ("workflow_events", "workflow_step_runs", "workflow_artifacts"):
            try:
                backend.execute(
                    f"ALTER TABLE {ident(table)} DROP CONSTRAINT IF EXISTS {ident(f'{table}_run_id_fkey')}",
                    connection=conn,
                )
            except Exception:
                pass
            try:
                backend.execute(
                    f"ALTER TABLE {ident(table)} ADD CONSTRAINT {ident(f'{table}_run_id_fkey')} "
                    f"FOREIGN KEY ({ident('run_id')}) REFERENCES {ident('workflow_runs')}({ident('run_id')}) ON DELETE CASCADE",
                    connection=conn,
                )
            except Exception:
                pass

        # Partial indexes for hot statuses
        try:
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_runs_status_running')} ON {ident('workflow_runs')}({ident('status')}) WHERE {ident('status')} = 'running'",
                connection=conn,
            )
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_runs_status_queued')} ON {ident('workflow_runs')}({ident('status')}) WHERE {ident('status')} = 'queued'",
                connection=conn,
            )
        except Exception:
            pass
        # Dead-letter queue table for webhooks
        backend.execute(
            f"CREATE TABLE IF NOT EXISTS {ident('workflow_webhook_dlq')} ("
            f"id BIGSERIAL PRIMARY KEY,"
            f"tenant_id TEXT NOT NULL,"
            f"run_id TEXT NOT NULL,"
            f"url TEXT NOT NULL,"
            f"body_json TEXT,"
            f"attempts INTEGER NOT NULL DEFAULT 0,"
            f"next_attempt_at TIMESTAMPTZ,"
            f"last_error TEXT,"
            f"created_at TIMESTAMPTZ NOT NULL"
            ")",
            connection=conn,
        )

    def _backend_migrate_to_v4(self, conn) -> None:
        if not self.backend:
            return
        backend = self.backend
        ident = backend.escape_identifier
        # Add additional partial indexes for common terminal statuses
        try:
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_runs_status_succeeded')} ON {ident('workflow_runs')}({ident('status')}) WHERE {ident('status')} = 'succeeded'",
                connection=conn,
            )
        except Exception:
            pass
        try:
            backend.execute(
                f"CREATE INDEX IF NOT EXISTS {ident('idx_runs_status_failed')} ON {ident('workflow_runs')}({ident('status')}) WHERE {ident('status')} = 'failed'",
                connection=conn,
            )
        except Exception:
            pass

    def _initialize_schema_backend(self) -> None:
        if not self.backend:
            return

        backend = self.backend
        target_version = self._CURRENT_SCHEMA_VERSION

        try:
            with backend.transaction() as conn:
                backend.create_tables(WORKFLOWS_POSTGRES_SCHEMA, connection=conn)
                current_version = self._get_backend_schema_version(conn)

                if current_version > target_version:
                    raise WorkflowsSchemaError(
                        "Workflows schema version is newer than supported by this release."
                    )

                applied_version = current_version

                if applied_version < target_version:
                    applied_version = self._run_backend_migrations(conn, applied_version, target_version)

                if applied_version != target_version:
                    self._set_backend_schema_version(conn, target_version)
        except WorkflowsSchemaError:
            raise
        except BackendDatabaseError as exc:
            logger.error("Failed to initialise workflows schema on backend: %s", exc)
            raise
        except Exception as exc:
            logger.error("Unexpected error while initialising workflows schema: %s", exc)
            raise

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
                validation_mode TEXT DEFAULT 'block',
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
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
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
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
            );
            """
        )

        # Indices
        cur.execute("CREATE INDEX IF NOT EXISTS idx_workflows_owner ON workflows(owner_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON workflow_runs(status)")
        # Partial indexes for frequently accessed statuses (supported on modern SQLite)
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_status_running ON workflow_runs(status) WHERE status = 'running'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_status_queued ON workflow_runs(status) WHERE status = 'queued'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_status_succeeded ON workflow_runs(status) WHERE status = 'succeeded'")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_runs_status_failed ON workflow_runs(status) WHERE status = 'failed'")
        except Exception:
            pass
        cur.execute("CREATE INDEX IF NOT EXISTS idx_events_run_seq ON workflow_events(run_id, event_seq)")
        # Ensure uniqueness of per-run event sequence
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_events_run_seq ON workflow_events(run_id, event_seq)")
        self._conn.commit()

        # Optional per-run event counters for SQLite
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_event_counters (
                run_id TEXT PRIMARY KEY,
                next_seq INTEGER NOT NULL
            );
            """
        )

        # Dead-letter queue for webhooks
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_webhook_dlq (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                url TEXT NOT NULL,
                body_json TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TEXT,
                last_error TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
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
                FOREIGN KEY(run_id) REFERENCES workflow_runs(run_id) ON DELETE CASCADE
            );
            """
        )
        self._conn.commit()

    # ---------- Definitions ----------

    # SQLite write helpers with backoff to mitigate 'database is locked' under bursts
    def _sqlite_retry_execute(self, query: str, params: Optional[Any] = None, *, max_tries: int = 5) -> None:
        import time as _time
        tries = 0
        while True:
            try:
                self._conn.execute(query, params or ())
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and tries < max_tries - 1:
                    _time.sleep(0.05 * (2 ** tries))
                    tries += 1
                    continue
                raise

    def _sqlite_retry_commit(self) -> None:
        import time as _time
        tries = 0
        while True:
            try:
                self._conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and tries < 4:
                    _time.sleep(0.05 * (2 ** tries))
                    tries += 1
                    continue
                raise

    def _acquire_sqlite(self) -> sqlite3.Connection:
        """Acquire a SQLite connection from pool if enabled, else return primary connection."""
        if getattr(self, "_sqlite_pool", None):
            try:
                return self._sqlite_pool.pop() if self._sqlite_pool else self._conn
            except Exception:
                return self._conn
        return self._conn

    def _release_sqlite(self, conn: sqlite3.Connection) -> None:
        if getattr(self, "_sqlite_pool", None) and conn is not self._conn:
            try:
                self._sqlite_pool.append(conn)
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
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
        now = _utcnow_iso()
        # For PostgreSQL backend, pass actual booleans for boolean columns;
        # SQLite accepts ints, but psycopg will map Python bool to BOOL.
        is_active_param = bool(is_active)
        params = (
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
            is_active_param,
        )

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(
                    """
                    INSERT INTO workflows(tenant_id, name, version, owner_id, visibility, description, tags, definition_json, created_at, updated_at, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    params,
                    connection=conn,
                    ensure_returning=True,
                )
            row = self._row_from_result(result)
            if row:
                return int(row["id"])
            if result.lastrowid is not None:
                return int(result.lastrowid)
            raise WorkflowsSchemaError("Failed to retrieve workflow id after insert")

        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO workflows(tenant_id, name, version, owner_id, visibility, description, tags, definition_json, created_at, updated_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def get_definition(self, workflow_id: int) -> Optional[WorkflowDefinition]:
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(
                    "SELECT * FROM workflows WHERE id = ?",
                    (workflow_id,),
                    connection=conn,
                )
            row = self._row_from_result(result)
            if not row:
                return None
            return WorkflowDefinition(**row.to_dict())

        row = self._conn.cursor().execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
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
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, tuple(params), connection=conn)
            rows = self._rows_from_result(result)
            return [WorkflowDefinition(**row.to_dict()) for row in rows]

        rows = self._conn.cursor().execute(sql, params).fetchall()
        return [WorkflowDefinition(**dict(r)) for r in rows]

    def soft_delete_definition(self, workflow_id: int) -> bool:
        params = (_utcnow_iso(), workflow_id)
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(
                    "UPDATE workflows SET is_active = 0, updated_at = ? WHERE id = ?",
                    params,
                    connection=conn,
                )
            return result.rowcount > 0

        cur = self._conn.cursor()
        cur.execute("UPDATE workflows SET is_active = 0, updated_at = ? WHERE id = ?", params)
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
        validation_mode: str = "block",
    ) -> None:
        params = (
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
            validation_mode,
        )

        query = """
            INSERT INTO workflow_runs(
                run_id, tenant_id, workflow_id, status, status_reason, user_id, inputs_json, outputs_json,
                error, duration_ms, created_at, started_at, ended_at, definition_version, definition_snapshot_json,
                idempotency_key, session_id, validation_mode
            ) VALUES (?, ?, ?, 'queued', NULL, ?, ?, NULL, NULL, NULL, ?, NULL, NULL, ?, ?, ?, ?, ?)
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return

        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                # Retry with backoff on lock contention
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    def get_run(self, run_id: str) -> Optional[WorkflowRun]:
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(
                    "SELECT * FROM workflow_runs WHERE run_id = ?",
                    (run_id,),
                    connection=conn,
                )
            row = self._row_from_result(result)
            return WorkflowRun(**row.to_dict()) if row else None

        row = self._conn.cursor().execute("SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
        return WorkflowRun(**dict(row)) if row else None

    def list_runs(
        self,
        *,
        tenant_id: str,
        user_id: Optional[str] = None,
        statuses: Optional[List[str]] = None,
        workflow_id: Optional[int] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        cursor_ts: Optional[str] = None,
        cursor_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_desc: bool = True,
    ) -> List[WorkflowRun]:
        sql = "SELECT * FROM workflow_runs WHERE tenant_id = ?"
        params: List[Any] = [tenant_id]
        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            sql += f" AND status IN ({placeholders})"
            params.extend(list(statuses))
        if workflow_id is not None:
            sql += " AND workflow_id = ?"
            params.append(int(workflow_id))
        if created_after:
            sql += " AND created_at >= ?"
            params.append(created_after)
        if created_before:
            sql += " AND created_at <= ?"
            params.append(created_before)
        # Whitelist order_by to known columns
        allowed_order = {"created_at", "started_at", "ended_at"}
        ob = order_by if order_by in allowed_order else "created_at"
        # Apply cursor seek if provided (seek pagination)
        if cursor_ts and cursor_id:
            cmp = "<" if order_desc else ">"
            # Add tie-breaker on run_id; for DESC use run_id < last_id if same ts, for ASC use run_id > last_id
            tcmp = "<" if order_desc else ">"
            sql += f" AND (({ob} {cmp} ?) OR ({ob} = ? AND run_id {tcmp} ?))"
            params.extend([cursor_ts, cursor_ts, cursor_id])
            # When using cursor, ignore numeric offset to avoid skipping
            sql += f" ORDER BY {ob} {'DESC' if order_desc else 'ASC'}, run_id {'DESC' if order_desc else 'ASC'} LIMIT ?"
            params.extend([int(limit)])
        else:
            # Stable ordering with tie-breaker by run_id
            sql += f" ORDER BY {ob} {'DESC' if order_desc else 'ASC'}, run_id {'DESC' if order_desc else 'ASC'} LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, tuple(params), connection=conn)
            rows = self._rows_from_result(result)
            return [WorkflowRun(**row.to_dict()) for row in rows]

        cur = self._conn.cursor()
        rows = cur.execute(sql, params).fetchall()
        return [WorkflowRun(**dict(r)) for r in rows]

    # ---------- Quotas / Usage ----------
    def count_runs_for_user_window(
        self,
        *,
        tenant_id: str,
        user_id: str,
        window_start_iso: str,
        window_end_iso: Optional[str] = None,
    ) -> int:
        """Count runs created by a user within an ISO time window [start, end]."""
        sql = "SELECT COUNT(*) AS c FROM workflow_runs WHERE tenant_id = ? AND user_id = ? AND created_at >= ?"
        params: List[Any] = [tenant_id, user_id, window_start_iso]
        if window_end_iso:
            sql += " AND created_at < ?"
            params.append(window_end_iso)

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, tuple(params), connection=conn)
            row = self._row_from_result(result)
            try:
                return int(row[0]) if row is not None else 0
            except Exception:
                return int((row.get("c") if row else 0) or 0)

        cur = self._conn.cursor()
        row = cur.execute(sql, params).fetchone()
        if not row:
            return 0
        try:
            return int(row[0])
        except Exception:
            try:
                return int(row.get("c") or 0)  # type: ignore[attr-defined]
            except Exception:
                return 0

    def count_runs_for_tenant_window(
        self,
        *,
        tenant_id: str,
        window_start_iso: str,
        window_end_iso: Optional[str] = None,
    ) -> int:
        """Count runs created within a tenant over a time window."""
        sql = "SELECT COUNT(*) AS c FROM workflow_runs WHERE tenant_id = ? AND created_at >= ?"
        params: List[Any] = [tenant_id, window_start_iso]
        if window_end_iso:
            sql += " AND created_at < ?"
            params.append(window_end_iso)

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, tuple(params), connection=conn)
            row = self._row_from_result(result)
            try:
                return int(row[0]) if row is not None else 0
            except Exception:
                return int((row.get("c") if row else 0) or 0)

        cur = self._conn.cursor()
        row = cur.execute(sql, params).fetchone()
        if not row:
            return 0
        try:
            return int(row[0])
        except Exception:
            try:
                return int(row.get("c") or 0)  # type: ignore[attr-defined]
            except Exception:
                return 0

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
        params = (
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
        )

        query = """
            UPDATE workflow_runs
            SET status = ?, status_reason = ?, outputs_json = ?, error = ?,
                started_at = COALESCE(?, started_at), ended_at = COALESCE(?, ended_at),
                duration_ms = COALESCE(?, duration_ms),
                tokens_input = COALESCE(?, tokens_input),
                tokens_output = COALESCE(?, tokens_output),
                cost_usd = COALESCE(?, cost_usd)
            WHERE run_id = ?
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
        else:
            try:
                self._conn.execute(query, params)
                self._conn.commit()
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower():
                    self._sqlite_retry_execute(query, params)
                    self._sqlite_retry_commit()
                else:
                    raise
        try:
            from loguru import logger as _logger
            _logger.debug(f"WorkflowsDB: run {run_id} -> status={status}")
        except Exception:
            pass

    # ---------- Run control ----------
    def set_cancel_requested(self, run_id: str, cancel: bool = True) -> None:
        params = (bool(cancel), run_id)
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(
                    "UPDATE workflow_runs SET cancel_requested = ? WHERE run_id = ?",
                    params,
                    connection=conn,
                )
            return

        try:
            self._conn.execute("UPDATE workflow_runs SET cancel_requested = ? WHERE run_id = ?", params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute("UPDATE workflow_runs SET cancel_requested = ? WHERE run_id = ?", params)
                self._sqlite_retry_commit()
            else:
                raise

    def is_cancel_requested(self, run_id: str) -> bool:
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(
                    "SELECT cancel_requested FROM workflow_runs WHERE run_id = ?",
                    (run_id,),
                    connection=conn,
                )
            row = self._row_from_result(result)
            return bool(row[0]) if row else False

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
        # Prefer per-run counters when available
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                # Increment or initialize per-run counter atomically
                try:
                    # Use upsert to bump counter and read back the new value
                    inc = self._execute_backend(
                        """
                        INSERT INTO workflow_event_counters(run_id, next_seq)
                        VALUES (?, 1)
                        ON CONFLICT (run_id) DO UPDATE SET next_seq = workflow_event_counters.next_seq + 1
                        RETURNING next_seq
                        """,
                        (run_id,),
                        connection=conn,
                    )
                    r = self._row_from_result(inc)
                    next_seq = int(r["next_seq"]) if r else 1
                except Exception:
                    # Fallback to aggregate
                    seq_result = self._execute_backend(
                        "SELECT COALESCE(MAX(event_seq), 0) AS max_seq FROM workflow_events WHERE run_id = ?",
                        (run_id,),
                        connection=conn,
                    )
                    row = self._row_from_result(seq_result)
                    max_seq = int(row["max_seq"]) if row else 0
                    next_seq = max_seq + 1
                self._execute_backend(
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
                    connection=conn,
                )
                return next_seq

        # SQLite path
        conn = self._acquire_sqlite()
        cur = conn.cursor()
        try:
            # Try per-run counter with a short critical section
            row = cur.execute(
                "SELECT next_seq FROM workflow_event_counters WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if not row:
                next_seq = 1
                cur.execute(
                    "INSERT OR IGNORE INTO workflow_event_counters(run_id, next_seq) VALUES (?, ?)",
                    (run_id, next_seq),
                )
            else:
                current = int(row[0] if not isinstance(row, dict) else row.get("next_seq", 0))
                next_seq = current + 1
                cur.execute(
                    "UPDATE workflow_event_counters SET next_seq = ? WHERE run_id = ?",
                    (next_seq, run_id),
                )
        except Exception:
            # Fallback to aggregate scan if counters table missing
            row = cur.execute(
                "SELECT COALESCE(MAX(event_seq), 0) as max_seq FROM workflow_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            next_seq = int((row["max_seq"] if isinstance(row, dict) else row[0])) + 1

        params_insert = (
            tenant_id,
            run_id,
            step_run_id,
            next_seq,
            event_type,
            json.dumps(payload or {}),
            _utcnow_iso(),
        )
        try:
            cur.execute(
                """
                INSERT INTO workflow_events(tenant_id, run_id, step_run_id, event_seq, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                params_insert,
            )
            conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                # Retry on lock contention
                self._sqlite_retry_execute(
                    """
                    INSERT INTO workflow_events(tenant_id, run_id, step_run_id, event_seq, event_type, payload_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    params_insert,
                )
                self._sqlite_retry_commit()
            else:
                raise
        self._release_sqlite(conn)
        return next_seq

    def get_events(self, run_id: str, since: Optional[int] = None, limit: int = 500, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM workflow_events WHERE run_id = ?"
        params: List[Any] = [run_id]
        if since is not None:
            sql += " AND event_seq > ?"
            params.append(int(since))
        if types:
            placeholders = ",".join(["?"] * len(types))
            sql += f" AND event_type IN ({placeholders})"
            params.extend(list(types))
        # Stable ordering: primary by event_seq (per-run unique), tie-breaker by event_id
        sql += " ORDER BY event_seq ASC, event_id ASC LIMIT ?"
        params.append(int(limit))
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, tuple(params), connection=conn)
            rows = self._rows_from_result(result)
        else:
            conn = self._acquire_sqlite()
            try:
                rows = conn.cursor().execute(sql, params).fetchall()
            finally:
                self._release_sqlite(conn)

        out: List[Dict[str, Any]] = []
        for r in rows:
            data = self._row_to_dict(r)
            try:
                data["payload_json"] = json.loads(data.get("payload_json") or "{}")
            except Exception:
                pass
            out.append(data)
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
        params = (
            step_run_id,
            run_id,
            step_id,
            name,
            step_type,
            status,
            _utcnow_iso(),
            json.dumps(inputs or {}),
        )

        query = """
            INSERT INTO workflow_step_runs(
                step_run_id, run_id, step_id, name, type, status, started_at, inputs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return

        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    def complete_step_run(
        self,
        *,
        step_run_id: str,
        status: str = "succeeded",
        outputs: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        params = (
            status,
            _utcnow_iso(),
            json.dumps(outputs or {}),
            error,
            step_run_id,
        )
        query = """
            UPDATE workflow_step_runs
            SET status = ?, ended_at = ?, outputs_json = ?, error = ?
            WHERE step_run_id = ?
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return

        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    def update_step_attempt(self, *, step_run_id: str, attempt: int) -> None:
        """Persist the current attempt count for a step run."""
        params = (int(attempt), step_run_id)
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(
                    "UPDATE workflow_step_runs SET attempt = ? WHERE step_run_id = ?",
                    params,
                    connection=conn,
                )
            return

        try:
            self._conn.execute(
                "UPDATE workflow_step_runs SET attempt = ? WHERE step_run_id = ?",
                params,
            )
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute("UPDATE workflow_step_runs SET attempt = ? WHERE step_run_id = ?", params)
                self._sqlite_retry_commit()
            else:
                raise

    def get_last_failed_step_id(self, run_id: str) -> Optional[str]:
        query = (
            "SELECT step_id FROM workflow_step_runs WHERE run_id = ? AND status = 'failed' "
            "ORDER BY ended_at DESC LIMIT 1"
        )
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(query, (run_id,), connection=conn)
            row = self._row_from_result(result)
            return row[0] if row else None

        row = self._conn.cursor().execute(query, (run_id,)).fetchone()
        return row[0] if row else None

    def get_run_by_idempotency(self, tenant_id: str, user_id: str, idempotency_key: str) -> Optional[WorkflowRun]:
        params = (tenant_id, user_id, idempotency_key)
        query = "SELECT * FROM workflow_runs WHERE tenant_id = ? AND user_id = ? AND idempotency_key = ?"
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(query, params, connection=conn)
            row = self._row_from_result(result)
            return WorkflowRun(**row.to_dict()) if row else None

        row = self._conn.cursor().execute(query, params).fetchone()
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
        params = (
            locked_by,
            locked_at,
            lock_expires_at,
            locked_at,
            step_run_id,
        )
        query = """
            UPDATE workflow_step_runs
            SET locked_by = COALESCE(?, locked_by), locked_at = ?, lock_expires_at = COALESCE(?, lock_expires_at), heartbeat_at = ?
            WHERE step_run_id = ?
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return

        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise
        try:
            from loguru import logger as _logger
            _logger.debug(f"WorkflowsDB: heartbeat step_run_id={step_run_id}")
        except Exception:
            pass

    def find_orphan_step_runs(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        sql = (
            "SELECT * FROM workflow_step_runs WHERE status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < ?)"
        )
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, (cutoff_iso,), connection=conn)
            rows = self._rows_from_result(result)
        else:
            rows = self._conn.cursor().execute(sql, (cutoff_iso,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

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
        params = (
            pid,
            pgid,
            workdir,
            stdout_path,
            stderr_path,
            step_run_id,
        )
        query = """
            UPDATE workflow_step_runs
            SET pid = COALESCE(?, pid), pgid = COALESCE(?, pgid), workdir = COALESCE(?, workdir),
                stdout_path = COALESCE(?, stdout_path), stderr_path = COALESCE(?, stderr_path)
            WHERE step_run_id = ?
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return

        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    def find_running_subprocesses_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        sql = (
            "SELECT step_run_id, pid, pgid, workdir, stdout_path, stderr_path FROM workflow_step_runs "
            "WHERE run_id = ? AND status = 'running' AND (pid IS NOT NULL OR pgid IS NOT NULL)"
        )
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, (run_id,), connection=conn)
            rows = self._rows_from_result(result)
        else:
            rows = self._conn.cursor().execute(sql, (run_id,)).fetchall()
        return [self._row_to_dict(r) for r in rows]

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
        params = (
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
        )
        query = """
            INSERT INTO workflow_artifacts(
                artifact_id, tenant_id, run_id, step_run_id, type, uri, size_bytes, mime_type, checksum_sha256,
                encryption, owned_by, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return

        try:
            self._conn.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    def list_artifacts_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM workflow_artifacts WHERE run_id = ? ORDER BY created_at ASC"
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, (run_id,), connection=conn)
            rows = self._rows_from_result(result)
        else:
            rows = self._conn.cursor().execute(sql, (run_id,)).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            data = self._row_to_dict(r)
            # Decode metadata_json; attempt to decrypt if envelope present and key available
            md: Dict[str, Any] = {}
            try:
                md = json.loads(data.get("metadata_json") or "{}")
                if isinstance(md, dict) and "_encrypted" in md:
                    try:
                        from tldw_Server_API.app.core.Security.crypto import decrypt_json_blob
                        dec = decrypt_json_blob(md.get("_encrypted") or {})
                        if isinstance(dec, dict):
                            md = dec
                        else:
                            # Hide encrypted content when key not available
                            md = {"_encrypted": True}
                    except Exception:
                        md = {"_encrypted": True}
            except Exception:
                pass
            data["metadata_json"] = md
            out.append(data)
        return out

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM workflow_artifacts WHERE artifact_id = ?"
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(query, (artifact_id,), connection=conn)
            row = self._row_from_result(result)
            if not row:
                return None
            data = row.to_dict()
        else:
            row = self._conn.cursor().execute(query, (artifact_id,)).fetchone()
            if not row:
                return None
            data = dict(row)

        try:
            md = json.loads(data.get("metadata_json") or "{}")
            if isinstance(md, dict) and "_encrypted" in md:
                try:
                    from tldw_Server_API.app.core.Security.crypto import decrypt_json_blob
                    dec = decrypt_json_blob(md.get("_encrypted") or {})
                    if isinstance(dec, dict):
                        md = dec
                    else:
                        md = {"_encrypted": True}
                except Exception:
                    md = {"_encrypted": True}
            data["metadata_json"] = md
        except Exception:
            pass
        return data

    def delete_artifact(self, artifact_id: str) -> None:
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend("DELETE FROM workflow_artifacts WHERE artifact_id = ?", (artifact_id,), connection=conn)
            return
        cur = self._conn.cursor()
        try:
            cur.execute("DELETE FROM workflow_artifacts WHERE artifact_id = ?", (artifact_id,))
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute("DELETE FROM workflow_artifacts WHERE artifact_id = ?", (artifact_id,))
                self._sqlite_retry_commit()
            else:
                raise

    def list_artifacts_older_than(self, cutoff_iso: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM workflow_artifacts WHERE created_at < ?"
        rows: List[Any]
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                result = self._execute_backend(sql, (cutoff_iso,), connection=conn)
            rows = self._rows_from_result(result)
        else:
            rows = self._conn.cursor().execute(sql, (cutoff_iso,)).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(self._row_to_dict(r))
        return out

    # ---------- Human-in-the-loop decisions ----------
    def approve_step_decision(
        self,
        *,
        run_id: str,
        step_id: str,
        approved_by: str,
        comment: Optional[str] = None,
    ) -> None:
        """Mark step decision approved and set final status to succeeded for matching rows.

        For v0.1, we update all rows matching run_id and step_id.
        """
        params = ("approved", approved_by, _utcnow_iso(), comment or "", "succeeded", run_id, step_id)
        query = (
            "UPDATE workflow_step_runs SET decision = ?, approved_by = ?, approved_at = ?, review_comment = ?, status = ? "
            "WHERE run_id = ? AND step_id = ?"
        )
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return
        cur = self._conn.cursor()
        try:
            cur.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    # ---------- Webhook DLQ ----------
    def enqueue_webhook_dlq(self, *, tenant_id: str, run_id: str, url: str, body: Optional[Dict[str, Any]] = None, last_error: Optional[str] = None) -> None:
        params = (
            tenant_id,
            run_id,
            url,
            json.dumps(body or {}),
            0,
            None,
            last_error or "",
            _utcnow_iso(),
        )
        query = """
            INSERT INTO workflow_webhook_dlq(
                tenant_id, run_id, url, body_json, attempts, next_attempt_at, last_error, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return
        cur = self._conn.cursor()
        try:
            cur.execute(query, params)
            self._conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._sqlite_retry_execute(query, params)
                self._sqlite_retry_commit()
            else:
                raise

    def list_webhook_dlq_due(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        """Return DLQ rows that are due for retry (next_attempt_at is null or <= now).

        Results are ordered by next_attempt_at (nulls first via COALESCE to created_at) then id for stability.
        """
        if self._using_backend():
            query = (
                "SELECT id, tenant_id, run_id, url, body_json, attempts, next_attempt_at, last_error, created_at "
                "FROM workflow_webhook_dlq "
                "WHERE next_attempt_at IS NULL OR next_attempt_at <= NOW() "
                "ORDER BY COALESCE(next_attempt_at, created_at) ASC, id ASC "
                "LIMIT %s"
            )
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                rows = self._fetchall_backend(query, (limit,), connection=conn)
            return [dict(r) if isinstance(r, dict) else {
                "id": r[0], "tenant_id": r[1], "run_id": r[2], "url": r[3], "body_json": r[4],
                "attempts": r[5], "next_attempt_at": r[6], "last_error": r[7], "created_at": r[8]
            } for r in rows or []]
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT id, tenant_id, run_id, url, body_json, attempts, next_attempt_at, last_error, created_at
            FROM workflow_webhook_dlq
            WHERE next_attempt_at IS NULL OR next_attempt_at <= datetime('now')
            ORDER BY COALESCE(next_attempt_at, created_at) ASC, id ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows or []:
            try:
                out.append({
                    "id": r[0],
                    "tenant_id": r[1],
                    "run_id": r[2],
                    "url": r[3],
                    "body_json": r[4],
                    "attempts": r[5],
                    "next_attempt_at": r[6],
                    "last_error": r[7],
                    "created_at": r[8],
                })
            except Exception:
                # Attempt dict row style access (when using row_factory)
                out.append({
                    "id": r.get("id"),
                    "tenant_id": r.get("tenant_id"),
                    "run_id": r.get("run_id"),
                    "url": r.get("url"),
                    "body_json": r.get("body_json"),
                    "attempts": r.get("attempts"),
                    "next_attempt_at": r.get("next_attempt_at"),
                    "last_error": r.get("last_error"),
                    "created_at": r.get("created_at"),
                })
        return out

    def delete_webhook_dlq(self, *, dlq_id: int) -> None:
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend("DELETE FROM workflow_webhook_dlq WHERE id = %s", (dlq_id,), connection=conn)
            return
        cur = self._conn.cursor()
        cur.execute("DELETE FROM workflow_webhook_dlq WHERE id = ?", (dlq_id,))
        self._conn.commit()

    def update_webhook_dlq_failure(self, *, dlq_id: int, last_error: str, next_attempt_at_iso: Optional[str], attempts: Optional[int] = None) -> None:
        """Update DLQ row after a failed attempt.

        If attempts is provided, set to that value; else increment by 1.
        """
        if self._using_backend():
            if attempts is None:
                query = (
                    "UPDATE workflow_webhook_dlq SET attempts = attempts + 1, last_error = %s, next_attempt_at = %s WHERE id = %s"
                )
                params = (last_error, next_attempt_at_iso, dlq_id)
            else:
                query = (
                    "UPDATE workflow_webhook_dlq SET attempts = %s, last_error = %s, next_attempt_at = %s WHERE id = %s"
                )
                params = (attempts, last_error, next_attempt_at_iso, dlq_id)
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return
        cur = self._conn.cursor()
        if attempts is None:
            cur.execute(
                "UPDATE workflow_webhook_dlq SET attempts = attempts + 1, last_error = ?, next_attempt_at = ? WHERE id = ?",
                (last_error, next_attempt_at_iso, dlq_id),
            )
        else:
            cur.execute(
                "UPDATE workflow_webhook_dlq SET attempts = ?, last_error = ?, next_attempt_at = ? WHERE id = ?",
                (attempts, last_error, next_attempt_at_iso, dlq_id),
            )
        self._conn.commit()

    def list_webhook_dlq_all(self, *, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List all DLQ rows with stable ordering (admin UI)."""
        if self._using_backend():
            query = (
                "SELECT id, tenant_id, run_id, url, body_json, attempts, next_attempt_at, last_error, created_at "
                "FROM workflow_webhook_dlq ORDER BY created_at ASC, id ASC LIMIT %s OFFSET %s"
            )
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                rows = self._fetchall_backend(query, (int(limit), int(offset)), connection=conn)
            return [dict(r) if isinstance(r, dict) else {
                "id": r[0], "tenant_id": r[1], "run_id": r[2], "url": r[3], "body_json": r[4],
                "attempts": r[5], "next_attempt_at": r[6], "last_error": r[7], "created_at": r[8]
            } for r in rows or []]
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT id, tenant_id, run_id, url, body_json, attempts, next_attempt_at, last_error, created_at
            FROM workflow_webhook_dlq
            ORDER BY created_at ASC, id ASC
            LIMIT ? OFFSET ?
            """,
            (int(limit), int(offset)),
        )
        rows = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows or []:
            try:
                out.append({
                    "id": r[0],
                    "tenant_id": r[1],
                    "run_id": r[2],
                    "url": r[3],
                    "body_json": r[4],
                    "attempts": r[5],
                    "next_attempt_at": r[6],
                    "last_error": r[7],
                    "created_at": r[8],
                })
            except Exception:
                out.append({
                    "id": r.get("id"),
                    "tenant_id": r.get("tenant_id"),
                    "run_id": r.get("run_id"),
                    "url": r.get("url"),
                    "body_json": r.get("body_json"),
                    "attempts": r.get("attempts"),
                    "next_attempt_at": r.get("next_attempt_at"),
                    "last_error": r.get("last_error"),
                    "created_at": r.get("created_at"),
                })
        return out

    def reject_step_decision(
        self,
        *,
        run_id: str,
        step_id: str,
        approved_by: str,
        comment: Optional[str] = None,
    ) -> None:
        """Mark step decision rejected and set status to failed for matching rows."""
        params = ("rejected", approved_by, _utcnow_iso(), comment or "", "failed", run_id, step_id)
        query = (
            "UPDATE workflow_step_runs SET decision = ?, approved_by = ?, approved_at = ?, review_comment = ?, status = ? "
            "WHERE run_id = ? AND step_id = ?"
        )
        if self._using_backend():
            with self.backend.transaction() as conn:  # type: ignore[union-attr]
                self._execute_backend(query, params, connection=conn)
            return
        cur = self._conn.cursor()
        cur.execute(query, params)
        self._conn.commit()


__all__ = ["WorkflowsDatabase", "WorkflowDefinition", "WorkflowRun", "DEFAULT_DB_PATH"]
