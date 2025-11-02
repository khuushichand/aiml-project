# PromptStudioDatabase.py
# Database management for Prompt Studio feature
# Extends PromptsDatabase to add Prompt Studio specific functionality

import json
import os
import re
import sqlite3
import threading
import uuid
from configparser import ConfigParser
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union
try:  # psycopg v3 preferred; fall back to psycopg2 if installed
    from psycopg import sql as psycopg_sql  # type: ignore
except Exception:  # pragma: no cover
    try:
        from psycopg2 import sql as psycopg_sql  # type: ignore
    except Exception:  # pragma: no cover
        psycopg_sql = None  # type: ignore

from loguru import logger

# Local imports
from .Prompts_DB import PromptsDatabase, DatabaseError, SchemaError, InputError, ConflictError
from .backends.base import (
    BackendType,
    DatabaseBackend,
    DatabaseError as BackendDatabaseError,
    QueryResult,
)
from .backends.query_utils import (
    convert_sqlite_placeholders_to_postgres,
    normalise_params,
    prepare_backend_many_statement,
    prepare_backend_statement,
    replace_collate_nocase,
    replace_insert_or_ignore,
    transform_sqlite_query_for_postgres,
)
from .backends.fts_translator import FTSQueryTranslator


def _serialise_tags(tags: Optional[Union[str, Iterable[str]]]) -> Optional[str]:
    """Convert tag collections to a comma-separated string for storage."""

    if tags is None:
        return None

    if isinstance(tags, str):
        return tags

    try:
        return ",".join(
            [
                str(tag).strip()
                for tag in tags
                if str(tag).strip()
            ]
        ) or None
    except TypeError:
        return None


def _parse_tags(value: Any) -> List[str]:
    """Convert stored tag payloads into a list representation."""

    if value is None:
        return []

    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]

    if isinstance(value, str):
        return [segment.strip() for segment in value.split(",") if segment.strip()]

    try:
        decoded = bytes(value).decode("utf-8") if isinstance(value, (bytes, bytearray, memoryview)) else None
    except Exception:  # pragma: no cover - defensive
        decoded = None

    if decoded:
        return [segment.strip() for segment in decoded.split(",") if segment.strip()]

    return []


def _format_test_case_record(record: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalise Prompt Studio test case payloads for caller consumption."""

    if record is None:
        return None

    normalised = dict(record)
    normalised["tags"] = _parse_tags(normalised.get("tags"))

    # Ensure boolean fields surface as bools for both backends
    for field in ("is_golden", "is_generated", "deleted"):
        if field in normalised and normalised[field] is not None:
            normalised[field] = bool(normalised[field])

    # JSON fields sometimes arrive as strings; best-effort decoding
    for json_field in ("inputs", "expected_outputs", "actual_outputs"):
        value = normalised.get(json_field)
        if isinstance(value, str):
            try:
                normalised[json_field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

    return normalised


########################################################################################################################
# Backend cursor/connection helpers


class PromptStudioRowAdapter:
    """Row object that mimics sqlite3.Row semantics for consumers."""

    __slots__ = ("_mapping", "_columns")

    def __init__(self, mapping: Dict[str, Any], columns: Tuple[str, ...]):
        self._mapping = mapping
        self._columns = columns

    def __getitem__(self, key: Union[int, str]) -> Any:
        if isinstance(key, int):
            # Prefer named lookup when column metadata is a simple string
            try:
                col = self._columns[key]
                if isinstance(col, str) and isinstance(self._mapping, dict):
                    return self._mapping.get(col)
            except Exception:
                pass
            # Fallback: positional access over mapping values
            if isinstance(self._mapping, dict):
                try:
                    return list(self._mapping.values())[key]
                except Exception:
                    return None
            return None
        return self._mapping.get(key)

    def __iter__(self):
        for column in self._columns:
            yield self._mapping.get(column)

    def keys(self) -> Tuple[str, ...]:
        return self._columns

    def items(self):
        for column in self._columns:
            yield column, self._mapping.get(column)

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._mapping)


class PromptStudioBackendCursorAdapter:
    """Adapter that provides sqlite-like cursor behaviour for QueryResult objects."""

    def __init__(self, result: QueryResult):
        self._result = result
        self._index = 0
        self.rowcount = result.rowcount
        self.lastrowid = result.lastrowid
        self.description = result.description or []
        self._columns: Tuple[str, ...] = tuple(
            desc[0] if isinstance(desc, (list, tuple)) and desc else desc
            for desc in (self.description or [])
        )

    def _wrap_row(self, row: Any) -> PromptStudioRowAdapter:
        if isinstance(row, PromptStudioRowAdapter):
            return row
        if isinstance(row, dict):
            mapping = row
            columns = self._columns or tuple(mapping.keys())
        else:
            # Assume it's a sequence aligned with description
            columns = self._columns
            mapping = {columns[idx]: row[idx] for idx in range(len(columns))}
        return PromptStudioRowAdapter(mapping, columns)

    def fetchone(self) -> Optional[PromptStudioRowAdapter]:
        if self._index >= len(self._result.rows):
            return None
        row = self._result.rows[self._index]
        self._index += 1
        return self._wrap_row(row)

    def fetchall(self) -> List[PromptStudioRowAdapter]:
        rows = self._result.rows[self._index :]
        self._index = len(self._result.rows)
        return [self._wrap_row(row) for row in rows]

    def fetchmany(self, size: Optional[int] = None) -> List[PromptStudioRowAdapter]:
        if size is None or size <= 0:
            size = len(self._result.rows) - self._index
        end = min(self._index + size, len(self._result.rows))
        rows = self._result.rows[self._index : end]
        self._index = end
        return [self._wrap_row(row) for row in rows]

    def close(self) -> None:
        self._result = QueryResult(rows=[], rowcount=0)
        self.rowcount = 0
        self.lastrowid = None
        self.description = None
        self._columns = tuple()


class PromptStudioBackendCursorWrapper:
    """Cursor wrapper that routes SQL through the configured DatabaseBackend."""

    def __init__(self, db: 'BackendPromptStudioDatabaseBase', connection: Any):
        self._db = db
        self._connection = connection
        self._result: Optional[QueryResult] = None
        self._adapter: Optional[PromptStudioBackendCursorAdapter] = None
        self.rowcount: int = -1
        self.lastrowid: Optional[int] = None
        self.description = None
        self._columns: Tuple[str, ...] = tuple()

    def execute(self, query: str, params: Optional[Union[Tuple, List, Dict, Any]] = None):
        import sqlite3

        prepared_query, prepared_params = self._db._prepare_backend_statement(query, params)
        try:
            self._result = self._db.backend.execute(
                prepared_query,
                prepared_params,
                connection=self._connection,
            )
        except BackendDatabaseError as exc:
            msg = str(exc)
            if "duplicate" in msg.lower() or "unique constraint" in msg.lower():
                raise sqlite3.IntegrityError(msg)
            raise DatabaseError(f"Backend query execution failed: {msg}") from exc

        self._adapter = PromptStudioBackendCursorAdapter(self._result)
        self.rowcount = self._result.rowcount
        self.lastrowid = self._result.lastrowid
        self.description = self._adapter.description
        self._columns = self._adapter._columns
        return self

    def executemany(self, query: str, params_list: List[Union[Tuple, List, Dict, Any]]):
        import sqlite3

        prepared_query, prepared_params_list = self._db._prepare_backend_many_statement(query, params_list)
        try:
            self._result = self._db.backend.execute_many(
                prepared_query,
                prepared_params_list,
                connection=self._connection,
            )
        except BackendDatabaseError as exc:
            msg = str(exc)
            if "duplicate" in msg.lower() or "unique constraint" in msg.lower():
                raise sqlite3.IntegrityError(msg)
            raise DatabaseError(f"Backend batch execution failed: {msg}") from exc

        self._adapter = PromptStudioBackendCursorAdapter(self._result)
        self.rowcount = self._result.rowcount
        self.lastrowid = self._result.lastrowid
        self.description = self._adapter.description
        self._columns = self._adapter._columns
        return self

    def fetchone(self) -> Optional[Dict[str, Any]]:
        row = self._adapter.fetchone() if self._adapter else None
        return row

    def fetchall(self) -> List[Dict[str, Any]]:
        return self._adapter.fetchall() if self._adapter else []

    def fetchmany(self, size: Optional[int] = None) -> List[Dict[str, Any]]:
        return self._adapter.fetchmany(size) if self._adapter else []

    def close(self) -> None:
        if self._adapter:
            self._adapter.close()
        self._adapter = None
        self._result = None
        self.rowcount = -1
        self.lastrowid = None
        self.description = None


class PromptStudioBackendConnectionWrapper:
    """Connection wrapper exposing sqlite-like API backed by DatabaseBackend."""

    def __init__(self, db: 'BackendPromptStudioDatabaseBase', connection: Any):
        self._db = db
        self.raw_connection = connection

    def cursor(self):
        return PromptStudioBackendCursorWrapper(self._db, self.raw_connection)

    def execute(self, query: str, params: Optional[Union[Tuple, List, Dict, Any]] = None):
        cursor = self.cursor()
        return cursor.execute(query, params)

    def executemany(self, query: str, params_list: List[Union[Tuple, List, Dict, Any]]):
        cursor = self.cursor()
        return cursor.executemany(query, params_list)

    def commit(self):
        return self.raw_connection.commit()

    def rollback(self):
        return self.raw_connection.rollback()

    @property
    def closed(self) -> bool:
        return getattr(self.raw_connection, "closed", False)


class PromptStudioBackendManagedTransaction:
    """Context manager leveraging the backend's native transaction handling."""

    def __init__(self, db: 'BackendPromptStudioDatabaseBase'):
        self._db = db
        self._ctx = None
        self._conn = None

    def __enter__(self):
        self._ctx = self._db.backend.transaction()
        raw_conn = self._ctx.__enter__()
        self._conn = PromptStudioBackendConnectionWrapper(self._db, raw_conn)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._ctx is None:
            return False
        return self._ctx.__exit__(exc_type, exc_val, exc_tb)


########################################################################################################################
# Backend-aware Prompt Studio implementation (PostgreSQL)


class BackendPromptStudioDatabaseBase:
    """Common helpers for backend-backed Prompt Studio database implementations."""

    def __init__(
        self,
        db_path: Union[str, Path],
        client_id: str,
        *,
        backend: Optional[DatabaseBackend] = None,
        config: Optional[ConfigParser] = None,
    ) -> None:
        if backend is None:
            raise ValueError("Prompt Studio backend database requires an explicit DatabaseBackend instance")

        self.backend = backend
        self.backend_type = backend.backend_type
        if self.backend_type != BackendType.POSTGRESQL:
            raise ValueError(
                f"BackendPromptStudioDatabaseBase only supports PostgreSQL backends; received {self.backend_type.value}"
            )

        self.client_id = client_id
        self._config = config
        self.db_path = Path(db_path) if not isinstance(db_path, Path) else db_path
        self.db_path_str = str(self.db_path)
        self._local = threading.local()
        self._write_lock = threading.RLock()

        class _ConnCloseProxy:
            def __init__(self, outer: 'BackendPromptStudioDatabaseBase'):
                self._outer = outer

            def close(self) -> None:  # pragma: no cover - compatibility shim
                try:
                    self._outer.close_connection()
                except Exception:
                    pass

        self.conn = _ConnCloseProxy(self)

    # --- Connection handling ---
    def _open_new_connection(self):
        try:
            pool = self.backend.get_pool()
            return pool.get_connection()
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to acquire backend connection: {exc}") from exc

    def _release_connection(self, wrapper: Optional[PromptStudioBackendConnectionWrapper]) -> None:
        if not wrapper:
            return
        try:
            raw_conn = wrapper.raw_connection
            self.backend.get_pool().return_connection(raw_conn)
        except BackendDatabaseError as exc:
            logger.warning("Error returning backend connection to pool: %s", exc)

    def _get_thread_connection(self) -> PromptStudioBackendConnectionWrapper:
        wrapper: Optional[PromptStudioBackendConnectionWrapper] = getattr(self._local, 'conn', None)
        if wrapper is not None and not wrapper.closed:
            return wrapper

        raw_conn = self._open_new_connection()
        # Apply per-tenant session guard for PostgreSQL (RLS via current_setting('app.current_user_id'))
        try:
            if self.backend_type == BackendType.POSTGRESQL and self.client_id:
                cur = raw_conn.cursor()
                user_value = str(self.client_id)
                if psycopg_sql is not None:  # type: ignore[name-defined]
                    stmt = psycopg_sql.SQL("SET SESSION app.current_user_id = {}").format(
                        psycopg_sql.Literal(user_value)
                    )
                    cur.execute(stmt)
                else:
                    safe_value = user_value.replace("'", "''")
                    cur.execute(f"SET SESSION app.current_user_id = '{safe_value}'")
                try:
                    raw_conn.commit()
                except Exception:
                    pass
        except Exception:
            # Non-fatal if SET fails
            pass
        wrapper = PromptStudioBackendConnectionWrapper(self, raw_conn)
        self._local.conn = wrapper
        logger.debug(
            "Acquired Prompt Studio backend connection (%s) for thread %s",
            self.backend_type.value,
            threading.get_ident(),
        )
        return wrapper

    def get_connection(self) -> PromptStudioBackendConnectionWrapper:
        return self._get_thread_connection()

    def close_connection(self) -> None:
        wrapper: Optional[PromptStudioBackendConnectionWrapper] = getattr(self._local, 'conn', None)
        if wrapper is None:
            return

        try:
            if wrapper.raw_connection and getattr(wrapper.raw_connection, 'in_transaction', False):
                try:
                    wrapper.rollback()
                except Exception:
                    pass
            self._release_connection(wrapper)
        finally:
            self._local.conn = None

    def close(self) -> None:
        self.close_connection()

    @contextmanager
    def transaction(self) -> Iterable[PromptStudioBackendConnectionWrapper]:
        ctx = PromptStudioBackendManagedTransaction(self)
        conn = ctx.__enter__()
        try:
            yield conn
            ctx.__exit__(None, None, None)
        except Exception as exc:  # noqa: BLE001
            ctx.__exit__(exc.__class__, exc, exc.__traceback__)
            raise

    # --- Query preparation helpers ---
    def _prepare_backend_statement(
        self,
        query: str,
        params: Optional[Union[Tuple, List, Dict, Any]] = None,
    ) -> Tuple[str, Optional[Union[Tuple, Dict]]]:
        return prepare_backend_statement(
            self.backend_type,
            query,
            params,
            apply_default_transform=True,
            ensure_returning=True,
        )

    def _prepare_backend_many_statement(
        self,
        query: str,
        params_list: List[Union[Tuple, List, Dict, Any]],
    ) -> Tuple[str, List[Optional[Union[Tuple, Dict]]]]:
        return prepare_backend_many_statement(
            self.backend_type,
            query,
            params_list,
            apply_default_transform=True,
            ensure_returning=False,
        )

    # Convenience for subclasses
    def _execute(
        self,
        query: str,
        params: Optional[Union[Tuple, List, Dict, Any]] = None,
        *,
        connection: Optional[PromptStudioBackendConnectionWrapper] = None,
    ) -> PromptStudioBackendCursorWrapper:
        conn = connection or self.get_connection()
        cursor = conn.cursor()
        return cursor.execute(query, params)

    def _executemany(
        self,
        query: str,
        params_list: List[Union[Tuple, List, Dict, Any]],
        *,
        connection: Optional[PromptStudioBackendConnectionWrapper] = None,
    ) -> PromptStudioBackendCursorWrapper:
        conn = connection or self.get_connection()
        cursor = conn.cursor()
        return cursor.executemany(query, params_list)


class _BackendPromptStudioDatabase(BackendPromptStudioDatabaseBase):
    """PostgreSQL-backed Prompt Studio database implementation."""

    _SCHEMA_VERSION = 1
    _MIGRATION_FILES_SQL = [
        "001_prompt_studio_schema.sql",
        "003_prompt_studio_iterations.sql",
        "002_prompt_studio_indexes.sql",
        # 003 triggers file intentionally omitted (no-op placeholder)
        # 004 FTS handled via backend abstraction
        "005_add_chunking_templates.sql",
    ]

    _FTS_CONFIG = (
        ("prompt_studio_projects", ["name", "description"]),
        ("prompt_studio_prompts", ["name", "system_prompt", "user_prompt"]),
        ("prompt_studio_test_cases", ["name", "description", "tags"]),
    )

    _JSON_FIELDS = {
        "metadata",
        "input_schema",
        "output_schema",
        "constraints",
        "validation_rules",
        "few_shot_examples",
        "modules_config",
        "model_params",
        "inputs",
        "outputs",
        "expected_outputs",
        "actual_outputs",
        "scores",
        "test_case_ids",
        "test_run_ids",
        "aggregate_metrics",
        "model_configs",
        "payload",
        "result",
        "initial_metrics",
        "final_metrics",
        "optimization_config",
        "prompt_variant",
        "metrics",
    }

    _DATETIME_FIELDS = {
        "created_at",
        "updated_at",
        "deleted_at",
        "last_modified",
        "started_at",
        "completed_at",
    }

    _MIGRATIONS_DIR = Path(__file__).parent / "migrations"

    def __init__(
        self,
        db_path: Union[str, Path],
        client_id: str,
        *,
        backend: Optional[DatabaseBackend] = None,
        config: Optional[ConfigParser] = None,
    ) -> None:
        super().__init__(db_path, client_id, backend=backend, config=config)
        self._fts_columns = {
            table: f"{table}_tsv" for table, _columns in self._FTS_CONFIG
        }
        self._initialize_schema_postgres()

    def _cursor_exec(self, conn: Any, query: str, params: Optional[Union[Tuple, List, Dict, Any]] = None):
        """Execute a query using the backend's parameter style.

        Converts SQLite-style placeholders to PostgreSQL, then executes using the
        provided psycopg connection. Returns a native cursor with description set.
        """
        q, p = self._prepare_backend_statement(query, params)
        cur = conn.cursor()
        if p is not None:
            cur.execute(q, p)
        else:
            cur.execute(q)
        return cur

    # --- Schema management ---
    def _initialize_schema_postgres(self) -> None:
        with self.backend.transaction() as conn:
            self._ensure_extensions(conn)
            if not self.backend.table_exists('prompt_studio_projects', connection=conn):
                self._apply_postgres_migrations(conn)
            # Ensure auxiliary tables exist even on existing DBs (idempotency mapping)
            try:
                self.backend.execute(
                    (
                        "CREATE TABLE IF NOT EXISTS prompt_studio_idempotency ("
                        " id BIGSERIAL PRIMARY KEY,"
                        " entity_type TEXT NOT NULL,"
                        " idempotency_key TEXT NOT NULL,"
                        " entity_id BIGINT NOT NULL,"
                        " user_id TEXT,"
                        " created_at TIMESTAMPTZ DEFAULT NOW()"
                        ")"
                    ),
                    connection=conn,
                )
                # Composite uniqueness per user
                self.backend.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ps_idem_user ON prompt_studio_idempotency(entity_type, idempotency_key, user_id)",
                    connection=conn,
                )
                self.backend.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ps_idem_entity ON prompt_studio_idempotency(entity_type, user_id)",
                    connection=conn,
                )
                # Note: Postgres idempotency helpers are implemented in this class
                # via _idem_lookup/_idem_record and scoped by (entity_type, idempotency_key, user_id).
            except BackendDatabaseError as exc:
                raise SchemaError(f"Failed to ensure idempotency table: {exc}") from exc
            # Ensure leasing columns exist on job queue
            try:
                self.backend.execute(
                    "ALTER TABLE prompt_studio_job_queue ADD COLUMN IF NOT EXISTS leased_until TIMESTAMPTZ",
                    connection=conn,
                )
                self.backend.execute(
                    "ALTER TABLE prompt_studio_job_queue ADD COLUMN IF NOT EXISTS lease_owner TEXT",
                    connection=conn,
                )
            except BackendDatabaseError:
                # Older Postgres versions may not support IF NOT EXISTS on ADD COLUMN; fall back
                try:
                    # Probe column existence; if missing, add without IF NOT EXISTS
                    self.backend.execute(
                        "SELECT leased_until FROM prompt_studio_job_queue LIMIT 1",
                        connection=conn,
                    )
                except BackendDatabaseError:
                    self.backend.execute(
                        "ALTER TABLE prompt_studio_job_queue ADD COLUMN leased_until TIMESTAMPTZ",
                        connection=conn,
                    )
                try:
                    self.backend.execute(
                        "SELECT lease_owner FROM prompt_studio_job_queue LIMIT 1",
                        connection=conn,
                    )
                except BackendDatabaseError:
                    self.backend.execute(
                        "ALTER TABLE prompt_studio_job_queue ADD COLUMN lease_owner TEXT",
                        connection=conn,
                    )
        self._ensure_postgres_fts()

    def _ensure_extensions(self, conn) -> None:
        try:
            self.backend.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto", connection=conn)
        except BackendDatabaseError as exc:
            raise SchemaError(f"Failed enabling pgcrypto extension: {exc}") from exc

    def _apply_postgres_migrations(self, conn) -> None:
        for filename in self._MIGRATION_FILES_SQL:
            migration_path = self._MIGRATIONS_DIR / filename
            if not migration_path.exists():
                logger.warning("Prompt Studio migration file missing: %s", migration_path)
                continue
            sql = migration_path.read_text()
            statements = self._convert_sqlite_schema_to_postgres_statements(sql)
            for statement in statements:
                try:
                    self.backend.execute(statement, connection=conn)
                except BackendDatabaseError as exc:
                    raise SchemaError(f"Failed applying migration {filename}: {exc}") from exc

    def _ensure_postgres_fts(self) -> None:
        for source_table, columns in self._FTS_CONFIG:
            try:
                self.backend.create_fts_table(
                    table_name=source_table,
                    source_table=source_table,
                    columns=list(columns),
                )
            except BackendDatabaseError as exc:
                raise SchemaError(f"Failed to provision Prompt Studio FTS ({source_table}): {exc}") from exc

    def get_fts_column(self, table_name: str) -> Optional[str]:
        return getattr(self, "_fts_columns", {}).get(table_name)

    def _convert_sqlite_schema_to_postgres_statements(self, sql: str) -> List[str]:
        statements: List[str] = []
        buffer: List[str] = []
        in_block_comment = False
        in_trigger_block = False

        for raw_line in sql.splitlines():
            stripped = raw_line.strip()

            if not stripped:
                continue

            if in_block_comment:
                if '*/' in stripped:
                    in_block_comment = False
                continue

            if stripped.startswith('/*'):
                if '*/' not in stripped:
                    in_block_comment = True
                continue

            if stripped.startswith('--'):
                continue

            upper = stripped.upper()

            if upper.startswith('PRAGMA'):
                continue

            if in_trigger_block:
                # Skip lines belonging to a trigger block until semicolon
                if ';' in stripped:
                    in_trigger_block = False
                continue

            if 'CREATE VIRTUAL TABLE' in upper:
                # handled by backend FTS helpers
                continue

            if upper.startswith('INSERT INTO') and 'FTS' in upper:
                continue

            if upper.startswith('DROP TRIGGER') or upper.startswith('CREATE TRIGGER'):
                # Skip entire trigger block (SQLite syntax not supported in Postgres)
                in_trigger_block = True
                continue

            buffer.append(raw_line)

            if stripped.endswith(';'):
                statement = '\n'.join(buffer).strip()
                buffer = []
                transformed = self._transform_sqlite_statement_for_postgres(statement)
                if transformed:
                    statements.append(transformed)

        return statements

    # --- Idempotency helpers (Postgres) ---
    def _idem_lookup(self, entity_type: str, key: str, user_id: Optional[str]) -> Optional[int]:
        try:
            cursor = self._execute(
                """
                SELECT entity_id
                FROM prompt_studio_idempotency
                WHERE entity_type = ?
                  AND idempotency_key = ?
                  AND (user_id = ? OR user_id IS NULL)
                LIMIT 1
                """,
                (entity_type, key, user_id),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None
        except BackendDatabaseError:
            return None

    def _idem_record(self, entity_type: str, key: str, entity_id: int, user_id: Optional[str]) -> None:
        try:
            # INSERT OR IGNORE is translated to ON CONFLICT DO NOTHING for Postgres by the query adapter
            self._execute(
                "INSERT OR IGNORE INTO prompt_studio_idempotency (entity_type, idempotency_key, entity_id, user_id) VALUES (?, ?, ?, ?)",
                (entity_type, key, entity_id, user_id),
            )
        except BackendDatabaseError:
            pass

    def _transform_sqlite_statement_for_postgres(self, statement: str) -> Optional[str]:
        stmt = statement.strip()
        if not stmt:
            return None

        # Normalize whitespace for easier regex handling
        stmt = re.sub(r'\s+', ' ', stmt)

        # Column conversions
        stmt = re.sub(
            r'INTEGER PRIMARY KEY AUTOINCREMENT',
            'BIGSERIAL PRIMARY KEY',
            stmt,
            flags=re.IGNORECASE,
        )
        stmt = re.sub(
            r'INTEGER PRIMARY KEY',
            'BIGSERIAL PRIMARY KEY',
            stmt,
            flags=re.IGNORECASE,
        )

        def _replace_randomblob_default(match: re.Match[str]) -> str:
            prefix = match.group(1)
            return f"{prefix}encode(gen_random_bytes(16), 'hex')"

        stmt = re.sub(
            r'(DEFAULT\s*)\(LOWER\(HEX\(RANDOMBLOB\(16\)\)\)\)',
            _replace_randomblob_default,
            stmt,
            flags=re.IGNORECASE,
        )

        # Column-specific boolean conversions
        stmt = re.sub(r'(\bdeleted\b\s+)INTEGER\s+DEFAULT\s+0', r'\1BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'(\bis_golden\b\s+)INTEGER\s+DEFAULT\s+0', r'\1BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'(\bis_generated\b\s+)INTEGER\s+DEFAULT\s+0', r'\1BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'(\bis_builtin\b\s+)BOOLEAN\s+DEFAULT\s+0', r'\1BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)

        # Handle BOOLEAN defaults regardless of NOT NULL placement
        # e.g., "BOOLEAN NOT NULL DEFAULT 0" or "BOOLEAN DEFAULT 0 NOT NULL"
        stmt = re.sub(r'BOOLEAN\s+NOT\s+NULL\s+DEFAULT\s+0', 'BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+NOT\s+NULL\s+DEFAULT\s+1', 'BOOLEAN NOT NULL DEFAULT TRUE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+DEFAULT\s+0\s+NOT\s+NULL', 'BOOLEAN NOT NULL DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+DEFAULT\s+1\s+NOT\s+NULL', 'BOOLEAN NOT NULL DEFAULT TRUE', stmt, flags=re.IGNORECASE)
        # Simple form without NOT NULL
        stmt = re.sub(r'BOOLEAN\s+DEFAULT\s+0', 'BOOLEAN DEFAULT FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'BOOLEAN\s+DEFAULT\s+1', 'BOOLEAN DEFAULT TRUE', stmt, flags=re.IGNORECASE)

        stmt = re.sub(r'JSON\b', 'JSONB', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'DATETIME', 'TIMESTAMPTZ', stmt, flags=re.IGNORECASE)

        stmt = replace_collate_nocase(stmt)
        stmt = replace_insert_or_ignore(stmt)
        # Normalize boolean comparisons in indexes/constraints (e.g., WHERE deleted = 0)
        stmt = re.sub(r'\bdeleted\s*=\s*0\b', 'deleted = FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'\bdeleted\s*=\s*1\b', 'deleted = TRUE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'\bis_builtin\s*=\s*0\b', 'is_builtin = FALSE', stmt, flags=re.IGNORECASE)
        stmt = re.sub(r'\bis_builtin\s*=\s*1\b', 'is_builtin = TRUE', stmt, flags=re.IGNORECASE)

        if not stmt.endswith(';'):
            stmt = f"{stmt};"

        return stmt

    # NOTE: Removed a duplicated, misplaced idempotency helpers block here.
    # The correct implementations exist within the PromptStudioDatabase class
    # later in this file. Keeping only one canonical definition avoids
    # indentation/scope issues during import.

    # --- Data helpers ---
    def _row_to_dict(self, cursor, row: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        if row is None:
            row_obj = cursor
        else:
            row_obj = row

        if row_obj is None:
            return None

        if isinstance(row_obj, PromptStudioRowAdapter):
            result = row_obj.to_dict()
        elif isinstance(row_obj, dict):
            result = dict(row_obj)
        else:
            # Fallback: attempt to build from sequence with cursor description
            if hasattr(cursor, 'description') and cursor.description:
                columns = [desc[0] if isinstance(desc, (list, tuple)) and desc else desc for desc in cursor.description]
                result = {col: row_obj[idx] for idx, col in enumerate(columns)}
            else:
                raise DatabaseError("Unable to convert row to dict; missing column metadata")

        for field in self._JSON_FIELDS:
            if field in result and isinstance(result[field], str):
                try:
                    result[field] = json.loads(result[field])
                except (TypeError, ValueError):
                    pass
            elif field in result and isinstance(result[field], (bytes, bytearray, memoryview)):
                try:
                    result[field] = json.loads(bytes(result[field]).decode('utf-8'))
                except (TypeError, ValueError):
                    result[field] = None

        for field in self._DATETIME_FIELDS:
            value = result.get(field)
            if isinstance(value, str):
                try:
                    result[field] = datetime.fromisoformat(value)
                except ValueError:
                    pass

        return result

    def _log_sync_event(self, entity: str, entity_uuid: str, operation: str, payload: Dict[str, Any]) -> None:
        if not entity or not entity_uuid or not operation:
            return

        try:
            with self.transaction() as conn:
                cursor = self._cursor_exec(
                    conn,
                    """
                    INSERT INTO sync_log (entity, entity_uuid, operation, client_id, version, payload, timestamp)
                    VALUES (?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        entity,
                        entity_uuid,
                        operation,
                        self.client_id,
                        json.dumps(payload, separators=(',', ':')) if payload else None,
                    ),
                )
        except Exception:
            # sync_log is optional across backends; swallow any logging failures
            logger.debug(
                "Prompt Studio sync_log not available; skipping event for %s/%s",
                entity,
                entity_uuid,
            )

    # --- Core API ---
    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        status: str = "draft",
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        project_uuid = str(uuid.uuid4())
        payload = (
            project_uuid,
            name,
            description,
            user_id or self.client_id,
            self.client_id,
            status,
            json.dumps(metadata) if metadata is not None else None,
        )

        insert_sql = """
            INSERT INTO prompt_studio_projects
            (uuid, name, description, user_id, client_id, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id, uuid, name, description, user_id, client_id, status,
                      deleted, deleted_at, created_at, updated_at, last_modified,
                      version, metadata
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
                    project = self._row_to_dict(row)
            self._log_sync_event(
                "prompt_studio_project",
                project_uuid,
                "create",
                {
                    "name": name,
                    "description": description,
                    "status": status,
                },
            )
            return project or {}
        except BackendDatabaseError as exc:
            message = str(exc)
            if 'duplicate' in message.lower() and 'prompt_studio_projects_name_user_id_deleted_key' in message:
                raise ConflictError(f"Project with name '{name}' already exists for this user") from exc
            raise DatabaseError(f"Failed to create prompt studio project: {exc}") from exc
        except Exception as exc:
            # Psycopg unique violations, etc.
            msg = str(exc).lower()
            if 'duplicate' in msg or 'unique constraint' in msg or 'unique violation' in msg:
                raise ConflictError(f"Project with name '{name}' already exists for this user") from exc
            raise

    def get_project(self, project_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        clauses = ["id = ?"]
        params: List[Any] = [project_id]
        if not include_deleted:
            clauses.append("deleted = FALSE")
        query = (
            "SELECT id, uuid, name, description, user_id, client_id, status, deleted, deleted_at, "
            "created_at, updated_at, last_modified, version, metadata "
            "FROM prompt_studio_projects WHERE " + " AND ".join(clauses)
        )
        try:
            cursor = self._execute(query, params)
            row = cursor.fetchone()
            return self._row_to_dict(row)
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch prompt studio project {project_id}: {exc}") from exc

    def list_projects(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        where_clauses: List[str] = []
        params: List[Any] = []

        if not include_deleted:
            where_clauses.append("deleted = FALSE")
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if search:
            where_clauses.append("(name ILIKE ? OR description ILIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        count_sql = f"SELECT COUNT(*) AS total FROM prompt_studio_projects{where_sql}"
        try:
            count_cursor = self._execute(count_sql, params)
            total = count_cursor.fetchone()
            total_count = int(total.get('total', 0)) if total else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed counting prompt studio projects: {exc}") from exc

        offset = (page - 1) * per_page
        list_sql = f"""
            SELECT p.*,
                   (SELECT COUNT(*) FROM prompt_studio_prompts WHERE project_id = p.id AND deleted = FALSE) AS prompt_count,
                   (SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = p.id AND deleted = FALSE) AS test_case_count
            FROM prompt_studio_projects p
            {where_sql}
            ORDER BY p.updated_at DESC
            LIMIT ?
            OFFSET ?
        """
        params_with_pagination = list(params) + [per_page, offset]

        try:
            cursor = self._execute(list_sql, params_with_pagination)
            rows = cursor.fetchall()
            projects = [self._row_to_dict(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed listing prompt studio projects: {exc}") from exc

        return {
            "projects": projects,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "total_pages": (total_count + per_page - 1) // per_page if per_page else 0,
            },
        }

    def create_prompt(
        self,
        project_id: int,
        name: str,
        *,
        signature_id: Optional[int] = None,
        version_number: int = 1,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        few_shot_examples: Optional[Any] = None,
        modules_config: Optional[Any] = None,
        parent_version_id: Optional[int] = None,
        change_description: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt_uuid = str(uuid.uuid4())
        payload = (
            prompt_uuid,
            project_id,
            signature_id,
            version_number,
            name,
            system_prompt,
            user_prompt,
            json.dumps(few_shot_examples) if few_shot_examples is not None else None,
            json.dumps(modules_config) if modules_config is not None else None,
            parent_version_id,
            change_description,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_prompts (
                uuid, project_id, signature_id, version_number, name, system_prompt,
                user_prompt, few_shot_examples, modules_config, parent_version_id,
                change_description, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id, uuid, project_id, signature_id, version_number, name,
                      system_prompt, user_prompt, few_shot_examples, modules_config,
                      parent_version_id, change_description, client_id, deleted,
                      deleted_at, created_at, updated_at
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
                    prompt = self._row_to_dict(row)
            self._log_sync_event(
                "prompt_studio_prompt",
                prompt_uuid,
                "create",
                {
                    "project_id": project_id,
                    "name": name,
                    "version_number": version_number,
                },
            )
            return prompt or {}
        except BackendDatabaseError as exc:
            message = str(exc).lower()
            if 'duplicate' in message and 'prompt_studio_prompts' in message and 'name' in message:
                raise ConflictError(
                    f"Prompt with name '{name}' already exists in project {project_id}"
                ) from exc
            raise DatabaseError(f"Failed to create prompt studio prompt: {exc}") from exc
        except Exception as exc:
            msg = str(exc).lower()
            if 'duplicate' in msg or 'unique constraint' in msg or 'unique violation' in msg:
                raise ConflictError(
                    f"Prompt with name '{name}' already exists in project {project_id}"
                ) from exc
            raise

    def update_project(self, project_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = {"name", "description", "status", "metadata"}
        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                continue
            column = field
            if field == "metadata" and value is not None:
                value = json.dumps(value)
            set_clauses.append(f"{column} = ?")
            params.append(value)

        if not set_clauses:
            project = self.get_project(project_id, include_deleted=True)
            if project is None:
                raise InputError(f"Project {project_id} not found or already deleted")
            return project

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(project_id)

        update_sql = (
            "UPDATE prompt_studio_projects SET "
            + ", ".join(set_clauses)
            + " WHERE id = ? AND deleted = FALSE RETURNING *"
        )

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, update_sql, params)
                    row = cursor.fetchone()
                    if not row:
                        raise InputError(f"Project {project_id} not found or already deleted")
            project = self._row_to_dict(row)
            if project:
                self._log_sync_event(
                    "prompt_studio_project",
                    project.get('uuid', ''),
                    "update",
                    {key: updates[key] for key in updates if key in allowed_fields},
                )
            return project or {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to update prompt studio project {project_id}: {exc}") from exc

    def delete_project(self, project_id: int, hard_delete: bool = False) -> bool:
        try:
            with self._write_lock:
                with self.transaction() as conn:
                    if hard_delete:
                        cursor = self._cursor_exec(
                            conn,
                            "DELETE FROM prompt_studio_projects WHERE id = ? RETURNING uuid",
                            (project_id,),
                        )
                    else:
                        cursor = self._cursor_exec(
                            conn,
                            """
                            UPDATE prompt_studio_projects
                            SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP
                            WHERE id = ? AND deleted = FALSE
                            RETURNING uuid
                            """,
                            (project_id,),
                        )
                    row = cursor.fetchone()
                    success = row is not None
            if success and row:
                self._log_sync_event(
                    "prompt_studio_project",
                    row.get('uuid', ''),
                    "delete" if hard_delete else "soft_delete",
                    {"hard": hard_delete},
                )
            return success
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to delete prompt studio project {project_id}: {exc}") from exc

    # --- Signature helpers -----------------------------------------------

    def create_signature(
        self,
        project_id: int,
        name: str,
        *,
        input_schema: Iterable[Any],
        output_schema: Iterable[Any],
        constraints: Optional[Any] = None,
        validation_rules: Optional[Any] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not name or not str(name).strip():
            raise InputError("Signature name cannot be empty")

        signature_uuid = str(uuid.uuid4())
        payload = (
            signature_uuid,
            project_id,
            str(name).strip(),
            json.dumps(list(input_schema) if input_schema is not None else []),
            json.dumps(list(output_schema) if output_schema is not None else []),
            json.dumps(constraints) if constraints is not None else None,
            json.dumps(validation_rules) if validation_rules is not None else None,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_signatures (
                uuid, project_id, name, input_schema, output_schema,
                constraints, validation_rules, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
                    signature = self._row_to_dict(row)

            self._log_sync_event(
                "prompt_studio_signature",
                signature_uuid,
                "create",
                {
                    "project_id": project_id,
                    "name": name,
                },
            )
            return signature or {}
        except BackendDatabaseError as exc:
            message = str(exc).lower()
            if "duplicate" in message and "prompt_studio_signatures" in message:
                raise ConflictError(
                    f"Signature with name '{name}' already exists for project {project_id}"
                ) from exc
            raise DatabaseError(f"Failed to create prompt studio signature: {exc}") from exc

    def get_signature(
        self,
        signature_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        clauses = ["id = ?"]
        params: List[Any] = [signature_id]
        if not include_deleted:
            clauses.append("deleted = FALSE")

        query = "SELECT * FROM prompt_studio_signatures WHERE " + " AND ".join(clauses) + " LIMIT 1"

        try:
            cursor = self._execute(query, params)
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row)
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch signature {signature_id}: {exc}") from exc

    def list_signatures(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        return_pagination: bool = False,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        conditions = ["project_id = ?"]
        params: List[Any] = [project_id]

        if not include_deleted:
            conditions.append("deleted = FALSE")

        if search:
            comparator = "ILIKE" if self.backend_type == BackendType.POSTGRESQL else "LIKE"
            conditions.append(f"name {comparator} ?")
            params.append(f"%{search}%")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_sql = f"SELECT COUNT(*) FROM prompt_studio_signatures{where_clause}"
        try:
            count_cursor = self._execute(count_sql, params)
            total_row = count_cursor.fetchone()
            total = int(total_row[0]) if total_row and total_row[0] is not None else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed counting signatures for project {project_id}: {exc}") from exc

        offset = max(page - 1, 0) * per_page
        list_sql = f"""
            SELECT *
            FROM prompt_studio_signatures
            {where_clause}
            ORDER BY updated_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params_with_pagination = params + [per_page, offset]

        try:
            cursor = self._execute(list_sql, params_with_pagination)
            rows = cursor.fetchall()
            signatures = [self._row_to_dict(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed listing signatures for project {project_id}: {exc}") from exc

        if return_pagination:
            return {
                "signatures": signatures,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        return signatures

    def update_signature(self, signature_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = {
            "name",
            "input_schema",
            "output_schema",
            "constraints",
            "validation_rules",
        }

        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                continue

            if field in {"input_schema", "output_schema", "constraints", "validation_rules"} and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        if not set_clauses:
            signature = self.get_signature(signature_id, include_deleted=True)
            if signature is None:
                raise InputError(f"Signature {signature_id} not found or already deleted")
            return signature

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(signature_id)

        update_sql = (
            "UPDATE prompt_studio_signatures SET "
            + ", ".join(set_clauses)
            + " WHERE id = ? AND deleted = FALSE RETURNING *"
        )

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, update_sql, params)
                    row = cursor.fetchone()
                    if not row:
                        raise InputError(f"Signature {signature_id} not found or already deleted")
                    signature = self._row_to_dict(row)
            self._log_sync_event(
                "prompt_studio_signature",
                signature.get("uuid", ""),
                "update",
                {key: updates[key] for key in updates if key in allowed_fields},
            )
            return signature or {}
        except BackendDatabaseError as exc:
            message = str(exc).lower()
            if "duplicate" in message and "prompt_studio_signatures" in message:
                raise ConflictError(
                    "Signature update conflicts with an existing record"
                ) from exc
            raise DatabaseError(f"Failed to update signature {signature_id}: {exc}") from exc

    def delete_signature(self, signature_id: int, hard_delete: bool = False) -> bool:
        try:
            with self._write_lock:
                with self.transaction() as conn:
                    if hard_delete:
                        cursor = self._cursor_exec(
                            conn,
                            "DELETE FROM prompt_studio_signatures WHERE id = ? RETURNING uuid",
                            (signature_id,),
                        )
                    else:
                        cursor = self._cursor_exec(
                            conn,
                            """
                            UPDATE prompt_studio_signatures
                            SET deleted = TRUE, deleted_at = CURRENT_TIMESTAMP
                            WHERE id = ? AND deleted = FALSE
                            RETURNING uuid
                            """,
                            (signature_id,),
                        )
                    row = cursor.fetchone()
                    success = row is not None
            if success and row:
                self._log_sync_event(
                    "prompt_studio_signature",
                    row.get("uuid", ""),
                    "delete" if hard_delete else "soft_delete",
                    {"hard": hard_delete},
                )
            return success
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to delete signature {signature_id}: {exc}") from exc

    # --- Test run helpers ------------------------------------------------

    def create_test_run(
        self,
        *,
        project_id: int,
        prompt_id: int,
        test_case_id: int,
        model_name: str,
        model_params: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        expected_outputs: Optional[Dict[str, Any]] = None,
        scores: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None,
        error_message: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        run_uuid = str(uuid.uuid4())
        payload = (
            run_uuid,
            project_id,
            prompt_id,
            test_case_id,
            model_name,
            json.dumps(model_params) if model_params is not None else None,
            json.dumps(inputs) if inputs is not None else None,
            json.dumps(outputs) if outputs is not None else None,
            json.dumps(expected_outputs) if expected_outputs is not None else None,
            json.dumps(scores) if scores is not None else None,
            execution_time_ms,
            tokens_used,
            cost_estimate,
            error_message,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_test_runs (
                uuid, project_id, prompt_id, test_case_id, model_name,
                model_params, inputs, outputs, expected_outputs, scores,
                execution_time_ms, tokens_used, cost_estimate, error_message,
                client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to create prompt studio test run: {exc}") from exc

    def get_test_cases_by_ids(
        self,
        test_case_ids: Iterable[int],
        *,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        identifiers = list(dict.fromkeys(test_case_ids))
        if not identifiers:
            return []

        placeholders = ",".join(["?"] * len(identifiers))
        where_clause = f"id IN ({placeholders})"
        if not include_deleted:
            where_clause += " AND deleted = FALSE"

        query = f"SELECT * FROM prompt_studio_test_cases WHERE {where_clause}"

        try:
            cursor = self._execute(query, identifiers)
            rows = cursor.fetchall()
            return [self._format_test_case(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed fetching test cases: {exc}") from exc

    # --- Evaluation helpers ---------------------------------------------

    def create_evaluation(
        self,
        *,
        prompt_id: int,
        project_id: int,
        model_configs: Optional[Dict[str, Any]] = None,
        status: str = "running",
        test_case_ids: Optional[Iterable[int]] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        evaluation_uuid = str(uuid.uuid4())
        payload = (
            evaluation_uuid,
            prompt_id,
            project_id,
            json.dumps(model_configs) if model_configs is not None else None,
            status,
            json.dumps(list(test_case_ids) if test_case_ids is not None else []),
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_evaluations (
                uuid, prompt_id, project_id, model_configs, status,
                test_case_ids, started_at, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            RETURNING *
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to create prompt studio evaluation: {exc}") from exc

    def update_evaluation(self, evaluation_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        if not updates:
            evaluation = self.get_evaluation(evaluation_id)
            if evaluation is None:
                raise InputError(f"Evaluation {evaluation_id} not found")
            return evaluation

        json_fields = {"model_configs", "test_case_ids", "test_run_ids", "aggregate_metrics"}
        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field in json_fields and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        set_clause_sql = ", ".join(set_clauses)
        params.append(evaluation_id)

        update_sql = (
            "UPDATE prompt_studio_evaluations SET "
            + set_clause_sql
            + " WHERE id = ? RETURNING *"
        )

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, update_sql, params)
                    row = cursor.fetchone()
                    if not row:
                        raise InputError(f"Evaluation {evaluation_id} not found")
            return self._row_to_dict(cursor, row) if row else {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to update evaluation {evaluation_id}: {exc}") from exc

    def get_evaluation(self, evaluation_id: int) -> Optional[Dict[str, Any]]:
        try:
            cursor = self._execute(
                "SELECT * FROM prompt_studio_evaluations WHERE id = ?",
                [evaluation_id],
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch evaluation {evaluation_id}: {exc}") from exc

    def list_evaluations(
        self,
        *,
        project_id: Optional[int] = None,
        prompt_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        conditions: List[str] = []
        params: List[Any] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if prompt_id is not None:
            conditions.append("prompt_id = ?")
            params.append(prompt_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_sql = f"SELECT COUNT(*) FROM prompt_studio_evaluations{where_clause}"
        try:
            count_cursor = self._execute(count_sql, params)
            total_row = count_cursor.fetchone()
            total = int(total_row[0]) if total_row and total_row[0] is not None else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed counting evaluations: {exc}") from exc

        offset = max(page - 1, 0) * per_page
        list_sql = f"""
            SELECT *
            FROM prompt_studio_evaluations
            {where_clause}
            ORDER BY started_at DESC NULLS LAST, id DESC
            LIMIT ? OFFSET ?
        """
        params_with_page = list(params) + [per_page, offset]

        try:
            cursor = self._execute(list_sql, params_with_page)
            rows = cursor.fetchall()
            evaluations = [self._row_to_dict(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed listing evaluations: {exc}") from exc

        return {
            "evaluations": evaluations,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page if per_page else 0,
            },
        }

    # --- Optimization helpers -------------------------------------------

    def create_optimization(
        self,
        *,
        project_id: int,
        name: Optional[str],
        initial_prompt_id: Optional[int],
        optimizer_type: str,
        optimization_config: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        bootstrap_samples: Optional[int] = None,
        status: str = "pending",
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        optimization_uuid = str(uuid.uuid4())
        payload = (
            optimization_uuid,
            project_id,
            name,
            initial_prompt_id,
            None,  # optimized_prompt_id
            optimizer_type,
            json.dumps(optimization_config) if optimization_config is not None else None,
            None,
            None,
            None,
            0,
            max_iterations,
            bootstrap_samples,
            status,
            None,
            None,
            None,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_optimizations (
                uuid, project_id, name, initial_prompt_id, optimized_prompt_id,
                optimizer_type, optimization_config, initial_metrics, final_metrics,
                improvement_percentage, iterations_completed, max_iterations,
                bootstrap_samples, status, error_message, total_tokens, total_cost,
                client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
            optimization = self._row_to_dict(cursor, row) if row else {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to create optimization: {exc}") from exc

        self._log_sync_event(
            "prompt_studio_optimization",
            optimization_uuid,
            "create",
            {
                "project_id": project_id,
                "optimizer_type": optimizer_type,
                "status": status,
            },
        )
        return optimization

    def get_optimization(
        self,
        optimization_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        clauses = ["id = ?"]
        params: List[Any] = [optimization_id]
        if not include_deleted:
            clauses.append("deleted = FALSE")

        query = "SELECT * FROM prompt_studio_optimizations WHERE " + " AND ".join(clauses) + " LIMIT 1"

        try:
            cursor = self._execute(query, params)
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch optimization {optimization_id}: {exc}") from exc

    def list_optimizations(
        self,
        *,
        project_id: Optional[int] = None,
        status: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        conditions: List[str] = []
        params: List[Any] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if not include_deleted:
            conditions.append("deleted = FALSE")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_sql = f"SELECT COUNT(*) FROM prompt_studio_optimizations{where_clause}"
        try:
            count_cursor = self._execute(count_sql, params)
            total_row = count_cursor.fetchone()
            total = int(total_row[0]) if total_row and total_row[0] is not None else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed counting optimizations: {exc}") from exc

        offset = max(page - 1, 0) * per_page
        list_sql = f"""
            SELECT *
            FROM prompt_studio_optimizations
            {where_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params_with_page = list(params) + [per_page, offset]

        try:
            cursor = self._execute(list_sql, params_with_page)
            rows = cursor.fetchall()
            optimizations = [self._row_to_dict(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed listing optimizations: {exc}") from exc

        return {
            "optimizations": optimizations,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page if per_page else 0,
            },
        }

    def update_optimization(
        self,
        optimization_id: int,
        updates: Dict[str, Any],
        *,
        set_started_at: bool = False,
        set_completed_at: bool = False,
    ) -> Dict[str, Any]:
        json_fields = {"optimization_config", "initial_metrics", "final_metrics"}
        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field in json_fields and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        if set_started_at:
            set_clauses.append("started_at = CURRENT_TIMESTAMP")
        if set_completed_at:
            set_clauses.append("completed_at = CURRENT_TIMESTAMP")

        if not set_clauses:
            optimization = self.get_optimization(optimization_id, include_deleted=True)
            if optimization is None:
                raise InputError(f"Optimization {optimization_id} not found")
            return optimization

        params.append(optimization_id)
        update_sql = (
            "UPDATE prompt_studio_optimizations SET "
            + ", ".join(set_clauses)
            + " WHERE id = ? RETURNING *"
        )

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, update_sql, params)
                    row = cursor.fetchone()
                    if not row:
                        raise InputError(f"Optimization {optimization_id} not found")
            optimization = self._row_to_dict(cursor, row) if row else {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to update optimization {optimization_id}: {exc}") from exc

        log_payload = {}
        for key, value in updates.items():
            if isinstance(value, (dict, list)):
                try:
                    log_payload[key] = json.loads(json.dumps(value, default=str))
                except TypeError:
                    log_payload[key] = str(value)
            else:
                log_payload[key] = value

        if set_started_at:
            log_payload["started_at"] = "CURRENT_TIMESTAMP"
        if set_completed_at:
            log_payload["completed_at"] = "CURRENT_TIMESTAMP"

        self._log_sync_event(
            "prompt_studio_optimization",
            optimization.get("uuid", ""),
            "update",
            log_payload,
        )
        return optimization

    def set_optimization_status(
        self,
        optimization_id: int,
        status: str,
        *,
        error_message: Optional[str] = None,
        mark_started: bool = False,
        mark_completed: bool = False,
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {"status": status}
        if error_message is not None:
            updates["error_message"] = error_message
        return self.update_optimization(
            optimization_id,
            updates,
            set_started_at=mark_started,
            set_completed_at=mark_completed,
        )

    def complete_optimization(
        self,
        optimization_id: int,
        *,
        optimized_prompt_id: Optional[int] = None,
        iterations_completed: Optional[int] = None,
        initial_metrics: Optional[Dict[str, Any]] = None,
        final_metrics: Optional[Dict[str, Any]] = None,
        improvement_percentage: Optional[float] = None,
        total_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {
            "status": "completed",
            "optimized_prompt_id": optimized_prompt_id,
            "iterations_completed": iterations_completed,
            "initial_metrics": initial_metrics,
            "final_metrics": final_metrics,
            "improvement_percentage": improvement_percentage,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }
        # Remove keys with None to avoid overriding with NULL unnecessarily
        updates = {k: v for k, v in updates.items() if v is not None}
        return self.update_optimization(
            optimization_id,
            updates,
            set_completed_at=True,
        )

    def record_optimization_iteration(
        self,
        optimization_id: int,
        *,
        iteration_number: int,
        prompt_variant: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = (
            str(uuid.uuid4()),
            optimization_id,
            iteration_number,
            json.dumps(prompt_variant) if prompt_variant is not None else None,
            json.dumps(metrics) if metrics is not None else None,
            tokens_used,
            cost,
            note,
        )

        insert_sql = """
            INSERT INTO prompt_studio_optimization_iterations (
                uuid, optimization_id, iteration_number, prompt_variant, metrics,
                tokens_used, cost, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
        """

        try:
            with self.transaction() as conn:
                cursor = self._cursor_exec(conn, insert_sql, payload)
                row = cursor.fetchone()
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to record optimization iteration: {exc}") from exc

        record = self._row_to_dict(cursor, row) if row else {}
        self._log_sync_event(
            "prompt_studio_optimization_iteration",
            record.get("uuid", ""),
            "create",
            {
                "optimization_id": optimization_id,
                "iteration_number": iteration_number,
            },
        )
        return record

    def list_optimization_iterations(
        self,
        optimization_id: int,
        *,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        """List persisted iterations for an optimization (SQLite backend)."""
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Count total
            cursor.execute(
                "SELECT COUNT(*) FROM prompt_studio_optimization_iterations WHERE optimization_id = ?",
                (optimization_id,),
            )
            row = cursor.fetchone()
            total = int(row[0]) if row and row[0] is not None else 0

            # Page slice
            offset = max(page - 1, 0) * per_page
            cursor.execute(
                """
                SELECT *
                FROM prompt_studio_optimization_iterations
                WHERE optimization_id = ?
                ORDER BY iteration_number ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                (optimization_id, per_page, offset),
            )
            rows = cursor.fetchall()
            iterations = [self._row_to_dict(cursor, r) for r in rows if r]

            return {
                "iterations": iterations,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to list optimization iterations: {exc}") from exc

    def list_optimization_iterations(
        self,
        optimization_id: int,
        *,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        count_sql = "SELECT COUNT(*) FROM prompt_studio_optimization_iterations WHERE optimization_id = ?"

        try:
            count_cursor = self._execute(count_sql, [optimization_id])
            total_row = count_cursor.fetchone()
            total = int(total_row[0]) if total_row and total_row[0] is not None else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed counting optimization iterations: {exc}") from exc

        offset = max(page - 1, 0) * per_page
        list_sql = """
            SELECT *
            FROM prompt_studio_optimization_iterations
            WHERE optimization_id = ?
            ORDER BY iteration_number ASC, id ASC
            LIMIT ? OFFSET ?
        """

        try:
            cursor = self._execute(list_sql, [optimization_id, per_page, offset])
            rows = cursor.fetchall()
            iterations = [self._row_to_dict(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed listing optimization iterations: {exc}") from exc

        return {
            "iterations": iterations,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page if per_page else 0,
            },
        }

    # --- Prompt helpers ---

    def get_prompt(self, prompt_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        clauses = ["id = ?"]
        params: List[Any] = [prompt_id]
        if not include_deleted:
            clauses.append("deleted = FALSE")

        query = (
            "SELECT * FROM prompt_studio_prompts WHERE " + " AND ".join(clauses) + " LIMIT 1"
        )

        try:
            cursor = self._execute(query, params)
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row)
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch prompt {prompt_id}: {exc}") from exc

    def list_prompts(
        self,
        project_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        base_conditions = ["project_id = ?"]
        params: List[Any] = [project_id]
        if not include_deleted:
            base_conditions.append("deleted = FALSE")

        where_clause = " WHERE " + " AND ".join(base_conditions)

        count_sql = f"SELECT COUNT(*) FROM prompt_studio_prompts{where_clause}"
        try:
            count_cursor = self._execute(count_sql, params)
            total_row = count_cursor.fetchone()
            total = int(total_row[0]) if total_row and total_row[0] is not None else 0

            offset = (page - 1) * per_page
            list_sql = f"""
                SELECT *
                FROM prompt_studio_prompts
                {where_clause}
                ORDER BY updated_at DESC, version_number DESC
                LIMIT ? OFFSET ?
            """
            list_params = list(params) + [per_page, offset]
            list_cursor = self._execute(list_sql, list_params)
            rows = list_cursor.fetchall()
            prompts = [self._row_to_dict(list_cursor, row) for row in rows if row]

            return {
                "prompts": prompts,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        except BackendDatabaseError as exc:
            raise DatabaseError(
                f"Failed to list prompts for project {project_id}: {exc}"
            ) from exc

    def list_prompt_versions(
        self,
        project_id: int,
        prompt_name: str,
        *,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        conditions = ["project_id = ?", "name = ?"]
        params: List[Any] = [project_id, prompt_name]
        if not include_deleted:
            conditions.append("deleted = FALSE")

        query = """
            SELECT id, uuid, version_number, name, change_description,
                   created_at, parent_version_id
            FROM prompt_studio_prompts
            WHERE {where}
            ORDER BY version_number DESC
        """.format(where=" AND ".join(conditions))

        try:
            cursor = self._execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(
                f"Failed to list versions for prompt '{prompt_name}' in project {project_id}: {exc}"
            ) from exc

    def ensure_prompt_stub(
        self,
        *,
        prompt_id: int,
        project_id: int,
        name: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> None:
        """Ensure a placeholder prompt exists for the given identifiers."""

        if not prompt_id or not project_id:
            return

        try:
            cursor = self._execute(
                "SELECT 1 FROM prompt_studio_prompts WHERE id = ?",
                [prompt_id],
            )
            if cursor.fetchone() is not None:
                return
        except BackendDatabaseError as exc:
            raise DatabaseError(
                f"Failed to verify prompt {prompt_id} existence: {exc}"
            ) from exc

        stub_name = name or f"Auto-Created Prompt {prompt_id}"
        params = (
            prompt_id,
            project_id,
            stub_name,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT OR IGNORE INTO prompt_studio_prompts (
                id, uuid, project_id, version_number, name, client_id
            ) VALUES (?, lower(hex(randomblob(16))), ?, 1, ?, ?)
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    _ = self._cursor_exec(conn, insert_sql, params)
        except BackendDatabaseError as exc:
            raise DatabaseError(
                f"Failed to create placeholder prompt {prompt_id}: {exc}"
            ) from exc

    # --- Job queue helpers ---

    def create_job(
        self,
        job_type: str,
        entity_id: int,
        payload: Optional[Any],
        *,
        project_id: Optional[int] = None,
        priority: int = 5,
        status: str = "queued",
        max_retries: int = 3,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        job_uuid = str(uuid.uuid4())
        payload_json = json.dumps(payload) if payload is not None else json.dumps({})

        with self._write_lock:
            with self.transaction() as conn:
                cursor = self._cursor_exec(
                    conn,
                    """
                    INSERT INTO prompt_studio_job_queue (
                        uuid, job_type, entity_id, project_id, priority, status,
                        payload, max_retries, client_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING *
                    """,
                    (
                        job_uuid,
                        job_type,
                        entity_id,
                        project_id,
                        priority,
                        status,
                        payload_json,
                        max_retries,
                        client_id or self.client_id,
                    ),
                )
                row = cursor.fetchone()
                if not row:
                    raise DatabaseError("Failed to create prompt studio job queue record")
                job = self._row_to_dict(cursor, row)
        return job or {}

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        try:
            cursor = self._execute(
                "SELECT * FROM prompt_studio_job_queue WHERE id = ? LIMIT 1",
                (job_id,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch job {job_id}: {exc}") from exc

    def get_job_by_uuid(self, job_uuid: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = self._execute(
                "SELECT * FROM prompt_studio_job_queue WHERE uuid = ? LIMIT 1",
                (job_uuid,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch job {job_uuid}: {exc}") from exc

    def list_jobs(
        self,
        *,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if job_type:
            clauses.append("job_type = ?")
            params.append(job_type)

        where_clause = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"""
            SELECT *
            FROM prompt_studio_job_queue
            {where_clause}
            ORDER BY priority DESC, created_at ASC
            LIMIT ?
        """
        params_with_limit = list(params) + [limit]

        try:
            cursor = self._execute(query, params_with_limit)
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to list prompt studio jobs: {exc}") from exc

    def update_job_status(
        self,
        job_id: int,
        status: str,
        *,
        error_message: Optional[str] = None,
        result: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        updates = ["status = ?"]
        params: List[Any] = [status]

        if status == "processing":
            updates.append("started_at = CURRENT_TIMESTAMP")
            # Extend lease window when explicitly setting processing
            updates.append("leased_until = NOW() + INTERVAL '60 seconds'")
        elif status in {"completed", "failed", "cancelled"}:
            updates.append("completed_at = CURRENT_TIMESTAMP")
            # Clear lease on terminal states
            updates.append("leased_until = NULL")
            updates.append("lease_owner = NULL")

        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)

        if result is not None:
            updates.append("result = ?")
            params.append(json.dumps(result))

        params.append(job_id)

        query = f"""
            UPDATE prompt_studio_job_queue
            SET {', '.join(updates)}
            WHERE id = ?
            RETURNING *
        """

        try:
            with self.transaction() as conn:
                cursor = self._cursor_exec(conn, query, params)
                row = cursor.fetchone()
                record = self._row_to_dict(cursor, row) if row else None
                # Release advisory lock on terminal states
                if record and status in {"completed", "failed", "cancelled"}:
                    try:
                        self._execute("SELECT pg_advisory_unlock(?)", (job_id,))
                    except BackendDatabaseError:
                        pass
                return record
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to update job {job_id}: {exc}") from exc

    def acquire_next_job(self, worker_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._write_lock:
            with self.transaction() as conn:
                cursor = conn.cursor()
                owner_value: Optional[str] = None
                if worker_id:
                    try:
                        owner_value = str(worker_id).strip()[:128]
                        if not owner_value:
                            owner_value = None
                    except Exception:
                        owner_value = None
                if self.backend_type == BackendType.POSTGRESQL:
                    import os as _os
                    try:
                        _lease_secs = max(5, min(3600, int(_os.getenv("TLDW_PS_JOB_LEASE_SECONDS", "60"))))
                    except Exception:
                        _lease_secs = 60
                    # Acquire using advisory lock as a gate to avoid double-processing across processes
                    # Metrics: advisory lock attempt
                    try:
                        from tldw_Server_API.app.core.Prompt_Management.prompt_studio.monitoring import prompt_studio_metrics as _psm
                        _psm.metrics_manager.increment("prompt_studio.pg_advisory.lock_attempts_total")
                    except Exception:
                        pass
                    cursor.execute(
                        f"""
                        WITH candidate AS (
                            SELECT id,
                                   (status = 'processing' AND (leased_until IS NULL OR leased_until < NOW())) AS was_reclaim
                            FROM prompt_studio_job_queue
                            WHERE (status = 'queued'
                                   OR (status = 'processing' AND (leased_until IS NULL OR leased_until < NOW())))
                            ORDER BY priority DESC, created_at ASC
                            LIMIT 10
                        ), locked AS (
                            SELECT id, was_reclaim
                            FROM candidate
                            WHERE pg_try_advisory_lock(id)
                            LIMIT 1
                        )
                        UPDATE prompt_studio_job_queue AS q
                        SET status = 'processing',
                            started_at = CURRENT_TIMESTAMP,
                            leased_until = NOW() + INTERVAL '{_lease_secs} seconds',
                            lease_owner = COALESCE(%s, lease_owner)
                        FROM locked
                        WHERE q.id = locked.id
                        RETURNING q.*, locked.was_reclaim
                        """,
                        (owner_value,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    # Metrics: locks acquired
                    try:
                        _psm.metrics_manager.increment("prompt_studio.pg_advisory.locks_acquired_total")
                    except Exception:
                        pass
                    # Release advisory lock immediately; we rely on leased_until+heartbeat for visibility timeout
                    try:
                        job_id_val = None
                        try:
                            job_id_val = row["id"]
                        except Exception:
                            job_id_val = row[0]
                        cursor.execute("SELECT pg_advisory_unlock(%s)", (job_id_val,))
                        try:
                            _psm.metrics_manager.increment("prompt_studio.pg_advisory.unlocks_total")
                        except Exception:
                            pass
                    except Exception:
                        pass
                    record = self._row_to_dict(cursor, row)
                    # Record queue latency for Postgres
                    try:
                        from datetime import datetime
                        created = record.get("created_at")
                        started = record.get("started_at")
                        def _parse(v):
                            if v is None:
                                return None
                            if isinstance(v, datetime):
                                return v
                            try:
                                return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                            except Exception:
                                return None
                        cdt = _parse(created)
                        sdt = _parse(started)
                        if cdt and sdt:
                            qlat = max(0.0, (sdt - cdt).total_seconds())
                            try:
                                _psm.metrics_manager.observe(
                                    "jobs.queue_latency_seconds",
                                    qlat,
                                    labels={"job_type": str(record.get("job_type", ""))},
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Increment reclaims if applicable
                    try:
                        was_reclaim = False
                        try:
                            was_reclaim = bool(row["was_reclaim"])  # dict_row in pg
                        except Exception:
                            # positional
                            was_reclaim = bool(row[-1])
                        if was_reclaim:
                            _psm.metrics_manager.increment("jobs.reclaims_total", labels={"job_type": str(record.get("job_type", ""))})
                    except Exception:
                        pass
                    return record
                else:
                    cursor.execute(
                        """
                        SELECT id
                        FROM prompt_studio_job_queue
                        WHERE (status = 'queued' OR (status = 'processing' AND (leased_until IS NULL OR leased_until < CURRENT_TIMESTAMP)))
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                        """,
                        (owner_value,),
                    )
                    job_row = cursor.fetchone()
                    if not job_row:
                        return None
                    job_id = job_row[0]
                    import os as _os2
                    try:
                        _lease_secs2 = max(5, min(3600, int(_os2.getenv("TLDW_PS_JOB_LEASE_SECONDS", "60"))))
                    except Exception:
                        _lease_secs2 = 60
                    cursor.execute(
                        f"""
                        UPDATE prompt_studio_job_queue
                        SET status = 'processing',
                            started_at = CURRENT_TIMESTAMP,
                            leased_until = DATETIME('now', '+{_lease_secs2} seconds'),
                            lease_owner = COALESCE(?, lease_owner)
                        WHERE id = ?
                          AND (
                              status = 'queued'
                              OR (status = 'processing' AND (leased_until IS NULL OR leased_until < CURRENT_TIMESTAMP))
                          )
                        RETURNING *
                        """,
                        (owner_value, job_id),
                    )

                row = cursor.fetchone()
                if not row:
                    return None
                job = self._row_to_dict(cursor, row)
                # Record queue latency for SQLite
                try:
                    from datetime import datetime
                    created = job.get("created_at")
                    started = job.get("started_at")
                    def _parse(v):
                        if v is None:
                            return None
                        if isinstance(v, datetime):
                            return v
                        try:
                            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                        except Exception:
                            return None
                    cdt = _parse(created)
                    sdt = _parse(started)
                    if cdt and sdt:
                        qlat = max(0.0, (sdt - cdt).total_seconds())
                        try:
                            from tldw_Server_API.app.core.Prompt_Management.prompt_studio.monitoring import prompt_studio_metrics as _psm2
                            _psm2.metrics_manager.observe(
                                "jobs.queue_latency_seconds",
                                qlat,
                                labels={"job_type": str(job.get("job_type", ""))},
                            )
                        except Exception:
                            pass
                except Exception:
                    pass
        return job

    def retry_job_record(self, job_id: int) -> bool:
        with self._write_lock:
            with self.transaction() as conn:
                cursor = self._cursor_exec(
                    conn,
                    """
                    UPDATE prompt_studio_job_queue
                    SET status = 'queued',
                        retry_count = retry_count + 1,
                        error_message = NULL,
                        started_at = NULL,
                        completed_at = NULL,
                        leased_until = NULL,
                        lease_owner = NULL
                    WHERE id = ?
                    RETURNING retry_count, max_retries
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                success = row is not None
                if success:
                    try:
                        self._execute("SELECT pg_advisory_unlock(?)", (job_id,))
                    except BackendDatabaseError:
                        pass
                return success

    def get_job_stats(self) -> Dict[str, Any]:
        stats: Dict[str, Any] = {}
        try:
            cursor = self._execute(
                """
                SELECT status, COUNT(*) AS count
                FROM prompt_studio_job_queue
                GROUP BY status
                """,
            )
            stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = self._execute(
                """
                SELECT job_type, COUNT(*) AS count
                FROM prompt_studio_job_queue
                GROUP BY job_type
                """,
            )
            stats["by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = self._execute(
                """
                SELECT AVG(
                    CAST((EXTRACT(EPOCH FROM (completed_at - started_at))) AS BIGINT)
                )
                FROM prompt_studio_job_queue
                WHERE status = 'completed'
                  AND started_at IS NOT NULL
                  AND completed_at IS NOT NULL
                """,
            )
            avg_time_row = cursor.fetchone()
            stats["avg_processing_time_seconds"] = (
                avg_time_row[0] if avg_time_row and avg_time_row[0] is not None else 0
            )

            cursor = self._execute(
                """
                SELECT
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(CASE WHEN status IN ('completed', 'failed') THEN 1 END), 0)
                FROM prompt_studio_job_queue
                WHERE status IN ('completed', 'failed')
                """,
            )
            success_row = cursor.fetchone()
            stats["success_rate"] = (
                float(success_row[0]) if success_row and success_row[0] is not None else 0.0
            )

            stats.setdefault("by_status", {})
            stats["queue_depth"] = stats["by_status"].get("queued", 0)
            stats["processing"] = stats["by_status"].get("processing", 0)
            return stats
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to compute job statistics: {exc}") from exc

    def count_jobs(
        self,
        *,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> int:
        """Return count of jobs filtered by optional status and job_type."""
        try:
            with self.transaction() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) AS c FROM prompt_studio_job_queue WHERE 1=1"
                params: List[Any] = []
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if job_type:
                    query += " AND job_type = ?"
                    params.append(job_type)
                cursor.execute(query, params)
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to count jobs: {exc}") from exc

    def get_lease_stats(self, warn_seconds: int = 30) -> Dict[str, int]:
        """Return basic lease health: active, expiring soon, and stale processing counts."""
        try:
            warn_seconds = max(1, min(3600, int(warn_seconds)))
        except Exception:
            warn_seconds = 30
        try:
            result: Dict[str, int] = {}
            # Active leases: processing with future leased_until
            cursor = self._execute(
                """
                SELECT COUNT(*) FROM prompt_studio_job_queue
                WHERE status = 'processing' AND leased_until IS NOT NULL AND leased_until > NOW()
                """,
            )
            result["active"] = int(cursor.fetchone()[0])

            # Expiring soon: processing with lease expiring within warn_seconds
            cursor = self._execute(
                f"""
                SELECT COUNT(*) FROM prompt_studio_job_queue
                WHERE status = 'processing'
                  AND leased_until IS NOT NULL
                  AND leased_until > NOW()
                  AND leased_until <= NOW() + INTERVAL '{warn_seconds} seconds'
                """,
            )
            result["expiring_soon"] = int(cursor.fetchone()[0])

            # Stale processing: processing with missing/expired lease
            cursor = self._execute(
                """
                SELECT COUNT(*) FROM prompt_studio_job_queue
                WHERE status = 'processing'
                  AND (leased_until IS NULL OR leased_until < NOW())
                """,
            )
            result["stale_processing"] = int(cursor.fetchone()[0])
            return result
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to compute lease stats: {exc}") from exc

    def cleanup_jobs(self, older_than_days: int = 30) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        try:
            cursor = self._execute(
                """
                DELETE FROM prompt_studio_job_queue
                WHERE status IN ('completed', 'failed', 'cancelled')
                  AND completed_at IS NOT NULL
                  AND completed_at < ?
                """,
                (cutoff.isoformat(),),
            )
            return cursor.rowcount
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed cleaning up old jobs: {exc}") from exc

    def get_latest_job_for_entity(self, job_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
        query = """
            SELECT *
            FROM prompt_studio_job_queue
            WHERE job_type = ? AND entity_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """
        try:
            cursor = self._execute(query, (job_type, entity_id))
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except BackendDatabaseError as exc:
            raise DatabaseError(
                f"Failed fetching latest job for entity {entity_id}: {exc}"
            ) from exc

    def list_jobs_for_entity(
        self,
        job_type: str,
        entity_id: int,
        *,
        limit: int = 50,
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        order_clause = "ASC" if ascending else "DESC"
        query = f"""
            SELECT *
            FROM prompt_studio_job_queue
            WHERE job_type = ? AND entity_id = ?
            ORDER BY created_at {order_clause}, id {order_clause}
            LIMIT ?
        """
        try:
            cursor = self._execute(query, (job_type, entity_id, limit))
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(
                f"Failed listing jobs for entity {entity_id}: {exc}"
            ) from exc

    def get_prompt_with_project(
        self,
        prompt_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        clauses = ["p.id = ?"]
        if not include_deleted:
            clauses.append("p.deleted = FALSE")
        query = f"""
            SELECT p.*, proj.user_id AS project_user_id
            FROM prompt_studio_prompts p
            JOIN prompt_studio_projects proj ON p.project_id = proj.id
            WHERE {' AND '.join(clauses)}
            LIMIT 1
        """
        try:
            cursor = self._execute(query, [prompt_id])
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch prompt {prompt_id}: {exc}") from exc

    def create_prompt_version(
        self,
        prompt_id: int,
        *,
        change_description: str,
        name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        few_shot_examples: Optional[Any] = None,
        modules_config: Optional[Any] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not change_description:
            raise InputError("change_description is required")

        with self._write_lock:
            with self.transaction() as conn:
                cursor = self._cursor_exec(
                    conn,
                    """
                    SELECT *
                    FROM prompt_studio_prompts
                    WHERE id = ? AND deleted = FALSE
                    LIMIT 1
                    """,
                    (prompt_id,),
                )
                current_row = cursor.fetchone()
                if not current_row:
                    raise InputError(f"Prompt {prompt_id} not found or already deleted")
                current_prompt = self._row_to_dict(cursor, current_row) or {}

                new_uuid = str(uuid.uuid4())
                new_version = int(current_prompt.get("version_number", 0)) + 1

                next_name = name if name is not None else current_prompt.get("name")
                next_system = (
                    system_prompt
                    if system_prompt is not None
                    else current_prompt.get("system_prompt")
                )
                next_user = (
                    user_prompt
                    if user_prompt is not None
                    else current_prompt.get("user_prompt")
                )
                next_examples = (
                    few_shot_examples
                    if few_shot_examples is not None
                    else current_prompt.get("few_shot_examples")
                )
                next_modules = (
                    modules_config
                    if modules_config is not None
                    else current_prompt.get("modules_config")
                )

                insert_sql = """
                    INSERT INTO prompt_studio_prompts (
                        uuid,
                        project_id,
                        signature_id,
                        version_number,
                        name,
                        system_prompt,
                        user_prompt,
                        few_shot_examples,
                        modules_config,
                        parent_version_id,
                        change_description,
                        client_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING *
                """

                payload = (
                    new_uuid,
                    current_prompt.get("project_id"),
                    current_prompt.get("signature_id"),
                    new_version,
                    next_name,
                    next_system,
                    next_user,
                    json.dumps(next_examples) if next_examples is not None else None,
                    json.dumps(next_modules) if next_modules is not None else None,
                    prompt_id,
                    change_description,
                    client_id or current_prompt.get("client_id") or self.client_id,
                )

                cursor.execute(insert_sql, payload)
                new_row = cursor.fetchone()
                prompt = self._row_to_dict(cursor, new_row)

        self._log_sync_event(
            "prompt_studio_prompt",
            prompt.get("uuid", ""),
            "version_create",
            {
                "prompt_id": prompt_id,
                "new_version": prompt.get("version_number"),
                "change_description": change_description,
            },
        )
        return prompt

    def revert_prompt_to_version(
        self,
        prompt_id: int,
        target_version: int,
        *,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if target_version < 1:
            raise InputError("target_version must be >= 1")

        with self._write_lock:
            with self.transaction() as conn:
                cursor = self._cursor_exec(
                    conn,
                    """
                    SELECT *
                    FROM prompt_studio_prompts
                    WHERE id = ? AND deleted = FALSE
                    LIMIT 1
                    """,
                    (prompt_id,),
                )
                current_row = cursor.fetchone()
                if not current_row:
                    raise InputError(f"Prompt {prompt_id} not found or already deleted")
                current_prompt = self._row_to_dict(cursor, current_row) or {}

                cursor = self._cursor_exec(
                    conn,
                    """
                    SELECT *
                    FROM prompt_studio_prompts
                    WHERE project_id = ? AND name = ? AND version_number = ? AND deleted = FALSE
                    LIMIT 1
                    """,
                    (
                        current_prompt.get("project_id"),
                        current_prompt.get("name"),
                        target_version,
                    ),
                )
                target_row = cursor.fetchone()
                if not target_row:
                    raise InputError(
                        f"Version {target_version} not found for prompt {current_prompt.get('name')}"
                    )
                target_prompt = self._row_to_dict(cursor, target_row) or {}

                cursor = self._cursor_exec(
                    conn,
                    """
                    SELECT COALESCE(MAX(version_number), 0)
                    FROM prompt_studio_prompts
                    WHERE project_id = ? AND name = ?
                    """,
                    (current_prompt.get("project_id"), current_prompt.get("name")),
                )
                max_version_row = cursor.fetchone()
                next_version = int(max_version_row[0]) + 1 if max_version_row else 1

                new_uuid = str(uuid.uuid4())
                insert_sql = """
                    INSERT INTO prompt_studio_prompts (
                        uuid,
                        project_id,
                        signature_id,
                        version_number,
                        name,
                        system_prompt,
                        user_prompt,
                        few_shot_examples,
                        modules_config,
                        parent_version_id,
                        change_description,
                        client_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING *
                """

                payload = (
                    new_uuid,
                    target_prompt.get("project_id"),
                    target_prompt.get("signature_id"),
                    next_version,
                    target_prompt.get("name"),
                    target_prompt.get("system_prompt"),
                    target_prompt.get("user_prompt"),
                    json.dumps(target_prompt.get("few_shot_examples"))
                    if target_prompt.get("few_shot_examples") is not None
                    else None,
                    json.dumps(target_prompt.get("modules_config"))
                    if target_prompt.get("modules_config") is not None
                    else None,
                    prompt_id,
                    f"Reverted to version {target_version}",
                    client_id or current_prompt.get("client_id") or self.client_id,
                )

                cursor.execute(insert_sql, payload)
                new_row = cursor.fetchone()
                prompt = self._row_to_dict(cursor, new_row)

        self._log_sync_event(
            "prompt_studio_prompt",
            prompt.get("uuid", ""),
            "version_revert",
            {
                "prompt_id": prompt_id,
                "target_version": target_version,
                "new_version": prompt.get("version_number"),
            },
        )
        return prompt

    def get_golden_test_cases(
        self,
        project_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        query = (
            """
            SELECT id, uuid, project_id, signature_id, name, description,
                   inputs, expected_outputs, actual_outputs, tags,
                   is_golden, is_generated, client_id, deleted,
                   created_at, updated_at
            FROM prompt_studio_test_cases
            WHERE project_id = ? AND is_golden = TRUE
        """
        )
        params: List[Any] = [project_id]
        query += " AND deleted = FALSE"  # Always exclude deleted in helper
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        try:
            cursor = self._execute(query, params)
            rows = cursor.fetchall()
            return [self._format_test_case(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch golden test cases for project {project_id}: {exc}") from exc

    # --- Test case helpers -------------------------------------------------

    def _format_test_case(self, row: Any) -> Optional[Dict[str, Any]]:
        return _format_test_case_record(self._row_to_dict(row))

    def _build_test_case_filters(
        self,
        project_id: int,
        *,
        signature_id: Optional[int] = None,
        is_golden: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        include_deleted: bool = False,
    ) -> Tuple[str, List[Any]]:
        conditions: List[str] = ["project_id = ?"]
        params: List[Any] = [project_id]

        if not include_deleted:
            conditions.append("deleted = 0")

        if signature_id is not None:
            conditions.append("signature_id = ?")
            params.append(signature_id)

        if is_golden is not None:
            conditions.append("is_golden = ?")
            params.append(bool(is_golden) if self.backend_type == BackendType.POSTGRESQL else int(bool(is_golden)))

        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            if tag_conditions:
                conditions.append(f"({' OR '.join(tag_conditions)})")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where_clause, params

    def create_test_case(
        self,
        project_id: int,
        name: str,
        *,
        inputs: Dict[str, Any],
        description: Optional[str] = None,
        expected_outputs: Optional[Dict[str, Any]] = None,
        actual_outputs: Optional[Dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        is_golden: bool = False,
        is_generated: bool = False,
        signature_id: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not name or not name.strip():
            raise InputError("Test case name cannot be empty")

        test_case_uuid = str(uuid.uuid4())
        payload = (
            test_case_uuid,
            project_id,
            signature_id,
            name.strip(),
            description,
            json.dumps(inputs),
            json.dumps(expected_outputs) if expected_outputs is not None else None,
            json.dumps(actual_outputs) if actual_outputs is not None else None,
            _serialise_tags(tags),
            bool(is_golden) if self.backend_type == BackendType.POSTGRESQL else int(bool(is_golden)),
            bool(is_generated) if self.backend_type == BackendType.POSTGRESQL else int(bool(is_generated)),
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_test_cases (
                uuid, project_id, signature_id, name, description,
                inputs, expected_outputs, actual_outputs, tags,
                is_golden, is_generated, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
                    test_case = self._format_test_case(row)
            return test_case or {}
        except BackendDatabaseError as exc:
            message = str(exc).lower()
            if "unique" in message and "prompt_studio_test_cases" in message and "name" in message:
                raise ConflictError(f"Test case with name '{name}' already exists") from exc
            raise DatabaseError(f"Failed to create prompt studio test case: {exc}") from exc

    def get_test_case(
        self,
        test_case_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        where_clauses = ["id = ?"]
        params: List[Any] = [test_case_id]
        if not include_deleted:
            where_clauses.append("deleted = 0")

        query = (
            "SELECT * FROM prompt_studio_test_cases WHERE "
            + " AND ".join(where_clauses)
            + " LIMIT 1"
        )

        try:
            cursor = self._execute(query, params)
            row = cursor.fetchone()
            return self._format_test_case(row)
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch test case {test_case_id}: {exc}") from exc

    def list_test_cases(
        self,
        project_id: int,
        *,
        signature_id: Optional[int] = None,
        is_golden: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 20,
        return_pagination: bool = False,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        where_clause, params = self._build_test_case_filters(
            project_id,
            signature_id=signature_id,
            is_golden=is_golden,
            tags=tags,
            include_deleted=include_deleted,
        )

        if search:
            comparator = "ILIKE" if self.backend_type == BackendType.POSTGRESQL else "LIKE"
            where_clause += f" AND (name {comparator} ? OR description {comparator} ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        count_sql = f"SELECT COUNT(*) FROM prompt_studio_test_cases{where_clause}"
        try:
            count_cursor = self._execute(count_sql, params)
            count_row = count_cursor.fetchone()
            total = int(count_row[0]) if count_row else 0
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to count test cases for project {project_id}: {exc}") from exc

        offset = max(page - 1, 0) * per_page
        list_sql = f"""
            SELECT *
            FROM prompt_studio_test_cases
            {where_clause}
            ORDER BY is_golden DESC, created_at DESC
            LIMIT ? OFFSET ?
        """
        params_with_pagination = params + [per_page, offset]

        try:
            cursor = self._execute(list_sql, params_with_pagination)
            rows = cursor.fetchall()
            records = [self._format_test_case(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to list test cases for project {project_id}: {exc}") from exc

        if return_pagination:
            return {
                "test_cases": records,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        return records

    def update_test_case(self, test_case_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = {
            "name",
            "description",
            "inputs",
            "expected_outputs",
            "actual_outputs",
            "tags",
            "is_golden",
            "is_generated",
            "signature_id",
        }
        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                continue

            if field in {"inputs", "expected_outputs", "actual_outputs"} and value is not None:
                params.append(json.dumps(value))
            elif field in {"is_golden", "is_generated"} and value is not None:
                params.append(int(bool(value)))
            elif field == "tags":
                params.append(_serialise_tags(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        if not set_clauses:
            existing = self.get_test_case(test_case_id)
            if existing is None:
                raise InputError(f"Test case {test_case_id} not found or already deleted")
            return existing

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(test_case_id)

        update_sql = f"""
            UPDATE prompt_studio_test_cases
            SET {', '.join(set_clauses)}
            WHERE id = ? AND deleted = 0
            RETURNING *
        """

        try:
            with self.transaction() as conn:
                cursor = self._cursor_exec(conn, update_sql, params)
                row = cursor.fetchone()
                if not row:
                    raise InputError(f"Test case {test_case_id} not found or already deleted")
                return self._format_test_case(row) or {}
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to update test case {test_case_id}: {exc}") from exc

    def delete_test_case(self, test_case_id: int, *, hard_delete: bool = False) -> bool:
        try:
            with self.transaction() as conn:
                if hard_delete:
                    cursor = self._cursor_exec(
                        conn,
                        "DELETE FROM prompt_studio_test_cases WHERE id = ? RETURNING id",
                        (test_case_id,),
                    )
                else:
                    cursor = self._cursor_exec(
                        conn,
                        """
                        UPDATE prompt_studio_test_cases
                        SET deleted = 1,
                            deleted_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND deleted = 0
                        RETURNING id
                        """,
                        (test_case_id,),
                    )
                row = cursor.fetchone()
                return row is not None
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to delete test case {test_case_id}: {exc}") from exc

    def create_bulk_test_cases(
        self,
        project_id: int,
        test_cases: List[Dict[str, Any]],
        *,
        signature_id: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        created: List[Dict[str, Any]] = []
        for test_case in test_cases:
            created_case = self.create_test_case(
                project_id,
                test_case.get("name", ""),
                inputs=test_case.get("inputs", {}),
                description=test_case.get("description"),
                expected_outputs=test_case.get("expected_outputs"),
                actual_outputs=test_case.get("actual_outputs"),
                tags=test_case.get("tags"),
                is_golden=test_case.get("is_golden", False),
                is_generated=test_case.get("is_generated", False),
                signature_id=signature_id or test_case.get("signature_id"),
                client_id=client_id or test_case.get("client_id"),
            )
            created.append(created_case)
        return created

    def search_test_cases(
        self,
        project_id: int,
        query: str,
        *,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        backend_query = query
        if self.backend_type == BackendType.POSTGRESQL:
            backend_query = FTSQueryTranslator.normalize_query(query, "postgresql") or query
            fts_column = self.get_fts_column("prompt_studio_test_cases") or "prompt_studio_test_cases_tsv"
            search_sql = f"""
                SELECT tc.*, ts_rank({fts_column}, to_tsquery('english', ?)) AS rank
                FROM prompt_studio_test_cases tc
                WHERE tc.project_id = ?
                  AND tc.deleted = FALSE
                  AND {fts_column} @@ to_tsquery('english', ?)
                ORDER BY rank DESC
                LIMIT ?
            """
            params = [backend_query, project_id, backend_query, limit]
        else:
            search_sql = """
                SELECT tc.*
                FROM prompt_studio_test_cases tc
                JOIN prompt_studio_test_cases_fts ON tc.id = prompt_studio_test_cases_fts.rowid
                WHERE tc.project_id = ?
                  AND tc.deleted = 0
                  AND prompt_studio_test_cases_fts MATCH ?
                ORDER BY bm25(prompt_studio_test_cases_fts)
                LIMIT ?
            """
            params = [project_id, backend_query, limit]

        try:
            cursor = self._execute(search_sql, params)
            rows = cursor.fetchall()
            return [self._format_test_case(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to search test cases in project {project_id}: {exc}") from exc

    def get_test_cases_by_signature(self, signature_id: int) -> List[Dict[str, Any]]:
        query = """
            SELECT *
            FROM prompt_studio_test_cases
            WHERE signature_id = ? AND deleted = 0
            ORDER BY is_golden DESC, created_at DESC
        """
        try:
            cursor = self._execute(query, [signature_id])
            rows = cursor.fetchall()
            return [self._format_test_case(row) for row in rows if row]
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to fetch test cases for signature {signature_id}: {exc}") from exc

    def get_test_case_stats(self, project_id: int) -> Dict[str, Any]:
        stats: Dict[str, Any] = {}
        try:
            total_cursor = self._execute(
                "SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = ? AND deleted = 0",
                (project_id,),
            )
            total_row = total_cursor.fetchone()
            stats["total"] = total_row[0] if total_row else 0

            golden_cursor = self._execute(
                "SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = ? AND deleted = 0 AND is_golden = 1",
                (project_id,),
            )
            golden_row = golden_cursor.fetchone()
            stats["golden"] = golden_row[0] if golden_row else 0

            generated_cursor = self._execute(
                "SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = ? AND deleted = 0 AND is_generated = 1",
                (project_id,),
            )
            generated_row = generated_cursor.fetchone()
            stats["generated"] = generated_row[0] if generated_row else 0

            expected_cursor = self._execute(
                "SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = ? AND deleted = 0 AND expected_outputs IS NOT NULL",
                (project_id,),
            )
            expected_row = expected_cursor.fetchone()
            stats["with_expected"] = expected_row[0] if expected_row else 0

            signature_cursor = self._execute(
                """
                SELECT signature_id, COUNT(*)
                FROM prompt_studio_test_cases
                WHERE project_id = ? AND deleted = 0 AND signature_id IS NOT NULL
                GROUP BY signature_id
                """,
                (project_id,),
            )
            stats["by_signature"] = {
                row[0]: row[1]
                for row in signature_cursor.fetchall()
                if row and row[0] is not None
            }

            tags_cursor = self._execute(
                """
                SELECT tags
                FROM prompt_studio_test_cases
                WHERE project_id = ? AND deleted = 0 AND tags IS NOT NULL
                """,
                (project_id,),
            )
            tag_counts: Dict[str, int] = {}
            for row in tags_cursor.fetchall():
                for tag in _parse_tags(row[0]):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

            stats["top_tags"] = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:10]
            return stats
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to compute test case stats for project {project_id}: {exc}") from exc

########################################################################################################################
# Prompt Studio Database Class

class _SQLitePromptStudioDatabase(PromptsDatabase):
    """
    Extends PromptsDatabase with Prompt Studio specific functionality.
    Manages projects, signatures, test cases, evaluations, and optimizations.
    """

    _PROMPT_STUDIO_SCHEMA_VERSION = 1

    def __init__(self, db_path: Union[str, Path], client_id: str):
        """
        Initialize PromptStudioDatabase with path and client ID.

        Args:
            db_path: Path to the database file
            client_id: Client identifier for sync logging
        """
        # Initialize parent class
        super().__init__(db_path, client_id)
        # Mark backend type for helper branches reused from backend-aware implementation
        self.backend_type = BackendType.SQLITE

        # Create a write lock for serializing write operations
        self._write_lock = threading.RLock()

        # Initialize prompt studio schema
        self._init_prompt_studio_schema()

        # Set pragmas for better reliability
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Keep SQLite lock wait short to avoid long blocking during concurrent tests
            # By default, avoid WAL for per-test temp DBs to reduce file artifact churn in CI.
            # Allow opting into WAL to mimic production via TLDW_PS_SQLITE_WAL=1
            try:
                import os as _ps_os
                _wal_requested = _ps_os.getenv("TLDW_PS_SQLITE_WAL", "0").lower() in {"1", "true", "yes", "on"}
                _mode = "WAL" if _wal_requested else "DELETE"
                cursor.execute(f"PRAGMA journal_mode={_mode}")
            except Exception:
                pass
            cursor.execute("PRAGMA busy_timeout=1000")  # 1 second timeout for locked database
            conn.commit()
        except Exception as e:
            logger.debug(f"Could not set pragmas: {e}")

        logger.info(f"PromptStudioDatabase initialized for {db_path} with client {client_id}")

    def _init_prompt_studio_schema(self):
        """Initialize Prompt Studio specific schema."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if prompt studio tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='prompt_studio_projects'
            """)

            if not cursor.fetchone():
                logger.info("Initializing Prompt Studio schema...")
                self._apply_prompt_studio_migrations(conn)
            # Ensure auxiliary tables exist even on existing DBs
            try:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS prompt_studio_idempotency (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        entity_type TEXT NOT NULL,
                        idempotency_key TEXT NOT NULL,
                        entity_id INTEGER NOT NULL,
                        user_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                # Composite uniqueness per user; SQLite treats NULLs as distinct, which is acceptable here
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_ps_idem_user ON prompt_studio_idempotency(entity_type, idempotency_key, user_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_ps_idem_entity ON prompt_studio_idempotency(entity_type, user_id)"
                )
                conn.commit()
            except Exception as _e:
                logger.warning(f"Failed ensuring idempotency table: {_e}")

            # Ensure leasing columns exist on job queue (SQLite)
            try:
                cursor.execute("SELECT leased_until FROM prompt_studio_job_queue LIMIT 1")
            except Exception:
                try:
                    cursor.execute("ALTER TABLE prompt_studio_job_queue ADD COLUMN leased_until TIMESTAMP")
                    conn.commit()
                except Exception:
                    pass
            try:
                cursor.execute("SELECT lease_owner FROM prompt_studio_job_queue LIMIT 1")
            except Exception:
                try:
                    cursor.execute("ALTER TABLE prompt_studio_job_queue ADD COLUMN lease_owner TEXT")
                    conn.commit()
                except Exception:
                    pass

        except Exception as e:
            logger.error(f"Error initializing Prompt Studio schema: {e}")
            raise SchemaError(f"Failed to initialize Prompt Studio schema: {e}")

    # Keep parity with backend helper: local execute that returns a cursor
    def _cursor_exec(self, conn: sqlite3.Connection, query: str, params: Optional[Union[Tuple, List, Dict, Any]] = None):
        cursor = conn.cursor()
        if params is not None:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def _apply_prompt_studio_migrations(self, conn: sqlite3.Connection):
        """Apply Prompt Studio migration scripts."""
        migrations_dir = Path(__file__).parent / "migrations"

        # List of migration files in order (ensure iterations table exists before indexes)
        migration_files = [
            "001_prompt_studio_schema.sql",
            "003_prompt_studio_iterations.sql",
            "002_prompt_studio_indexes.sql",
            "003_prompt_studio_triggers.sql",
            "004_prompt_studio_fts.sql",
        ]
        # Allow explicitly skipping FTS migrations when requested, but default to running them
        try:
            import os as _os
            if _os.getenv("SKIP_PROMPT_STUDIO_FTS", "").lower() == "true":
                migration_files = [mf for mf in migration_files if not mf.startswith("004_")]
        except Exception:
            pass

        for migration_file in migration_files:
            migration_path = migrations_dir / migration_file
            if migration_path.exists():
                logger.info(f"Applying migration: {migration_file}")
                with open(migration_path, 'r') as f:
                    migration_sql = f.read()

                # Execute migration statements
                try:
                    conn.executescript(migration_sql)
                    conn.commit()
                    logger.info(f"Successfully applied {migration_file}")
                except Exception as e:
                    logger.error(f"Failed to apply {migration_file}: {e}")
                    raise SchemaError(f"Migration {migration_file} failed: {e}")
            else:
                logger.warning(f"Migration file not found: {migration_path}")

    # --- Idempotency helpers (SQLite) ---
    def _idem_lookup(self, entity_type: str, key: str, user_id: Optional[str]) -> Optional[int]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            # Scoped lookup by entity_type and (user_id or NULL-scope). This prevents returning
            # mappings created by other users while preserving existing keys created without user scope.
            cursor.execute(
                """
                SELECT entity_id
                FROM prompt_studio_idempotency
                WHERE entity_type = ?
                  AND idempotency_key = ?
                  AND (user_id = ? OR user_id IS NULL)
                LIMIT 1
                """,
                (entity_type, key, user_id),
            )
            row = cursor.fetchone()
            return int(row[0]) if row else None
        except Exception:
            return None

    def _idem_record(self, entity_type: str, key: str, entity_id: int, user_id: Optional[str]) -> None:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO prompt_studio_idempotency (entity_type, idempotency_key, entity_id, user_id) VALUES (?, ?, ?, ?)",
                (entity_type, key, entity_id, user_id),
            )
            conn.commit()
        except Exception:
            pass

    ####################################################################################################################
    # Project Management

    def create_project(self, name: str, description: Optional[str] = None,
                      status: str = "draft", metadata: Optional[Dict] = None,
                      user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new prompt studio project.

        Args:
            name: Project name
            description: Project description
            status: Project status (draft, active, archived)
            metadata: Additional metadata

        Returns:
            Created project record
        """
        import time
        import sqlite3
        import random

        project_id = None
        # Get connection before acquiring lock to avoid deadlock
        conn = self.get_connection()

        max_retries = 5
        base_delay = 0.1  # 100ms

        for attempt in range(max_retries):
            should_retry = False
            retry_delay = 0

            # Use write lock to serialize write operations
            with self._write_lock:
                try:
                    cursor = conn.cursor()

                    # Generate UUID
                    project_uuid = str(uuid.uuid4())

                    # Insert project
                    cursor.execute("""
                        INSERT INTO prompt_studio_projects
                        (uuid, name, description, user_id, client_id, status, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (project_uuid, name, description, user_id or self.client_id, self.client_id,
                          status, json.dumps(metadata) if metadata else None))

                    project_id = cursor.lastrowid
                    conn.commit()

                    # Log to sync_log
                    self._log_sync_event("prompt_studio_project", project_uuid, "create", {
                        "name": name,
                        "description": description,
                        "status": status
                    })

                    logger.info(f"Created project: {name} (ID: {project_id})")
                    break  # Success, exit retry loop

                except sqlite3.OperationalError as e:
                    if "database is locked" in str(e) and attempt < max_retries - 1:
                        # Database locked, will retry
                        should_retry = True
                        retry_delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to create project: {e}")
                except sqlite3.IntegrityError as e:
                    if "UNIQUE" in str(e):
                        raise ConflictError(f"Project with name '{name}' already exists for this user")
                    raise DatabaseError(f"Failed to create project: {e}")
                except Exception as e:
                    raise DatabaseError(f"Failed to create project: {e}")

            # Sleep outside the lock if we need to retry
            if should_retry:
                time.sleep(retry_delay)

        # Get the project after releasing the lock
        return self.get_project(project_id)

    def get_project(self, project_id: int, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get a project by ID.

        Args:
            project_id: Project ID
            include_deleted: Include soft-deleted projects

        Returns:
            Project record or None
        """
        import sqlite3, time, random
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT
                id, uuid, name, description, user_id, client_id, status,
                deleted, deleted_at, created_at, updated_at, last_modified,
                version, metadata
            FROM prompt_studio_projects
            WHERE id = ?
        """
        if not include_deleted:
            query += " AND deleted = 0"

        max_retries = 5
        base_delay = 0.05
        for attempt in range(max_retries):
            try:
                cursor.execute(query, (project_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(cursor, row)
                return None
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    time.sleep(delay)
                    continue
                raise DatabaseError(f"Failed to get project: {e}")
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to get project: {e}")

    def list_projects(self, user_id: Optional[str] = None, status: Optional[str] = None,
                     include_deleted: bool = False, page: int = 1, per_page: int = 20,
                     search: Optional[str] = None) -> Dict[str, Any]:
        """
        List projects with optional filtering.

        Args:
            user_id: Filter by user ID
            status: Filter by status
            include_deleted: Include soft-deleted projects
            page: Page number
            per_page: Items per page

        Returns:
            Dictionary with projects list and pagination metadata
        """
        import sqlite3, time, random
        conn = self.get_connection()
        cursor = conn.cursor()

        # Build query
        conditions = []
        params = []
        if not include_deleted:
            conditions.append("deleted = 0")
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if search:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like])
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Count total with retry
        count_query = f"SELECT COUNT(*) FROM prompt_studio_projects{where_clause}"
        max_retries = 5
        base_delay = 0.05
        for attempt in range(max_retries):
            try:
                cursor.execute(count_query, params)
                total = cursor.fetchone()[0]
                break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    time.sleep(delay)
                    continue
                raise DatabaseError(f"Failed to list projects: {e}")
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to list projects: {e}")

        # Get projects with pagination (retry)
        offset = (page - 1) * per_page
        query = f"""
            SELECT
                p.*,
                (SELECT COUNT(*) FROM prompt_studio_prompts WHERE project_id = p.id AND deleted = 0) as prompt_count,
                (SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = p.id AND deleted = 0) as test_case_count
            FROM prompt_studio_projects p
            {where_clause}
            ORDER BY p.updated_at DESC
            LIMIT ? OFFSET ?
        """
        params_page = list(params) + [per_page, offset]
        for attempt in range(max_retries):
            try:
                cursor.execute(query, params_page)
                projects = [self._row_to_dict(cursor, row) for row in cursor.fetchall()]
                return {
                    "projects": projects,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "total_pages": (total + per_page - 1) // per_page
                    }
                }
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    time.sleep(delay)
                    continue
                raise DatabaseError(f"Failed to list projects: {e}")
            except sqlite3.Error as e:
                raise DatabaseError(f"Failed to list projects: {e}")

    def update_project(self, project_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a project.

        Args:
            project_id: Project ID
            updates: Fields to update

        Returns:
            Updated project record
        """
        import time
        import sqlite3
        import random

        conn = self.get_connection()
        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            project_uuid = None
            try:
                with self._write_lock:
                    cursor = conn.cursor()

                    # Build update query
                    allowed_fields = ["name", "description", "status", "metadata"]
                    set_clauses: List[str] = []
                    params: List[Any] = []

                    for field in allowed_fields:
                        if field in updates:
                            set_clauses.append(f"{field} = ?")
                            value = updates[field]
                            if field == "metadata" and value is not None:
                                value = json.dumps(value)
                            params.append(value)

                    if not set_clauses:
                        return self.get_project(project_id)

                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(project_id)

                    query = (
                        "UPDATE prompt_studio_projects "
                        f"SET {', '.join(set_clauses)} "
                        "WHERE id = ? AND deleted = 0"
                    )

                    cursor.execute(query, params)

                    if cursor.rowcount == 0:
                        raise InputError(f"Project {project_id} not found or already deleted")

                    cursor.execute(
                        "SELECT uuid FROM prompt_studio_projects WHERE id = ?",
                        (project_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        project_uuid = row[0]

                    conn.commit()

                if project_uuid:
                    self._log_sync_event(
                        "prompt_studio_project",
                        project_uuid,
                        "update",
                        updates,
                    )

                return self.get_project(project_id)

            except sqlite3.IntegrityError as exc:
                if "UNIQUE" in str(exc):
                    raise ConflictError("Project with name already exists")
                raise DatabaseError(f"Failed to update project: {exc}")
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    time.sleep(delay)
                    continue
                raise DatabaseError(f"Failed to update project: {exc}")
            except Exception as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to update project: {exc}")

        raise DatabaseError("Failed to update project after retries")

    ####################################################################################################################
    # Signature Management

    def create_signature(
        self,
        project_id: int,
        name: str,
        *,
        input_schema: Iterable[Any],
        output_schema: Iterable[Any],
        constraints: Optional[Any] = None,
        validation_rules: Optional[Any] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import sqlite3
        import time
        import random

        if not name or not str(name).strip():
            raise InputError("Signature name cannot be empty")

        conn = self.get_connection()
        signature_uuid = str(uuid.uuid4())
        payload = (
            signature_uuid,
            project_id,
            str(name).strip(),
            json.dumps(list(input_schema) if input_schema is not None else []),
            json.dumps(list(output_schema) if output_schema is not None else []),
            json.dumps(constraints) if constraints is not None else None,
            json.dumps(validation_rules) if validation_rules is not None else None,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_signatures (
                uuid, project_id, name, input_schema, output_schema,
                constraints, validation_rules, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(insert_sql, payload)
                    signature_id = cursor.lastrowid
                    conn.commit()

                    cursor.execute(
                        "SELECT * FROM prompt_studio_signatures WHERE id = ?",
                        (signature_id,),
                    )
                    row = cursor.fetchone()
                    signature = self._row_to_dict(cursor, row) if row else {}

                    self._log_sync_event(
                        "prompt_studio_signature",
                        signature_uuid,
                        "create",
                        {
                            "project_id": project_id,
                            "name": name,
                        },
                    )
                    return signature
                except sqlite3.IntegrityError as exc:
                    message = str(exc)
                    if "UNIQUE" in message:
                        raise ConflictError(
                            f"Signature with name '{name}' already exists for project {project_id}"
                        )
                    raise DatabaseError(f"Failed to create signature: {exc}") from exc
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to create signature: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to create signature: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        raise DatabaseError("Failed to create signature due to database locks")

    def get_signature(
        self,
        signature_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        import sqlite3
        import time
        import random

        conn = self.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM prompt_studio_signatures WHERE id = ?"
        params: List[Any] = [signature_id]
        if not include_deleted:
            query += " AND deleted = 0"

        max_retries = 5
        base_delay = 0.05
        for attempt in range(max_retries):
            try:
                cursor.execute(query, params)
                row = cursor.fetchone()
                return self._row_to_dict(cursor, row) if row else None
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    time.sleep(delay)
                    continue
                raise DatabaseError(f"Failed to fetch signature {signature_id}: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to fetch signature {signature_id}: {exc}") from exc

        return None

    def list_signatures(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
        search: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        return_pagination: bool = False,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        import sqlite3
        import time
        import random

        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = ["project_id = ?"]
        params: List[Any] = [project_id]
        if not include_deleted:
            conditions.append("deleted = 0")
        if search:
            conditions.append("name LIKE ?")
            params.append(f"%{search}%")

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_sql = f"SELECT COUNT(*) FROM prompt_studio_signatures{where_clause}"

        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            try:
                cursor.execute(count_sql, params)
                total_row = cursor.fetchone()
                total = int(total_row[0]) if total_row else 0
                break
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                raise DatabaseError(f"Failed to count signatures: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to count signatures: {exc}") from exc
        else:
            raise DatabaseError("Failed to count signatures due to database locks")

        offset = max(page - 1, 0) * per_page
        list_sql = (
            f"SELECT * FROM prompt_studio_signatures{where_clause} "
            "ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?"
        )
        params_with_pagination = params + [per_page, offset]

        for attempt in range(max_retries):
            try:
                cursor.execute(list_sql, params_with_pagination)
                rows = cursor.fetchall()
                signatures = [self._row_to_dict(cursor, row) for row in rows if row]
                break
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                raise DatabaseError(f"Failed to list signatures: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to list signatures: {exc}") from exc
        else:
            raise DatabaseError("Failed to list signatures due to database locks")

        if return_pagination:
            return {
                "signatures": signatures,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        return signatures

    def update_signature(self, signature_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        import sqlite3

        allowed_fields = {
            "name",
            "input_schema",
            "output_schema",
            "constraints",
            "validation_rules",
        }

        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                continue

            if field in {"input_schema", "output_schema", "constraints", "validation_rules"} and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        if not set_clauses:
            signature = self.get_signature(signature_id, include_deleted=True)
            if signature is None:
                raise InputError(f"Signature {signature_id} not found or already deleted")
            return signature

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(signature_id)

        update_sql = (
            "UPDATE prompt_studio_signatures SET "
            + ", ".join(set_clauses)
            + " WHERE id = ? AND deleted = 0"
        )

        conn = self.get_connection()

        with self._write_lock:
            try:
                cursor = conn.cursor()
                cursor.execute(update_sql, params)
                if cursor.rowcount == 0:
                    raise InputError(f"Signature {signature_id} not found or already deleted")
                conn.commit()
                cursor.execute(
                    "SELECT * FROM prompt_studio_signatures WHERE id = ?",
                    (signature_id,),
                )
                row = cursor.fetchone()
                if not row:
                    raise DatabaseError(f"Failed to fetch updated signature {signature_id}")
                signature = self._row_to_dict(cursor, row)
            except sqlite3.IntegrityError as exc:
                message = str(exc)
                if "UNIQUE" in message:
                    raise ConflictError("Signature update conflicts with existing record") from exc
                raise DatabaseError(f"Failed to update signature: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to update signature: {exc}") from exc

        self._log_sync_event(
            "prompt_studio_signature",
            signature.get("uuid", ""),
            "update",
            {key: updates[key] for key in updates if key in allowed_fields},
        )
        return signature

    def delete_signature(self, signature_id: int, *, hard_delete: bool = False) -> bool:
        import sqlite3
        import time

        conn = self.get_connection()
        cursor = conn.cursor()
        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            try:
                if hard_delete:
                    cursor.execute(
                        "SELECT uuid FROM prompt_studio_signatures WHERE id = ?",
                        (signature_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    signature_uuid = row[0]
                    cursor.execute(
                        "DELETE FROM prompt_studio_signatures WHERE id = ?",
                        (signature_id,),
                    )
                else:
                    cursor.execute(
                        "SELECT uuid FROM prompt_studio_signatures WHERE id = ? AND deleted = 0",
                        (signature_id,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return False
                    signature_uuid = row[0]
                    cursor.execute(
                        """
                        UPDATE prompt_studio_signatures
                        SET deleted = 1, deleted_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND deleted = 0
                        """,
                        (signature_id,),
                    )

                if cursor.rowcount > 0:
                    conn.commit()
                    self._log_sync_event(
                        "prompt_studio_signature",
                        signature_uuid,
                        "delete" if hard_delete else "soft_delete",
                        {"hard": hard_delete},
                    )
                    return True
                return False
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                raise DatabaseError(f"Failed to delete signature {signature_id}: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to delete signature {signature_id}: {exc}") from exc

        raise DatabaseError("Failed to delete signature due to database locks")

    ####################################################################################################################
    # Test Run Management

    def create_test_run(
        self,
        *,
        project_id: int,
        prompt_id: int,
        test_case_id: int,
        model_name: str,
        model_params: Optional[Dict[str, Any]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        outputs: Optional[Dict[str, Any]] = None,
        expected_outputs: Optional[Dict[str, Any]] = None,
        scores: Optional[Dict[str, Any]] = None,
        execution_time_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        cost_estimate: Optional[float] = None,
        error_message: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import sqlite3
        import time
        import random

        conn = self.get_connection()
        cursor = conn.cursor()
        run_uuid = str(uuid.uuid4())

        payload = (
            run_uuid,
            project_id,
            prompt_id,
            test_case_id,
            model_name,
            json.dumps(model_params) if model_params is not None else None,
            json.dumps(inputs) if inputs is not None else None,
            json.dumps(outputs) if outputs is not None else None,
            json.dumps(expected_outputs) if expected_outputs is not None else None,
            json.dumps(scores) if scores is not None else None,
            execution_time_ms,
            tokens_used,
            cost_estimate,
            error_message,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_test_runs (
                uuid, project_id, prompt_id, test_case_id, model_name,
                model_params, inputs, outputs, expected_outputs, scores,
                execution_time_ms, tokens_used, cost_estimate, error_message,
                client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        base_delay = 0.05
        for attempt in range(5):
            try:
                with self._write_lock:
                    cursor.execute(insert_sql, payload)
                    run_id = cursor.lastrowid
                    conn.commit()
                    cursor.execute(
                        "SELECT * FROM prompt_studio_test_runs WHERE id = ?",
                        (run_id,),
                    )
                    row = cursor.fetchone()
                    return self._row_to_dict(cursor, row) if row else {}
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < 4:
                    time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                raise DatabaseError(f"Failed to create test run: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to create test run: {exc}") from exc

        raise DatabaseError("Failed to create test run due to database locks")

    def get_test_cases_by_ids(
        self,
        test_case_ids: Iterable[int],
        *,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        import sqlite3

        identifiers = list(dict.fromkeys(test_case_ids))
        if not identifiers:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        placeholders = ",".join(["?"] * len(identifiers))
        query = f"SELECT * FROM prompt_studio_test_cases WHERE id IN ({placeholders})"
        if not include_deleted:
            query += " AND deleted = 0"

        try:
            cursor.execute(query, identifiers)
            rows = cursor.fetchall()
            return [self._format_test_case(cursor, row) for row in rows if row]
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to fetch test cases: {exc}") from exc

    ####################################################################################################################
    # Evaluation Management

    def create_evaluation(
        self,
        *,
        prompt_id: int,
        project_id: int,
        model_configs: Optional[Dict[str, Any]] = None,
        status: str = "running",
        test_case_ids: Optional[Iterable[int]] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import sqlite3
        import time
        import random

        conn = self.get_connection()
        cursor = conn.cursor()

        eval_uuid = str(uuid.uuid4())
        payload = (
            eval_uuid,
            prompt_id,
            project_id,
            json.dumps(model_configs) if model_configs is not None else None,
            status,
            json.dumps(list(test_case_ids) if test_case_ids is not None else []),
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_evaluations (
                uuid, prompt_id, project_id, model_configs, status,
                test_case_ids, started_at, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        """

        base_delay = 0.05
        for attempt in range(5):
            try:
                with self._write_lock:
                    cursor.execute(insert_sql, payload)
                    eval_id = cursor.lastrowid
                    conn.commit()
                    cursor.execute(
                        "SELECT * FROM prompt_studio_evaluations WHERE id = ?",
                        (eval_id,),
                    )
                    row = cursor.fetchone()
                    return self._row_to_dict(cursor, row) if row else {}
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < 4:
                    time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                raise DatabaseError(f"Failed to create evaluation: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to create evaluation: {exc}") from exc

        raise DatabaseError("Failed to create evaluation due to database locks")

    def update_evaluation(self, evaluation_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        import sqlite3

        if not updates:
            evaluation = self.get_evaluation(evaluation_id)
            if evaluation is None:
                raise InputError(f"Evaluation {evaluation_id} not found")
            return evaluation

        json_fields = {"model_configs", "test_case_ids", "test_run_ids", "aggregate_metrics"}
        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field in json_fields and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        params.append(evaluation_id)

        query = (
            "UPDATE prompt_studio_evaluations SET "
            + ", ".join(set_clauses)
            + " WHERE id = ?"
        )

        with self._write_lock:
            cursor = self.get_connection().cursor()
            try:
                cursor.execute(query, params)
                if cursor.rowcount == 0:
                    raise InputError(f"Evaluation {evaluation_id} not found")
                self.get_connection().commit()
                cursor.execute(
                    "SELECT * FROM prompt_studio_evaluations WHERE id = ?",
                    (evaluation_id,),
                )
                row = cursor.fetchone()
                if not row:
                    raise DatabaseError(f"Failed to fetch evaluation {evaluation_id}")
                return self._row_to_dict(cursor, row)
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to update evaluation: {exc}") from exc

    def get_evaluation(self, evaluation_id: int) -> Optional[Dict[str, Any]]:
        import sqlite3

        cursor = self.get_connection().cursor()
        try:
            cursor.execute(
                "SELECT * FROM prompt_studio_evaluations WHERE id = ?",
                (evaluation_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_dict(cursor, row)
            return None
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to fetch evaluation {evaluation_id}: {exc}") from exc

    def list_evaluations(
        self,
        project_id: Optional[int] = None,
        prompt_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        import sqlite3
        import time
        import random

        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        conn = self.get_connection()
        cursor = conn.cursor()

        conditions: List[str] = []
        params: List[Any] = []
        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if prompt_id is not None:
            conditions.append("prompt_id = ?")
            params.append(prompt_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        count_query = f"SELECT COUNT(*) FROM prompt_studio_evaluations{where_clause}"

        base_delay = 0.05
        for attempt in range(5):
            try:
                cursor.execute(count_query, params)
                total = cursor.fetchone()[0]
                break
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < 4:
                    time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                raise DatabaseError(f"Failed to list evaluations: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to list evaluations: {exc}") from exc
        else:
            raise DatabaseError("Failed to list evaluations due to database locks")

        offset = (page - 1) * per_page
        query = f"""
            SELECT *
            FROM prompt_studio_evaluations
            {where_clause}
            ORDER BY started_at DESC, id DESC
            LIMIT ? OFFSET ?
        """
        params_with_page = list(params) + [per_page, offset]

        for attempt in range(5):
            try:
                cursor.execute(query, params_with_page)
                rows = cursor.fetchall()
                evaluations = [self._row_to_dict(cursor, row) for row in rows if row]
                return {
                    "evaluations": evaluations,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                        "total_pages": (total + per_page - 1) // per_page
                    }
                }
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < 4:
                    time.sleep(base_delay * (2 ** attempt) * (0.5 + random.random()))
                    continue
                raise DatabaseError(f"Failed to list evaluations: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to list evaluations: {exc}") from exc

        raise DatabaseError("Failed to list evaluations due to database locks")

    def create_prompt(
        self,
        project_id: int,
        name: str,
        *,
        signature_id: Optional[int] = None,
        version_number: int = 1,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        few_shot_examples: Optional[Any] = None,
        modules_config: Optional[Any] = None,
        parent_version_id: Optional[int] = None,
        change_description: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import time
        import random

        prompt_uuid = str(uuid.uuid4())
        payload = (
            prompt_uuid,
            project_id,
            signature_id,
            version_number,
            name,
            system_prompt,
            user_prompt,
            json.dumps(few_shot_examples) if few_shot_examples is not None else None,
            json.dumps(modules_config) if modules_config is not None else None,
            parent_version_id,
            change_description,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_prompts (
                uuid, project_id, signature_id, version_number, name, system_prompt,
                user_prompt, few_shot_examples, modules_config, parent_version_id,
                change_description, client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        conn = self.get_connection()
        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(insert_sql, payload)
                    prompt_id = cursor.lastrowid
                    conn.commit()
                    prompt = self.get_prompt(prompt_id)
                    self._log_sync_event(
                        "prompt_studio_prompt",
                        prompt_uuid,
                        "create",
                        {
                            "project_id": project_id,
                            "name": name,
                            "version_number": version_number,
                        },
                    )
                    return prompt or {}
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to create prompt: {exc}") from exc
                except sqlite3.IntegrityError as exc:
                    if "UNIQUE" in str(exc).upper():
                        raise ConflictError(
                            f"Prompt with name '{name}' already exists in project {project_id}"
                        ) from exc
                    raise DatabaseError(f"Failed to create prompt: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        raise DatabaseError("Failed to create prompt after multiple retries")

    def delete_project(self, project_id: int, hard_delete: bool = False) -> bool:
        """
        Delete a project (soft delete by default).

        Args:
            project_id: Project ID
            hard_delete: Permanently delete if True

        Returns:
            True if deleted
        """
        import sqlite3
        import time
        import random

        conn = self.get_connection()
        max_retries = 5
        base_delay = 0.1

        for attempt in range(max_retries):
            should_retry = False
            try:
                with self._write_lock:
                    cursor = conn.cursor()
                    if hard_delete:
                        # Cascade delete all related data
                        cursor.execute("DELETE FROM prompt_studio_projects WHERE id = ?", (project_id,))
                    else:
                        # Soft delete
                        cursor.execute(
                            """
                            UPDATE prompt_studio_projects
                            SET deleted = 1, deleted_at = CURRENT_TIMESTAMP
                            WHERE id = ? AND deleted = 0
                            """,
                            (project_id,)
                        )
                    success = cursor.rowcount > 0
                    if success:
                        conn.commit()
                        logger.info(f"{'Hard' if hard_delete else 'Soft'} deleted project {project_id}")
                    return success
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    should_retry = True
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    logger.warning(f"Delete project locked, retrying in {delay:.3f}s (attempt {attempt+1})")
                    time.sleep(delay)
                else:
                    raise DatabaseError(f"Failed to delete project: {e}")
            except Exception as e:
                raise DatabaseError(f"Failed to delete project: {e}")

            if not should_retry:
                break

        return False

    ####################################################################################################################
    # Helper Methods

    def _row_to_dict(self, cursor: sqlite3.Cursor, row: tuple) -> Dict[str, Any]:
        """Convert a database row to dictionary."""
        if not row:
            return None

        columns = [description[0] for description in cursor.description]
        result = dict(zip(columns, row))

        # Parse JSON fields
        json_fields = ["metadata", "input_schema", "output_schema", "constraints",
                      "validation_rules", "few_shot_examples", "modules_config",
                      "model_params", "inputs", "outputs", "expected_outputs",
                      "actual_outputs", "scores", "test_case_ids", "test_run_ids",
                      "aggregate_metrics", "model_configs", "payload", "result",
                      "initial_metrics", "final_metrics", "optimization_config"]

        for field in json_fields:
            if field in result and result[field]:
                try:
                    result[field] = json.loads(result[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Parse datetime fields
        datetime_fields = ["created_at", "updated_at", "deleted_at", "last_modified",
                          "started_at", "completed_at"]

        for field in datetime_fields:
            if field in result and result[field]:
                try:
                    if isinstance(result[field], str):
                        result[field] = datetime.fromisoformat(result[field])
                except (ValueError, TypeError):
                    pass

        return result

    def _log_sync_event(self, entity: str, entity_uuid: str, operation: str, payload: Dict[str, Any]):
        """Log an event to sync_log table if it exists."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if sync_log table exists
            cursor.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='sync_log'
                """
            )

            if cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO sync_log (
                        entity,
                        entity_uuid,
                        operation,
                        client_id,
                        version,
                        payload,
                        timestamp
                    )
                    VALUES (?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        entity,
                        entity_uuid,
                        operation,
                        self.client_id,
                        json.dumps(payload),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.debug(f"Could not log sync event: {e}")

    # Public convenience alias matching some endpoint call sites
    def row_to_dict(self, row: tuple, cursor: sqlite3.Cursor) -> Dict[str, Any]:
        """
        Convert a (row, cursor) pair to a dict. Wrapper around _row_to_dict,
        provided to match call sites that pass (row, cursor) in that order.
        """
        return self._row_to_dict(cursor, row)

    def _format_test_case(self, cursor: sqlite3.Cursor, row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        return _format_test_case_record(self._row_to_dict(cursor, row))

    ####################################################################################################################
    # Prompt Accessors (Prompt Studio tables)

    def get_prompt(self, prompt_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a prompt-studio prompt by id from the prompt_studio_prompts table.

        Args:
            prompt_id: ID of the prompt (prompt_studio_prompts.id)

        Returns:
            A dictionary representing the prompt or None if not found.
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT *
                FROM prompt_studio_prompts
                WHERE id = ? AND deleted = 0
                """,
                (prompt_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(cursor, row)
        except Exception as e:
            logger.error(f"Failed to get prompt {prompt_id}: {e}")
            return None

    def get_prompt_with_project(
        self,
        prompt_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            clause = "" if include_deleted else "AND p.deleted = 0"
            cursor.execute(
                f"""
                SELECT p.*, proj.user_id AS project_user_id
                FROM prompt_studio_prompts p
                JOIN prompt_studio_projects proj ON p.project_id = proj.id
                WHERE p.id = ? {clause}
                """,
                (prompt_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_dict(cursor, row)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Failed to fetch prompt {prompt_id}: {exc}")
            return None

    def create_prompt_version(
        self,
        prompt_id: int,
        *,
        change_description: str,
        name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        few_shot_examples: Optional[Any] = None,
        modules_config: Optional[Any] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import random
        import time

        if not change_description:
            raise InputError("change_description is required")

        conn = self.get_connection()
        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT *
                        FROM prompt_studio_prompts
                        WHERE id = ? AND deleted = 0
                        """,
                        (prompt_id,),
                    )
                    current_row = cursor.fetchone()
                    if not current_row:
                        raise InputError(f"Prompt {prompt_id} not found or already deleted")
                    current_prompt = self._row_to_dict(cursor, current_row)

                    new_uuid = str(uuid.uuid4())
                    new_version = int(current_prompt.get("version_number", 0)) + 1

                    next_name = name if name is not None else current_prompt.get("name")
                    next_system = (
                        system_prompt
                        if system_prompt is not None
                        else current_prompt.get("system_prompt")
                    )
                    next_user = (
                        user_prompt
                        if user_prompt is not None
                        else current_prompt.get("user_prompt")
                    )
                    next_examples = (
                        few_shot_examples
                        if few_shot_examples is not None
                        else current_prompt.get("few_shot_examples")
                    )
                    next_modules = (
                        modules_config
                        if modules_config is not None
                        else current_prompt.get("modules_config")
                    )

                    cursor.execute(
                        """
                        INSERT INTO prompt_studio_prompts (
                            uuid, project_id, signature_id, version_number, name,
                            system_prompt, user_prompt, few_shot_examples, modules_config,
                            parent_version_id, change_description, client_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_uuid,
                            current_prompt.get("project_id"),
                            current_prompt.get("signature_id"),
                            new_version,
                            next_name,
                            next_system,
                            next_user,
                            json.dumps(next_examples) if next_examples is not None else None,
                            json.dumps(next_modules) if next_modules is not None else None,
                            prompt_id,
                            change_description,
                            client_id or current_prompt.get("client_id") or self.client_id,
                        ),
                    )

                    new_prompt_id = cursor.lastrowid
                    conn.commit()

                    cursor.execute(
                        "SELECT * FROM prompt_studio_prompts WHERE id = ?",
                        (new_prompt_id,),
                    )
                    row = cursor.fetchone()
                    prompt = self._row_to_dict(cursor, row) if row else {}

                    self._log_sync_event(
                        "prompt_studio_prompt",
                        prompt.get("uuid", ""),
                        "version_create",
                        {
                            "prompt_id": prompt_id,
                            "new_version": prompt.get("version_number"),
                            "change_description": change_description,
                        },
                    )
                    return prompt
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to create prompt version: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to create prompt version: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        raise DatabaseError("Failed to create prompt version due to database locks")

    def revert_prompt_to_version(
        self,
        prompt_id: int,
        target_version: int,
        *,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import random
        import time

        if target_version < 1:
            raise InputError("target_version must be >= 1")

        conn = self.get_connection()
        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT * FROM prompt_studio_prompts
                        WHERE id = ? AND deleted = 0
                        """,
                        (prompt_id,),
                    )
                    current_row = cursor.fetchone()
                    if not current_row:
                        raise InputError(f"Prompt {prompt_id} not found or already deleted")
                    current_prompt = self._row_to_dict(cursor, current_row)

                    cursor.execute(
                        """
                        SELECT * FROM prompt_studio_prompts
                        WHERE project_id = ? AND name = ? AND version_number = ? AND deleted = 0
                        """,
                        (
                            current_prompt.get("project_id"),
                            current_prompt.get("name"),
                            target_version,
                        ),
                    )
                    target_row = cursor.fetchone()
                    if not target_row:
                        raise InputError(
                            f"Version {target_version} not found for this prompt"
                        )
                    target_prompt = self._row_to_dict(cursor, target_row)

                    cursor.execute(
                        """
                        SELECT MAX(version_number) FROM prompt_studio_prompts
                        WHERE project_id = ? AND name = ?
                        """,
                        (current_prompt.get("project_id"), current_prompt.get("name")),
                    )
                    max_version = cursor.fetchone()[0] or 0
                    new_version = max_version + 1

                    new_uuid = str(uuid.uuid4())
                    cursor.execute(
                        """
                        INSERT INTO prompt_studio_prompts (
                            uuid, project_id, signature_id, version_number, name,
                            system_prompt, user_prompt, few_shot_examples, modules_config,
                            parent_version_id, change_description, client_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            new_uuid,
                            target_prompt.get("project_id"),
                            target_prompt.get("signature_id"),
                            new_version,
                            target_prompt.get("name"),
                            target_prompt.get("system_prompt"),
                            target_prompt.get("user_prompt"),
                            json.dumps(target_prompt.get("few_shot_examples"))
                            if target_prompt.get("few_shot_examples") is not None
                            else None,
                            json.dumps(target_prompt.get("modules_config"))
                            if target_prompt.get("modules_config") is not None
                            else None,
                            prompt_id,
                            f"Reverted to version {target_version}",
                            client_id or current_prompt.get("client_id") or self.client_id,
                        ),
                    )

                    new_prompt_id = cursor.lastrowid
                    conn.commit()

                    cursor.execute(
                        "SELECT * FROM prompt_studio_prompts WHERE id = ?",
                        (new_prompt_id,),
                    )
                    row = cursor.fetchone()
                    prompt = self._row_to_dict(cursor, row) if row else {}

                    self._log_sync_event(
                        "prompt_studio_prompt",
                        prompt.get("uuid", ""),
                        "version_revert",
                        {
                            "prompt_id": prompt_id,
                            "target_version": target_version,
                            "new_version": prompt.get("version_number"),
                        },
                    )
                    return prompt
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to revert prompt: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to revert prompt: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        raise DatabaseError("Failed to revert prompt due to database locks")

    # --- Optimization helpers -------------------------------------------------

    def get_optimization(
        self,
        optimization_id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            clause = "" if include_deleted else " AND deleted = 0"
            cursor.execute(
                f"""
                SELECT *
                FROM prompt_studio_optimizations
                WHERE id = ?{clause}
                LIMIT 1
                """,
                (optimization_id,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to fetch optimization {optimization_id}: {exc}") from exc

    def update_optimization(
        self,
        optimization_id: int,
        updates: Dict[str, Any],
        *,
        set_started_at: bool = False,
        set_completed_at: bool = False,
    ) -> Dict[str, Any]:
        if not updates and not (set_started_at or set_completed_at):
            optimization = self.get_optimization(optimization_id, include_deleted=True)
            if optimization is None:
                raise InputError(f"Optimization {optimization_id} not found")
            return optimization

        json_fields = {"optimization_config", "initial_metrics", "final_metrics"}
        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field in json_fields and value is not None:
                params.append(json.dumps(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        if set_started_at:
            set_clauses.append("started_at = CURRENT_TIMESTAMP")
        if set_completed_at:
            set_clauses.append("completed_at = CURRENT_TIMESTAMP")

        params.append(optimization_id)
        sql = (
            "UPDATE prompt_studio_optimizations SET "
            + ", ".join(set_clauses)
            + " WHERE id = ?"
        )

        try:
            with self._write_lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute(sql, params)
                if cursor.rowcount == 0:
                    raise InputError(f"Optimization {optimization_id} not found")
                conn.commit()

                cursor.execute(
                    "SELECT * FROM prompt_studio_optimizations WHERE id = ?",
                    (optimization_id,),
                )
                row = cursor.fetchone()
                optimization = self._row_to_dict(cursor, row) if row else {}
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to update optimization {optimization_id}: {exc}") from exc

        log_payload = {}
        for key, value in updates.items():
            if isinstance(value, (dict, list)):
                try:
                    log_payload[key] = json.loads(json.dumps(value, default=str))
                except TypeError:
                    log_payload[key] = str(value)
            else:
                log_payload[key] = value
        if set_started_at:
            log_payload["started_at"] = "CURRENT_TIMESTAMP"
        if set_completed_at:
            log_payload["completed_at"] = "CURRENT_TIMESTAMP"

        self._log_sync_event(
            "prompt_studio_optimization",
            optimization.get("uuid", ""),
            "update",
            log_payload,
        )
        return optimization

    def set_optimization_status(
        self,
        optimization_id: int,
        status: str,
        *,
        error_message: Optional[str] = None,
        mark_started: bool = False,
        mark_completed: bool = False,
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {"status": status}
        if error_message is not None:
            updates["error_message"] = error_message
        return self.update_optimization(
            optimization_id,
            updates,
            set_started_at=mark_started,
            set_completed_at=mark_completed,
        )

    def complete_optimization(
        self,
        optimization_id: int,
        *,
        optimized_prompt_id: Optional[int] = None,
        iterations_completed: Optional[int] = None,
        initial_metrics: Optional[Dict[str, Any]] = None,
        final_metrics: Optional[Dict[str, Any]] = None,
        improvement_percentage: Optional[float] = None,
        total_tokens: Optional[int] = None,
        total_cost: Optional[float] = None,
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {
            "status": "completed",
            "optimized_prompt_id": optimized_prompt_id,
            "iterations_completed": iterations_completed,
            "initial_metrics": initial_metrics,
            "final_metrics": final_metrics,
            "improvement_percentage": improvement_percentage,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
        }
        updates = {k: v for k, v in updates.items() if v is not None}
        return self.update_optimization(
            optimization_id,
            updates,
            set_completed_at=True,
        )

    def record_optimization_iteration(
        self,
        optimization_id: int,
        *,
        iteration_number: int,
        prompt_variant: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
        cost: Optional[float] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = (
            str(uuid.uuid4()),
            optimization_id,
            iteration_number,
            json.dumps(prompt_variant) if prompt_variant is not None else None,
            json.dumps(metrics) if metrics is not None else None,
            tokens_used,
            cost,
            note,
        )

        try:
            with self._write_lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO prompt_studio_optimization_iterations (
                        uuid, optimization_id, iteration_number, prompt_variant,
                        metrics, tokens_used, cost, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                iteration_id = cursor.lastrowid
                conn.commit()

                cursor.execute(
                    "SELECT * FROM prompt_studio_optimization_iterations WHERE id = ?",
                    (iteration_id,),
                )
                row = cursor.fetchone()
                record = self._row_to_dict(cursor, row) if row else {}
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to record optimization iteration: {exc}") from exc

        self._log_sync_event(
            "prompt_studio_optimization_iteration",
            record.get("uuid", ""),
            "create",
            {
                "optimization_id": optimization_id,
                "iteration_number": iteration_number,
            },
        )
        return record

    def list_optimization_iterations(
        self,
        optimization_id: int,
        *,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        """List persisted iterations for an optimization (SQLite backend)."""
        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM prompt_studio_optimization_iterations WHERE optimization_id = ?",
                (optimization_id,),
            )
            row = cursor.fetchone()
            total = int(row[0]) if row and row[0] is not None else 0

            offset = max(page - 1, 0) * per_page
            cursor.execute(
                """
                SELECT *
                FROM prompt_studio_optimization_iterations
                WHERE optimization_id = ?
                ORDER BY iteration_number ASC, id ASC
                LIMIT ? OFFSET ?
                """,
                (optimization_id, per_page, offset),
            )
            rows = cursor.fetchall()
            iterations = [self._row_to_dict(cursor, r) for r in rows if r]

            return {
                "iterations": iterations,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to list optimization iterations: {exc}") from exc

    # --- Job queue helpers ---

    def create_job(
        self,
        job_type: str,
        entity_id: int,
        payload: Optional[Any],
        *,
        project_id: Optional[int] = None,
        priority: int = 5,
        status: str = "queued",
        max_retries: int = 3,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        import random
        import time

        conn = self.get_connection()
        job_uuid = str(uuid.uuid4())
        payload_json = json.dumps(payload) if payload is not None else json.dumps({})
        base_delay = 0.05

        for attempt in range(5):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO prompt_studio_job_queue (
                            uuid, job_type, entity_id, project_id, priority, status,
                            payload, max_retries, client_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_uuid,
                            job_type,
                            entity_id,
                            project_id,
                            priority,
                            status,
                            payload_json,
                            max_retries,
                            client_id or self.client_id,
                        ),
                    )
                    job_id = cursor.lastrowid
                    conn.commit()
                    return self.get_job(job_id) or {}
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < 4:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to create job: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to create job: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        raise DatabaseError("Failed to create job due to database locks")

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM prompt_studio_job_queue WHERE id = ?",
                (job_id,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to fetch job {job_id}: {exc}") from exc

    def get_job_by_uuid(self, job_uuid: str) -> Optional[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM prompt_studio_job_queue WHERE uuid = ?",
                (job_uuid,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to fetch job {job_uuid}: {exc}") from exc

    def list_jobs(
        self,
        *,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            query = "SELECT * FROM prompt_studio_job_queue WHERE 1=1"
            params: List[Any] = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
            query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows if row]
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to list prompt studio jobs: {exc}") from exc

    def update_job_status(
        self,
        job_id: int,
        status: str,
        *,
        error_message: Optional[str] = None,
        result: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        import random
        import time

        conn = self.get_connection()
        base_delay = 0.05

        for attempt in range(5):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    updates = ["status = ?"]
                    params: List[Any] = [status]

                    if status == "processing":
                        updates.append("started_at = CURRENT_TIMESTAMP")
                        # Extend lease window on explicit processing state
                        import os as _os_ul
                        try:
                            _lease_secs_upd = max(5, min(3600, int(_os_ul.getenv("TLDW_PS_JOB_LEASE_SECONDS", "60"))))
                        except Exception:
                            _lease_secs_upd = 60
                        updates.append(f"leased_until = DATETIME('now', '+{_lease_secs_upd} seconds')")
                    elif status in {"completed", "failed", "cancelled"}:
                        updates.append("completed_at = CURRENT_TIMESTAMP")
                        updates.append("leased_until = NULL")
                        updates.append("lease_owner = NULL")

                    if error_message is not None:
                        updates.append("error_message = ?")
                        params.append(error_message)

                    if result is not None:
                        updates.append("result = ?")
                        params.append(json.dumps(result))

                    params.append(job_id)

                    cursor.execute(
                        f"""
                        UPDATE prompt_studio_job_queue
                        SET {', '.join(updates)}
                        WHERE id = ?
                        """,
                        params,
                    )

                    if cursor.rowcount > 0:
                        conn.commit()
                        cursor.execute(
                            "SELECT * FROM prompt_studio_job_queue WHERE id = ?",
                            (job_id,),
                        )
                        row = cursor.fetchone()
                        return self._row_to_dict(cursor, row) if row else None
                    return None
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < 4:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to update job {job_id}: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to update job {job_id}: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        raise DatabaseError("Failed to update job status due to database locks")

    def acquire_next_job(self, worker_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        import random
        import time

        conn = self.get_connection()
        base_delay = 0.05
        owner_value: Optional[str] = None
        if worker_id:
            try:
                owner_value = str(worker_id).strip()[:128]
                if not owner_value:
                    owner_value = None
            except Exception:
                owner_value = None

        for attempt in range(5):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT id
                        FROM prompt_studio_job_queue
                        WHERE (status = 'queued' OR (status = 'processing' AND (leased_until IS NULL OR leased_until < CURRENT_TIMESTAMP)))
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                        """,
                    )
                    row = cursor.fetchone()
                    if not row:
                        return None
                    job_id = row[0]

                    # Determine lease window from env
                    import os as _os_s1
                    try:
                        _lease_secs_sqlite = max(5, min(3600, int(_os_s1.getenv("TLDW_PS_JOB_LEASE_SECONDS", "60"))))
                    except Exception:
                        _lease_secs_sqlite = 60
                    query = (
                        "UPDATE prompt_studio_job_queue "
                        "SET status = 'processing', "
                        "    started_at = CURRENT_TIMESTAMP, "
                        f"    leased_until = DATETIME('now', '+{_lease_secs_sqlite} seconds'), "
                        "    lease_owner = COALESCE(?, lease_owner) "
                        "WHERE id = ? "
                        "  AND (status = 'queued' OR (status = 'processing' AND (leased_until IS NULL OR leased_until < CURRENT_TIMESTAMP)))"
                    )
                    cursor.execute(query, (owner_value, job_id))

                    if cursor.rowcount > 0:
                        conn.commit()
                        job = self.get_job(job_id)
                        # Record queue latency (started_at - created_at)
                        try:
                            from datetime import datetime
                            if job:
                                created = job.get("created_at")
                                started = job.get("started_at")
                                def _parse(v):
                                    if v is None:
                                        return None
                                    if isinstance(v, datetime):
                                        return v
                                    try:
                                        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
                                    except Exception:
                                        return None
                                cdt = _parse(created)
                                sdt = _parse(started)
                                if cdt and sdt:
                                    qlat = max(0.0, (sdt - cdt).total_seconds())
                                    try:
                                        from tldw_Server_API.app.core.Prompt_Management.prompt_studio.monitoring import prompt_studio_metrics as _psm2
                                        _psm2.metrics_manager.observe(
                                            "jobs.queue_latency_seconds",
                                            qlat,
                                            labels={"job_type": str(job.get("job_type", ""))},
                                        )
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        return job
                    # Lost race to another worker updating this job; retry selection
                    should_retry = True
                    delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < 4:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to acquire job: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to acquire job: {exc}") from exc

            if should_retry:
                try:
                    time.sleep(delay)
                except Exception:
                    time.sleep(0.01)

        raise DatabaseError("Failed to acquire job due to database locks or contention")

    def retry_job_record(self, job_id: int) -> bool:
        import random
        import time

        conn = self.get_connection()
        base_delay = 0.05

        for attempt in range(5):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE prompt_studio_job_queue
                        SET status = 'queued',
                            retry_count = retry_count + 1,
                            error_message = NULL,
                            started_at = NULL,
                            completed_at = NULL,
                            leased_until = NULL,
                            lease_owner = NULL
                        WHERE id = ?
                        """,
                        (job_id,),
                    )
                    success = cursor.rowcount > 0
                    if success:
                        conn.commit()
                        return True
                    # Fallback: if guard matched and row already had identical values, treat as success
                    try:
                        cursor.execute(
                            "SELECT status, lease_owner, leased_until FROM prompt_studio_job_queue WHERE id = ?",
                            (job_id,),
                        )
                        row2 = cursor.fetchone()
                        if row2:
                            st = str(row2[0]) if row2[0] is not None else ""
                            owner = str(row2[1]) if row2[1] is not None else None
                            if st.lower() == "processing" and (owner_value is None or owner == owner_value):
                                return True
                    except Exception:
                        pass
                    return False
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < 4:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to reschedule job {job_id}: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to reschedule job {job_id}: {exc}") from exc

            if should_retry:
                time.sleep(delay)

        return False

    def get_job_stats(self) -> Dict[str, Any]:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            stats: Dict[str, Any] = {}

            cursor.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM prompt_studio_job_queue
                GROUP BY status
                """,
            )
            stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT job_type, COUNT(*) AS count
                FROM prompt_studio_job_queue
                GROUP BY job_type
                """,
            )
            stats["by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT AVG(
                    CAST((julianday(completed_at) - julianday(started_at)) * 24 * 60 * 60 AS INTEGER)
                )
                FROM prompt_studio_job_queue
                WHERE status = 'completed'
                  AND started_at IS NOT NULL
                  AND completed_at IS NOT NULL
                """,
            )
            avg_time = cursor.fetchone()[0]
            stats["avg_processing_time_seconds"] = avg_time if avg_time else 0

            cursor.execute(
                """
                SELECT
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 /
                    COUNT(CASE WHEN status IN ('completed', 'failed') THEN 1 END)
                FROM prompt_studio_job_queue
                WHERE status IN ('completed', 'failed')
                """,
            )
            success_rate = cursor.fetchone()[0]
            stats["success_rate"] = success_rate if success_rate else 0

            stats.setdefault("by_status", {})
            stats["queue_depth"] = stats["by_status"].get("queued", 0)
            stats["processing"] = stats["by_status"].get("processing", 0)
            return stats
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to compute job stats: {exc}") from exc

    def count_jobs(
        self,
        *,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> int:
        """Return count of jobs filtered by optional status and job_type."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM prompt_studio_job_queue WHERE 1=1"
            params: List[Any] = []
            if status:
                query += " AND status = ?"
                params.append(status)
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
            cursor.execute(query, params)
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to count jobs: {exc}") from exc

    def get_lease_stats(self, warn_seconds: int = 30) -> Dict[str, int]:
        """Return basic lease health: active, expiring soon, and stale processing counts."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                warn_seconds = max(1, min(3600, int(warn_seconds)))
            except Exception:
                warn_seconds = 30

            # Active leases: processing with future leased_until
            cursor.execute(
                """
                SELECT COUNT(*) FROM prompt_studio_job_queue
                WHERE status = 'processing' AND leased_until IS NOT NULL AND leased_until > CURRENT_TIMESTAMP
                """,
            )
            active = int(cursor.fetchone()[0])

            # Expiring soon within warn_seconds
            cursor.execute(
                f"""
                SELECT COUNT(*) FROM prompt_studio_job_queue
                WHERE status = 'processing'
                  AND leased_until IS NOT NULL
                  AND leased_until > CURRENT_TIMESTAMP
                  AND leased_until <= DATETIME('now', '+{warn_seconds} seconds')
                """,
            )
            expiring_soon = int(cursor.fetchone()[0])

            # Stale: missing or expired lease
            cursor.execute(
                """
                SELECT COUNT(*) FROM prompt_studio_job_queue
                WHERE status = 'processing'
                  AND (leased_until IS NULL OR leased_until < CURRENT_TIMESTAMP)
                """,
            )
            stale = int(cursor.fetchone()[0])

            return {"active": active, "expiring_soon": expiring_soon, "stale_processing": stale}
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to compute lease stats: {exc}") from exc

    def cleanup_jobs(self, older_than_days: int = 30) -> int:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=older_than_days)).isoformat()
            cursor.execute(
                """
                DELETE FROM prompt_studio_job_queue
                WHERE status IN ('completed', 'failed', 'cancelled')
                  AND completed_at IS NOT NULL
                  AND completed_at < ?
                """,
                (cutoff,),
            )
            deleted = cursor.rowcount
            if deleted:
                conn.commit()
            return deleted
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to clean up old jobs: {exc}") from exc

    def get_latest_job_for_entity(self, job_type: str, entity_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT *
            FROM prompt_studio_job_queue
            WHERE job_type = ? AND entity_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """
        try:
            cursor.execute(query, (job_type, entity_id))
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else None
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(
                f"Failed fetching latest job for entity {entity_id}: {exc}"
            ) from exc

    def list_jobs_for_entity(
        self,
        job_type: str,
        entity_id: int,
        *,
        limit: int = 50,
        ascending: bool = True,
    ) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        order_clause = "ASC" if ascending else "DESC"
        query = (
            f"SELECT * FROM prompt_studio_job_queue "
            f"WHERE job_type = ? AND entity_id = ? "
            f"ORDER BY created_at {order_clause}, id {order_clause} LIMIT ?"
        )
        try:
            cursor.execute(query, (job_type, entity_id, limit))
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows if row]
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(
                f"Failed listing jobs for entity {entity_id}: {exc}"
            ) from exc

    def renew_job_lease(self, job_id: int, seconds: int = 60, worker_id: Optional[str] = None) -> bool:
        import random
        import time
        try:
            seconds = max(5, min(3600, int(seconds)))
        except Exception:
            seconds = 60
        owner_value: Optional[str] = None
        if worker_id:
            try:
                owner_value = str(worker_id).strip()[:128]
                if not owner_value:
                    owner_value = None
            except Exception:
                owner_value = None

        conn = self.get_connection()
        base_delay = 0.05
        for attempt in range(5):
            should_retry = False
            with self._write_lock:
                try:
                    cursor = conn.cursor()
                    set_owner_sql = ", lease_owner = COALESCE(?, lease_owner)" if owner_value is not None else ""
                    owner_guard_sql = " AND (lease_owner IS NULL OR lease_owner = ?)" if owner_value is not None else ""
                    params = (owner_value, job_id, owner_value) if owner_value is not None else (job_id,)
                    cursor.execute(
                        f"""
                        UPDATE prompt_studio_job_queue
                        SET leased_until = DATETIME('now', '+{seconds} seconds'){set_owner_sql}
                        WHERE id = ?
                          AND status = 'processing'
                          {owner_guard_sql}
                        """,
                        params,
                    )
                    success = cursor.rowcount > 0
                    if success:
                        conn.commit()
                    return success
                except sqlite3.OperationalError as exc:
                    if "database is locked" in str(exc).lower() and attempt < 4:
                        should_retry = True
                        delay = base_delay * (2 ** attempt) * (0.5 + random.random())
                    else:
                        raise DatabaseError(f"Failed to renew job lease for {job_id}: {exc}") from exc
                except sqlite3.Error as exc:  # noqa: BLE001
                    raise DatabaseError(f"Failed to renew job lease for {job_id}: {exc}") from exc
            if should_retry:
                time.sleep(delay)
        raise DatabaseError("Failed to renew job lease due to database locks")

    def list_prompts(
        self,
        project_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        import sqlite3

        if page < 1:
            raise InputError("Page index must be >= 1")
        if per_page < 1:
            raise InputError("Items per page must be >= 1")

        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            base_clause = "FROM prompt_studio_prompts WHERE project_id = ?"
            params: List[Any] = [project_id]
            if not include_deleted:
                base_clause += " AND deleted = 0"

            cursor.execute(f"SELECT COUNT(*) {base_clause}", params)
            total_row = cursor.fetchone()
            total = int(total_row[0]) if total_row and total_row[0] is not None else 0

            offset = (page - 1) * per_page
            list_query = (
                f"SELECT * {base_clause} "
                "ORDER BY updated_at DESC, version_number DESC LIMIT ? OFFSET ?"
            )
            cursor.execute(list_query, params + [per_page, offset])
            prompts = [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

            return {
                "prompts": prompts,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to list prompts: {exc}") from exc

    def list_prompt_versions(
        self,
        project_id: int,
        prompt_name: str,
        *,
        include_deleted: bool = False,
    ) -> List[Dict[str, Any]]:
        import sqlite3

        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            deleted_clause = "" if include_deleted else "AND deleted = 0"
            cursor.execute(
                f"""
                SELECT id, uuid, version_number, name, change_description,
                       created_at, parent_version_id
                FROM prompt_studio_prompts
                WHERE project_id = ? AND name = ? {deleted_clause}
                ORDER BY version_number DESC
                """,
                (project_id, prompt_name),
            )
            rows = cursor.fetchall()
            return [self._row_to_dict(cursor, row) for row in rows]
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(
                f"Failed to list prompt versions for project {project_id}: {exc}"
            ) from exc

    def ensure_prompt_stub(
        self,
        *,
        prompt_id: int,
        project_id: int,
        name: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> None:
        import sqlite3

        if not prompt_id or not project_id:
            return

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT 1 FROM prompt_studio_prompts WHERE id = ?",
                (prompt_id,),
            )
            if cursor.fetchone() is not None:
                return
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(
                f"Failed to verify prompt {prompt_id} existence: {exc}"
            ) from exc

        stub_name = name or f"Auto-Created Prompt {prompt_id}"
        try:
            cursor.execute(
                """
                INSERT OR IGNORE INTO prompt_studio_prompts (
                    id, uuid, project_id, version_number, name, client_id
                ) VALUES (?, lower(hex(randomblob(16))), ?, 1, ?, ?)
                """,
                (
                    prompt_id,
                    project_id,
                    stub_name,
                    client_id or self.client_id,
                ),
            )
            conn.commit()
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(
                f"Failed to create placeholder prompt {prompt_id}: {exc}"
            ) from exc

    ####################################################################################################################
    # Test Case Methods

    def create_test_case(
        self,
        project_id: int,
        name: str,
        *,
        inputs: Dict[str, Any],
        description: Optional[str] = None,
        expected_outputs: Optional[Dict[str, Any]] = None,
        actual_outputs: Optional[Dict[str, Any]] = None,
        tags: Optional[Iterable[str]] = None,
        is_golden: bool = False,
        is_generated: bool = False,
        signature_id: Optional[int] = None,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not name or not name.strip():
            raise InputError("Test case name cannot be empty")

        import time

        conn = self.get_connection()
        cursor = conn.cursor()

        # Ensure uniqueness within project for active test cases
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM prompt_studio_test_cases
                WHERE project_id = ? AND name = ? AND deleted = 0
                """,
                (project_id, name.strip()),
            )
            if cursor.fetchone()[0]:
                raise ConflictError(f"Test case with name '{name}' already exists")
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to validate test case uniqueness: {exc}") from exc

        test_case_uuid = str(uuid.uuid4())
        tags_str = _serialise_tags(tags)
        payload = (
            test_case_uuid,
            project_id,
            signature_id,
            name.strip(),
            description,
            json.dumps(inputs),
            json.dumps(expected_outputs) if expected_outputs else None,
            json.dumps(actual_outputs) if actual_outputs else None,
            tags_str,
            bool(is_golden) if self.backend_type == BackendType.POSTGRESQL else int(bool(is_golden)),
            bool(is_generated) if self.backend_type == BackendType.POSTGRESQL else int(bool(is_generated)),
            client_id or self.client_id,
        )

        max_retries = 5
        base_delay = 0.05
        for attempt in range(max_retries):
            try:
                cursor.execute(
                    """
                    INSERT INTO prompt_studio_test_cases (
                        uuid, project_id, signature_id, name, description,
                        inputs, expected_outputs, actual_outputs, tags,
                        is_golden, is_generated, client_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
                test_case_id = cursor.lastrowid
                conn.commit()
                created = self.get_test_case(test_case_id)
                if created:
                    logger.info(
                        "Created test case %s (ID: %s) for project %s",
                        name,
                        test_case_id,
                        project_id,
                    )
                    return created
                break
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "create_test_case locked, retrying in %.3fs (attempt %s/%s)",
                        delay,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(delay)
                    continue
                raise DatabaseError(f"Failed to create test case: {exc}") from exc
            except sqlite3.IntegrityError as exc:  # noqa: BLE001
                raise ConflictError(f"Failed to create test case: {exc}") from exc
            except Exception as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to create test case: {exc}") from exc

        raise DatabaseError("Failed to create test case after multiple retries")

    def get_test_case(self, test_case_id: int, *, include_deleted: bool = False) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM prompt_studio_test_cases WHERE id = ?"
        params: List[Any] = [test_case_id]
        if not include_deleted:
            query += " AND deleted = 0"
        cursor.execute(query, params)
        row = cursor.fetchone()
        return self._format_test_case(cursor, row)

    def list_test_cases(
        self,
        project_id: int,
        *,
        signature_id: Optional[int] = None,
        is_golden: Optional[bool] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        include_deleted: bool = False,
        page: int = 1,
        per_page: int = 20,
        return_pagination: bool = False,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        import time

        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = ["project_id = ?"]
        params: List[Any] = [project_id]

        if not include_deleted:
            conditions.append("deleted = 0")

        if signature_id is not None:
            conditions.append("signature_id = ?")
            params.append(signature_id)

        if is_golden is not None:
            conditions.append("is_golden = ?")
            params.append(bool(is_golden) if self.backend_type == BackendType.POSTGRESQL else int(bool(is_golden)))

        if tags:
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            if tag_conditions:
                conditions.append(f"({' OR '.join(tag_conditions)})")

        where_clause = " WHERE " + " AND ".join(conditions)

        search_clause = ""
        if search:
            search_clause = " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        count_query = f"SELECT COUNT(*) FROM prompt_studio_test_cases{where_clause}{search_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        offset = (page - 1) * per_page
        list_query = f"""
            SELECT * FROM prompt_studio_test_cases
            {where_clause}{search_clause}
            ORDER BY is_golden DESC, created_at DESC
            LIMIT ? OFFSET ?
        """

        # Retry loop mirroring historical behaviour for locked databases
        params_with_pagination = params + [per_page, offset]
        max_retries = 5
        base_delay = 0.05
        for attempt in range(max_retries):
            try:
                cursor.execute(list_query, params_with_pagination)
                break
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                raise DatabaseError(f"Failed to list test cases: {exc}") from exc

        records = [self._format_test_case(cursor, row) for row in cursor.fetchall() if row]

        if return_pagination:
            return {
                "test_cases": records,
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": (total + per_page - 1) // per_page if per_page else 0,
                },
            }
        return records

    def update_test_case(self, test_case_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()

        allowed_fields = {
            "name",
            "description",
            "inputs",
            "expected_outputs",
            "actual_outputs",
            "tags",
            "is_golden",
            "is_generated",
            "signature_id",
        }

        set_clauses: List[str] = []
        params: List[Any] = []

        for field, value in updates.items():
            if field not in allowed_fields:
                continue

            if field in {"inputs", "expected_outputs", "actual_outputs"} and value is not None:
                params.append(json.dumps(value))
            elif field in {"is_golden", "is_generated"} and value is not None:
                params.append(int(bool(value)))
            elif field == "tags":
                params.append(_serialise_tags(value))
            else:
                params.append(value)
            set_clauses.append(f"{field} = ?")

        if not set_clauses:
            existing = self.get_test_case(test_case_id)
            if existing is None:
                raise InputError(f"Test case {test_case_id} not found or already deleted")
            return existing

        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params.append(test_case_id)

        try:
            cursor.execute(
                f"""
                UPDATE prompt_studio_test_cases
                SET {', '.join(set_clauses)}
                WHERE id = ? AND deleted = 0
                """,
                params,
            )
            if cursor.rowcount == 0:
                raise InputError(f"Test case {test_case_id} not found or already deleted")
            conn.commit()
            updated = self.get_test_case(test_case_id)
            if updated is None:
                raise DatabaseError(f"Failed to fetch updated test case {test_case_id}")
            return updated
        except sqlite3.IntegrityError as exc:  # noqa: BLE001
            raise ConflictError(f"Failed to update test case: {exc}") from exc
        except sqlite3.Error as exc:  # noqa: BLE001
            raise DatabaseError(f"Failed to update test case: {exc}") from exc

    def delete_test_case(self, test_case_id: int, *, hard_delete: bool = False) -> bool:
        import time

        conn = self.get_connection()
        cursor = conn.cursor()
        max_retries = 5
        base_delay = 0.05

        for attempt in range(max_retries):
            try:
                if hard_delete:
                    cursor.execute("DELETE FROM prompt_studio_test_cases WHERE id = ?", (test_case_id,))
                else:
                    cursor.execute(
                        """
                        UPDATE prompt_studio_test_cases
                        SET deleted = 1, deleted_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND deleted = 0
                        """,
                        (test_case_id,),
                    )
                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(
                        "%s deleted test case %s",
                        "Hard" if hard_delete else "Soft",
                        test_case_id,
                    )
                    return True
                return False
            except sqlite3.OperationalError as exc:
                if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                raise DatabaseError(f"Failed to delete test case {test_case_id}: {exc}") from exc
            except sqlite3.Error as exc:  # noqa: BLE001
                raise DatabaseError(f"Failed to delete test case {test_case_id}: {exc}") from exc

        return False

    def create_bulk_test_cases(
        self,
        project_id: int,
        test_cases: List[Dict[str, Any]],
        *,
        signature_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        import time

        created: List[Dict[str, Any]] = []
        with self.transaction() as conn:
            cursor = conn.cursor()
            max_retries = 5
            base_delay = 0.05

            for test_case in test_cases:
                test_case_uuid = str(uuid.uuid4())
                tags_str = _serialise_tags(test_case.get("tags"))
                params = (
                    test_case_uuid,
                    project_id,
                    signature_id or test_case.get("signature_id"),
                    test_case.get("name"),
                    test_case.get("description"),
                    json.dumps(test_case.get("inputs", {})),
                    json.dumps(test_case.get("expected_outputs")) if test_case.get("expected_outputs") else None,
                    json.dumps(test_case.get("actual_outputs")) if test_case.get("actual_outputs") else None,
                    tags_str,
                    int(bool(test_case.get("is_golden", False))),
                    int(bool(test_case.get("is_generated", False))),
                    self.client_id,
                )

                for attempt in range(max_retries):
                    try:
                        cursor.execute(
                            """
                            INSERT INTO prompt_studio_test_cases (
                                uuid, project_id, signature_id, name, description,
                                inputs, expected_outputs, actual_outputs, tags,
                                is_golden, is_generated, client_id
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            params,
                        )
                        new_id = cursor.lastrowid
                        created_case = self.get_test_case(new_id)
                        if created_case:
                            created.append(created_case)
                        break
                    except sqlite3.OperationalError as exc:
                        if "database is locked" in str(exc).lower() and attempt < max_retries - 1:
                            time.sleep(base_delay * (2 ** attempt))
                            continue
                        raise DatabaseError(f"Failed to create test case in bulk: {exc}") from exc

        logger.info("Created %s test cases in bulk for project %s", len(created), project_id)
        return created

    def search_test_cases(self, project_id: int, query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tc.*
            FROM prompt_studio_test_cases tc
            JOIN prompt_studio_test_cases_fts ON tc.id = prompt_studio_test_cases_fts.rowid
            WHERE tc.project_id = ?
              AND tc.deleted = 0
              AND prompt_studio_test_cases_fts MATCH ?
            ORDER BY bm25(prompt_studio_test_cases_fts)
            LIMIT ?
            """,
            (project_id, query, limit),
        )
        return [self._format_test_case(cursor, row) for row in cursor.fetchall() if row]

    def get_test_cases_by_signature(self, signature_id: int) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM prompt_studio_test_cases
            WHERE signature_id = ? AND deleted = 0
            ORDER BY is_golden DESC, created_at DESC
            """,
            (signature_id,),
        )
        return [self._format_test_case(cursor, row) for row in cursor.fetchall() if row]

    def get_test_case_stats(self, project_id: int) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        stats: Dict[str, Any] = {}

        cursor.execute(
            "SELECT COUNT(*) FROM prompt_studio_test_cases WHERE project_id = ? AND deleted = 0",
            (project_id,),
        )
        stats["total"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM prompt_studio_test_cases
            WHERE project_id = ? AND deleted = 0 AND is_golden = 1
            """,
            (project_id,),
        )
        stats["golden"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM prompt_studio_test_cases
            WHERE project_id = ? AND deleted = 0 AND is_generated = 1
            """,
            (project_id,),
        )
        stats["generated"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM prompt_studio_test_cases
            WHERE project_id = ? AND deleted = 0 AND expected_outputs IS NOT NULL
            """,
            (project_id,),
        )
        stats["with_expected"] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT signature_id, COUNT(*)
            FROM prompt_studio_test_cases
            WHERE project_id = ? AND deleted = 0 AND signature_id IS NOT NULL
            GROUP BY signature_id
            """,
            (project_id,),
        )
        stats["by_signature"] = {
            row[0]: row[1]
            for row in cursor.fetchall()
            if row and row[0] is not None
        }

        cursor.execute(
            """
            SELECT tags
            FROM prompt_studio_test_cases
            WHERE project_id = ? AND deleted = 0 AND tags IS NOT NULL
            """,
            (project_id,),
        )
        tag_counts: Dict[str, int] = {}
        for row in cursor.fetchall():
            for tag in _parse_tags(row[0]):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        stats["top_tags"] = sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:10]
        return stats

    def renew_job_lease(self, job_id: int, seconds: int = 60, worker_id: Optional[str] = None) -> bool:
        try:
            seconds = max(5, min(3600, int(seconds)))
        except Exception:
            seconds = 60
        owner_value: Optional[str] = None
        if worker_id:
            try:
                owner_value = str(worker_id).strip()[:128]
                if not owner_value:
                    owner_value = None
            except Exception:
                owner_value = None
        set_owner_sql = ", lease_owner = COALESCE(%s, lease_owner)"
        owner_guard_sql = ""
        params: List[Any] = [owner_value, job_id]
        if owner_value is not None:
            owner_guard_sql = " AND (lease_owner IS NULL OR lease_owner = %s)"
            params.append(owner_value)
        try:
            with self.transaction() as conn:
                cursor = self._cursor_exec(
                    conn,
                    f"""
                    UPDATE prompt_studio_job_queue
                    SET leased_until = NOW() + INTERVAL '{seconds} seconds'
                        {set_owner_sql}
                    WHERE id = %s AND status = 'processing'
                      {owner_guard_sql}
                    RETURNING id
                    """,
                    tuple(params),
                )
                row = cursor.fetchone()
                return bool(row)
        except BackendDatabaseError as exc:
            raise DatabaseError(f"Failed to renew job lease for {job_id}: {exc}") from exc

    def get_golden_test_cases(self, project_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM prompt_studio_test_cases
            WHERE project_id = ? AND is_golden = 1 AND deleted = 0
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (project_id, limit, offset),
        )
        return [self._format_test_case(cursor, row) for row in cursor.fetchall() if row]

    ####################################################################################################################
    # Transaction Management

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions.
        Ensures atomic operations with automatic rollback on error.
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    ####################################################################################################################
    # Optimization helpers (SQLite)

    def create_optimization(
        self,
        *,
        project_id: int,
        name: Optional[str],
        initial_prompt_id: Optional[int],
        optimizer_type: str,
        optimization_config: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        bootstrap_samples: Optional[int] = None,
        status: str = "pending",
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        optimization_uuid = str(uuid.uuid4())
        payload = (
            optimization_uuid,
            project_id,
            name,
            initial_prompt_id,
            None,  # optimized_prompt_id
            optimizer_type,
            json.dumps(optimization_config) if optimization_config is not None else None,
            None,
            None,
            None,
            0,
            max_iterations,
            bootstrap_samples,
            status,
            None,
            None,
            None,
            client_id or self.client_id,
        )

        insert_sql = """
            INSERT INTO prompt_studio_optimizations (
                uuid, project_id, name, initial_prompt_id, optimized_prompt_id,
                optimizer_type, optimization_config, initial_metrics, final_metrics,
                improvement_percentage, iterations_completed, max_iterations,
                bootstrap_samples, status, error_message, total_tokens, total_cost,
                client_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
        """

        try:
            with self._write_lock:
                with self.transaction() as conn:
                    cursor = self._cursor_exec(conn, insert_sql, payload)
                    row = cursor.fetchone()
            return self._row_to_dict(cursor, row) if row else {}
        except Exception as exc:
            raise DatabaseError(f"Failed to create prompt studio optimization: {exc}") from exc


class PromptStudioDatabase:
    """Factory wrapper that selects SQLite or backend-aware implementations."""

    def __init__(
        self,
        db_path: Union[str, Path],
        client_id: str,
        *,
        backend: Optional[DatabaseBackend] = None,
        config: Optional[ConfigParser] = None,
    ) -> None:
        backend_type = backend.backend_type if backend else BackendType.SQLITE
        if backend_type == BackendType.POSTGRESQL and backend is not None:
            self._impl = _BackendPromptStudioDatabase(
                db_path,
                client_id,
                backend=backend,
                config=config,
            )
        else:
            self._impl = _SQLitePromptStudioDatabase(str(db_path), client_id)

    def __getattr__(self, item):
        return getattr(self._impl, item)

    def __dir__(self):
        return sorted(set(dir(type(self)) + dir(self._impl)))

    def __repr__(self) -> str:  # pragma: no cover - repr helper
        return f"PromptStudioDatabase<{self._impl!r}>"

    @property
    def backend_type(self) -> BackendType:
        return getattr(self._impl, 'backend_type', BackendType.SQLITE)

    @property
    def backend(self) -> Optional[DatabaseBackend]:
        return getattr(self._impl, 'backend', None)

    # Idempotency helpers (public facade)
    def lookup_idempotency(self, entity_type: str, key: str, user_id: Optional[str]) -> Optional[int]:
        if hasattr(self._impl, '_idem_lookup'):
            return self._impl._idem_lookup(entity_type, key, user_id)  # type: ignore[attr-defined]
        return None

    def record_idempotency(self, entity_type: str, key: str, entity_id: int, user_id: Optional[str]) -> None:
        if hasattr(self._impl, '_idem_record'):
            try:
                self._impl._idem_record(entity_type, key, entity_id, user_id)  # type: ignore[attr-defined]
            except Exception:
                pass

    def update_project(self, project_id: int, updates: Optional[Dict[str, Any]] = None, **fields: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if updates:
            payload.update(updates)
        if fields:
            payload.update(fields)
        return self._impl.update_project(project_id, payload)

    # Signature delegation ------------------------------------------------

    def create_signature(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.create_signature(*args, **kwargs)

    def get_signature(self, *args: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return self._impl.get_signature(*args, **kwargs)

    def list_signatures(self, *args: Any, **kwargs: Any) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        return self._impl.list_signatures(*args, **kwargs)

    def update_signature(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.update_signature(*args, **kwargs)

    def delete_signature(self, *args: Any, **kwargs: Any) -> bool:
        return self._impl.delete_signature(*args, **kwargs)

    def create_prompt(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.create_prompt(*args, **kwargs)

    def ensure_prompt_stub(self, *args: Any, **kwargs: Any) -> None:
        return self._impl.ensure_prompt_stub(*args, **kwargs)

    # Job queue delegation -------------------------------------------------

    def create_job(
        self,
        job_type: str,
        entity_id: int,
        payload: Optional[Any],
        *,
        project_id: Optional[int] = None,
        priority: int = 5,
        status: str = "queued",
        max_retries: int = 3,
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._impl.create_job(
            job_type,
            entity_id,
            payload,
            project_id=project_id,
            priority=priority,
            status=status,
            max_retries=max_retries,
            client_id=client_id,
        )

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        return self._impl.get_job(job_id)

    def get_job_by_uuid(self, job_uuid: str) -> Optional[Dict[str, Any]]:
        return self._impl.get_job_by_uuid(job_uuid)

    def list_jobs(
        self,
        *,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        return self._impl.list_jobs(status=status, job_type=job_type, limit=limit)

    def update_job_status(
        self,
        job_id: int,
        status: str,
        *,
        error_message: Optional[str] = None,
        result: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._impl.update_job_status(
            job_id,
            status,
            error_message=error_message,
            result=result,
        )

    def acquire_next_job(self, *, worker_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        return self._impl.acquire_next_job(worker_id=worker_id)

    def retry_job_record(self, job_id: int) -> bool:
        return self._impl.retry_job_record(job_id)

    # Optional: renew job lease
    def renew_job_lease(self, job_id: int, seconds: int = 60, *, worker_id: Optional[str] = None) -> bool:
        if hasattr(self._impl, 'renew_job_lease'):
            try:
                return bool(self._impl.renew_job_lease(job_id, seconds, worker_id=worker_id))  # type: ignore[attr-defined]
            except Exception:
                return False
        return False

    def get_job_stats(self) -> Dict[str, Any]:
        return self._impl.get_job_stats()

    def cleanup_jobs(self, older_than_days: int = 30) -> int:
        return self._impl.cleanup_jobs(older_than_days)

    def get_latest_job_for_entity(self, *args: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return self._impl.get_latest_job_for_entity(*args, **kwargs)

    def list_jobs_for_entity(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._impl.list_jobs_for_entity(*args, **kwargs)
    def get_lease_stats(self, warn_seconds: int = 30) -> Dict[str, int]:
        return self._impl.get_lease_stats(warn_seconds)

    # Job counters --------------------------------------------------------
    def count_jobs(
        self,
        *,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> int:
        return self._impl.count_jobs(status=status, job_type=job_type)

    # Test case delegation -------------------------------------------------

    def create_test_case(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.create_test_case(*args, **kwargs)

    def get_test_case(self, *args: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return self._impl.get_test_case(*args, **kwargs)

    def list_test_cases(self, *args: Any, **kwargs: Any) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        return self._impl.list_test_cases(*args, **kwargs)

    def update_test_case(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.update_test_case(*args, **kwargs)

    def delete_test_case(self, *args: Any, **kwargs: Any) -> bool:
        return self._impl.delete_test_case(*args, **kwargs)

    def create_bulk_test_cases(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._impl.create_bulk_test_cases(*args, **kwargs)

    def search_test_cases(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._impl.search_test_cases(*args, **kwargs)

    def get_test_cases_by_signature(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._impl.get_test_cases_by_signature(*args, **kwargs)

    def get_test_case_stats(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.get_test_case_stats(*args, **kwargs)

    def get_golden_test_cases(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._impl.get_golden_test_cases(*args, **kwargs)

    # Test run delegation -------------------------------------------------

    def create_test_run(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.create_test_run(*args, **kwargs)

    def get_test_cases_by_ids(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        return self._impl.get_test_cases_by_ids(*args, **kwargs)

    # Evaluation delegation -----------------------------------------------

    def create_evaluation(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.create_evaluation(*args, **kwargs)

    def update_evaluation(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.update_evaluation(*args, **kwargs)

    def get_evaluation(self, *args: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return self._impl.get_evaluation(*args, **kwargs)

    def list_evaluations(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.list_evaluations(*args, **kwargs)

    # Optimization delegation --------------------------------------------

    def create_optimization(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.create_optimization(*args, **kwargs)

    def get_optimization(self, *args: Any, **kwargs: Any) -> Optional[Dict[str, Any]]:
        return self._impl.get_optimization(*args, **kwargs)

    def list_optimizations(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.list_optimizations(*args, **kwargs)

    def update_optimization(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.update_optimization(*args, **kwargs)

    def set_optimization_status(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.set_optimization_status(*args, **kwargs)

    def complete_optimization(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.complete_optimization(*args, **kwargs)

    def record_optimization_iteration(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.record_optimization_iteration(*args, **kwargs)

    def list_optimization_iterations(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return self._impl.list_optimization_iterations(*args, **kwargs)
