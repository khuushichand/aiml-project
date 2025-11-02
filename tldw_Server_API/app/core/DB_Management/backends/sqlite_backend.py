"""
SQLite backend implementation for the database abstraction layer.

This module provides a concrete implementation of the DatabaseBackend
interface for SQLite databases, maintaining compatibility with the
existing codebase while enabling multi-backend support.
"""

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Generator
import json
from loguru import logger as _loguru_logger
from queue import Queue, Empty

from .base import (
    DatabaseBackend,
    DatabaseConfig,
    BackendType,
    BackendFeatures,
    ConnectionPool,
    QueryResult,
    FTSQuery,
    DatabaseError,
    NotSupportedError
)

logger = _loguru_logger


class SQLiteConnectionPool(ConnectionPool):
    """SQLite-specific connection pool using thread-local storage."""

    def __init__(self, db_path: str, config: DatabaseConfig):
        """
        Initialize SQLite connection pool.

        Args:
            db_path: Path to SQLite database file
            config: Database configuration
        """
        # Normalize to absolute path to avoid CWD-related open errors under tests
        # Detect in-memory databases and avoid path resolution
        self._is_memory = db_path == ':memory:'
        try:
            self.db_path = db_path if self._is_memory else str(Path(db_path).resolve())
        except Exception:
            self.db_path = db_path
        self.config = config
        self._local = threading.local()
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._lock = threading.RLock()
        self._closed = False

    def get_connection(self) -> sqlite3.Connection:
        """Get a thread-local connection."""
        thread_id = threading.get_ident()

        # Check if we have a connection for this thread
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            with self._lock:
                if thread_id not in self._connections or self._connections[thread_id] is None:
                    conn = self._create_connection()
                    self._connections[thread_id] = conn
                    self._local.connection = conn
                else:
                    self._local.connection = self._connections[thread_id]

        return self._local.connection

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection with optimal settings."""
        # Ensure database directory exists for file-backed DBs
        if not self._is_memory:
            try:
                dbp = Path(self.db_path)
                if dbp.parent and not dbp.parent.exists():
                    dbp.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None  # Autocommit mode
        )

        # Set row factory for dict-like access
        conn.row_factory = sqlite3.Row

        # Apply optimizations
        if self.config.sqlite_wal_mode and not self._is_memory:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")

        if self.config.sqlite_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")

        # Reduce lock contention under concurrent access (increase to 10s)
        conn.execute("PRAGMA busy_timeout = 10000")

        # Additional optimizations
        conn.execute("PRAGMA cache_size = -2000")  # 2MB cache
        conn.execute("PRAGMA temp_store = MEMORY")

        return conn

    def return_connection(self, connection: sqlite3.Connection) -> None:
        """SQLite connections are thread-local, no action needed."""
        pass

    def clear_thread_local_connection(self) -> None:
        """Clear the current thread's connection reference from the pool.

        This provides a safe way for higher layers to invalidate a broken
        connection without reaching into private attributes.
        """
        thread_id = threading.get_ident()
        with self._lock:
            try:
                self._connections[thread_id] = None
            except Exception:
                pass
            try:
                if hasattr(self._local, 'connection'):
                    self._local.connection = None
            except Exception:
                pass
            # Prune stale entries to avoid unbounded growth
            try:
                stale_keys = [tid for tid, conn in self._connections.items() if conn is None]
                for tid in stale_keys:
                    self._connections.pop(tid, None)
            except Exception:
                pass

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for connection handling."""
        conn = self.get_connection()
        try:
            yield conn
        except Exception as e:
            logger.error(f"Error in connection context: {e}")
            raise

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            self._closed = True
            for conn in self._connections.values():
                if conn:
                    try:
                        conn.close()
                    except Exception as e:
                        logger.error(f"Error closing connection: {e}")
            self._connections.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            active = len([c for c in self._connections.values() if c])
            # Keep "active_threads" for backward compatibility; prefer "active_connections"
            return {
                "total_connections": len(self._connections),
                "active_connections": active,
                "active_threads": active,  # deprecated alias
                "closed": self._closed,
                "db_path": self.db_path,
            }


class SQLiteBackend(DatabaseBackend):
    """SQLite implementation of the database backend."""

    @property
    def backend_type(self) -> BackendType:
        """Get the backend type."""
        return BackendType.SQLITE

    def _get_features(self) -> BackendFeatures:
        """Get SQLite feature support."""
        return BackendFeatures(
            full_text_search=True,  # FTS5
            json_support=True,       # JSON1 extension
            array_support=False,     # No native arrays
            window_functions=True,   # Since 3.25.0
            cte_support=True,        # Common Table Expressions
            partial_indexes=True,    # Since 3.8.0
            generated_columns=True,  # Since 3.31.0
            upsert_support=True,     # INSERT OR REPLACE
            returning_clause=True,   # Since 3.35.0
            listen_notify=False      # No LISTEN/NOTIFY
        )

    def connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection."""
        if not self.config.sqlite_path:
            raise DatabaseError("SQLite path not configured")
        # Handle in-memory DB distinctly
        is_memory = self.config.sqlite_path == ':memory:'

        # Ensure database directory exists for file-backed DBs
        if not is_memory:
            db_path = Path(self.config.sqlite_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            self.config.sqlite_path if is_memory else str(db_path),
            check_same_thread=False,
            isolation_level=None
        )

        conn.row_factory = sqlite3.Row

        # Apply configuration
        if self.config.sqlite_wal_mode and not is_memory:
            conn.execute("PRAGMA journal_mode = WAL")

        if self.config.sqlite_foreign_keys:
            conn.execute("PRAGMA foreign_keys = ON")

        # Reduce lock contention under concurrent access (increase to 10s)
        conn.execute("PRAGMA busy_timeout = 10000")

        return conn

    def disconnect(self, connection: sqlite3.Connection) -> None:
        """Close a SQLite connection."""
        if connection:
            connection.close()

    @contextmanager
    def transaction(self, connection: Optional[sqlite3.Connection] = None) -> Generator[sqlite3.Connection, None, None]:
        """SQLite transaction context manager.

        Uses explicit BEGIN/COMMIT/ROLLBACK and guards with in_transaction to
        avoid errors when statements (e.g., executescript) implicitly end a txn.
        """
        if connection:
            conn = connection
        else:
            conn = self.get_pool().get_connection()

        try:
            if not getattr(conn, "in_transaction", False):
                conn.execute("BEGIN")
            yield conn
            if getattr(conn, "in_transaction", False):
                conn.execute("COMMIT")
        except Exception as e:
            if getattr(conn, "in_transaction", False):
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.OperationalError:
                    # Best effort; ignore if no active transaction
                    pass
            logger.error(f"Transaction failed: {e}")
            raise

    def get_pool(self) -> ConnectionPool:
        """Get or create the connection pool."""
        if self._pool is None:
            if not self.config.sqlite_path:
                raise DatabaseError("SQLite path not configured")
            self._pool = SQLiteConnectionPool(self.config.sqlite_path, self.config)
        return self._pool

    def execute(
        self,
        query: str,
        params: Optional[Union[Tuple, Dict]] = None,
        connection: Optional[sqlite3.Connection] = None
    ) -> QueryResult:
        """Execute a query and return results."""
        start_time = time.time()

        if connection:
            conn = connection
        else:
            conn = self.get_pool().get_connection()

        try:
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Determine whether to fetch rows: SELECT or statements with RETURNING
            upper = query.strip().upper()
            is_select = upper.startswith("SELECT")
            has_returning = " RETURNING " in upper
            if is_select or has_returning:
                rows = cursor.fetchall()
                result_rows = [dict(row) for row in rows]
            else:
                result_rows = []

            execution_time = time.time() - start_time

            return QueryResult(
                rows=result_rows,
                rowcount=cursor.rowcount,
                lastrowid=cursor.lastrowid,
                description=cursor.description,
                execution_time=execution_time
            )

        except sqlite3.Error as e:
            logger.error(f"Query execution failed: {e}")
            raise DatabaseError(f"SQLite error: {e}")

    def execute_many(
        self,
        query: str,
        params_list: List[Union[Tuple, Dict]],
        connection: Optional[sqlite3.Connection] = None
    ) -> QueryResult:
        """Execute a query multiple times with different parameters."""
        start_time = time.time()

        if connection:
            conn = connection
        else:
            conn = self.get_pool().get_connection()

        try:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)

            execution_time = time.time() - start_time

            return QueryResult(
                rows=[],
                rowcount=cursor.rowcount,
                lastrowid=cursor.lastrowid,
                description=cursor.description,
                execution_time=execution_time
            )

        except sqlite3.Error as e:
            logger.error(f"Batch execution failed: {e}")
            raise DatabaseError(f"SQLite error: {e}")

    def create_tables(self, schema: str, connection: Optional[sqlite3.Connection] = None) -> None:
        """Create tables from a schema definition."""
        if connection:
            conn = connection
        else:
            conn = self.get_pool().get_connection()

        try:
            # Execute the schema as a script
            conn.executescript(schema)
        except sqlite3.Error as e:
            logger.error(f"Schema creation failed: {e}")
            raise DatabaseError(f"Failed to create schema: {e}")

    def table_exists(self, table_name: str, connection: Optional[sqlite3.Connection] = None) -> bool:
        """Check if a table exists."""
        query = """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name=?
        """
        result = self.execute(query, (table_name,), connection)
        return len(result.rows) > 0

    def get_table_info(
        self,
        table_name: str,
        connection: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        """Get information about a table's columns."""
        query = f"PRAGMA table_info({self.escape_identifier(table_name)})"
        result = self.execute(query, connection=connection)

        # Convert to standard format
        columns = []
        for row in result.rows:
            columns.append({
                "name": row["name"],
                "type": row["type"],
                "nullable": not row["notnull"],
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"])
            })

        return columns

    def create_fts_table(
        self,
        table_name: str,
        source_table: str,
        columns: List[str],
        connection: Optional[sqlite3.Connection] = None
    ) -> None:
        """Create a FTS5 virtual table."""
        self.features.require("full_text_search")

        # Build FTS5 table creation query
        columns_str = ", ".join([self.escape_identifier(c) for c in columns])
        query = f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {self.escape_identifier(table_name)}
            USING fts5({columns_str}, content='{source_table}')
        """

        try:
            self.execute(query, connection=connection)

            # Populate FTS table with existing data
            columns_select = ", ".join([self.escape_identifier(col) for col in columns])
            populate_query = f"""
                INSERT INTO {self.escape_identifier(table_name)} (rowid, {columns_str})
                SELECT rowid, {columns_select} FROM {self.escape_identifier(source_table)}
            """
            self.execute(populate_query, connection=connection)

        except sqlite3.Error as e:
            logger.error(f"FTS table creation failed: {e}")
            raise DatabaseError(f"Failed to create FTS table: {e}")

    def fts_search(
        self,
        fts_query: FTSQuery,
        connection: Optional[sqlite3.Connection] = None
    ) -> QueryResult:
        """Perform a FTS5 search."""
        self.features.require("full_text_search")

        if not fts_query.table:
            raise DatabaseError("FTS table name required")

        # Build the FTS query
        query_parts = [f"SELECT * FROM {self.escape_identifier(fts_query.table)}"]
        params = []

        # Add MATCH clause
        query_parts.append(f"WHERE {self.escape_identifier(fts_query.table)} MATCH ?")
        params.append(fts_query.query_text)

        # Add additional filters
        for key, value in fts_query.filters.items():
            query_parts.append(f"AND {self.escape_identifier(key)} = ?")
            params.append(value)

        # Add ORDER BY using bm25() by default for better relevance
        if fts_query.rank_expression:
            query_parts.append(f"ORDER BY {fts_query.rank_expression}")
        else:
            # bm25 returns lower scores for more relevant rows; sort ASC
            # Use bare table name (consistent with project queries elsewhere)
            query_parts.append(f"ORDER BY bm25({fts_query.table}) ASC")

        # Add LIMIT/OFFSET
        if fts_query.limit:
            query_parts.append(f"LIMIT {fts_query.limit}")
        if fts_query.offset:
            query_parts.append(f"OFFSET {fts_query.offset}")

        query = " ".join(query_parts)

        return self.execute(query, tuple(params), connection)

    def update_fts_index(
        self,
        table_name: str,
        connection: Optional[sqlite3.Connection] = None
    ) -> None:
        """Update the FTS5 index (rebuild if needed)."""
        query = f"INSERT INTO {self.escape_identifier(table_name)}({self.escape_identifier(table_name)}) VALUES('rebuild')"
        self.execute(query, connection=connection)

    def escape_identifier(self, identifier: str) -> str:
        """Escape a SQLite identifier."""
        # SQLite uses double quotes for identifiers
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def get_last_insert_id(self, connection: Optional[sqlite3.Connection] = None) -> Optional[int]:
        """Get the last inserted row ID."""
        result = self.execute("SELECT last_insert_rowid()", connection=connection)
        return result.scalar

    def vacuum(self, connection: Optional[sqlite3.Connection] = None) -> None:
        """Vacuum the SQLite database."""
        self.execute("VACUUM", connection=connection)

    def get_database_size(self, connection: Optional[sqlite3.Connection] = None) -> int:
        """Get the database size in bytes."""
        if not self.config.sqlite_path:
            return 0

        db_path = Path(self.config.sqlite_path)
        if db_path.exists():
            return db_path.stat().st_size
        return 0

    def export_schema(self, connection: Optional[sqlite3.Connection] = None) -> str:
        """Export the database schema as SQL."""
        query = """
            SELECT sql FROM sqlite_master
            WHERE type IN ('table', 'index', 'trigger', 'view')
            AND sql IS NOT NULL
            ORDER BY type, name
        """
        result = self.execute(query, connection=connection)

        schema_parts = []
        for row in result.rows:
            if row["sql"]:
                schema_parts.append(row["sql"] + ";")

        return "\n\n".join(schema_parts)

    def export_data(
        self,
        table_name: str,
        connection: Optional[sqlite3.Connection] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Export data from a table."""
        query = f"SELECT * FROM {self.escape_identifier(table_name)}"

        if connection:
            conn = connection
        else:
            conn = self.get_pool().get_connection()

        cursor = conn.cursor()
        cursor.execute(query)

        # Get column names
        columns = [desc[0] for desc in cursor.description]

        # Yield rows as dictionaries
        for row in cursor:
            yield dict(zip(columns, row))

    def import_data(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        connection: Optional[sqlite3.Connection] = None
    ) -> int:
        """Import data into a table."""
        if not data:
            return 0

        # Get column names from first row
        columns = list(data[0].keys())
        columns_str = ", ".join([self.escape_identifier(col) for col in columns])
        placeholders = ", ".join(["?" for _ in columns])

        query = f"""
            INSERT OR REPLACE INTO {self.escape_identifier(table_name)} ({columns_str})
            VALUES ({placeholders})
        """

        # Convert dicts to tuples
        params_list = [tuple(row.get(col) for col in columns) for row in data]

        result = self.execute_many(query, params_list, connection)
        return result.rowcount
