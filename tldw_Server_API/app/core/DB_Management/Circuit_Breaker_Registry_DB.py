"""Persistent shared storage for unified circuit breaker registry state."""

from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from tldw_Server_API.app.core.DB_Management.sqlite_policy import configure_sqlite_connection

_SCHEMA_VERSION = 2


class CircuitBreakerOptimisticLockError(RuntimeError):
    """Raised when a breaker row update fails optimistic locking checks."""

    def __init__(self, name: str, *, expected_version: int, current_version: int | None):
        super().__init__(
            f"Circuit breaker '{name}' version mismatch (expected {expected_version}, "
            f"current {current_version})"
        )
        self.name = name
        self.expected_version = expected_version
        self.current_version = current_version


@dataclass(frozen=True)
class CircuitBreakerStoredState:
    """Serialized circuit breaker state persisted in shared storage."""

    state: int
    failure_count: int
    success_count: int
    last_failure_time: float | None
    last_state_change_time: float
    half_open_calls: int
    current_recovery_timeout: float
    last_trip_failure_count: int


@dataclass(frozen=True)
class CircuitBreakerProbeLease:
    """Contract shape for distributed HALF_OPEN probe leases (stage 3 target)."""

    name: str
    lease_id: str
    owner_id: str
    acquired_at: float
    expires_at: float


class CircuitBreakerRegistryDB:
    """SQLite-backed shared store for circuit breaker state snapshots."""

    def __init__(self, db_path: str | Path | None = None):
        path = Path(db_path) if db_path is not None else self._resolve_default_db_path()
        self.db_path = path.expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_schema()

    @staticmethod
    def _resolve_default_db_path() -> Path:
        raw = os.getenv("CIRCUIT_BREAKER_REGISTRY_DB_PATH")
        if raw:
            return Path(str(raw)).expanduser()

        try:
            from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

            return DatabasePaths.get_shared_circuit_breaker_db_path()
        except Exception:
            repo_root = Path(__file__).resolve().parents[4]
            return repo_root / "Databases" / "circuit_breaker_registry.db"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        configure_sqlite_connection(conn)
        return conn

    def _initialize_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS circuit_breaker_registry_schema_version ("
                    "id INTEGER PRIMARY KEY CHECK (id = 1), "
                    "version INTEGER NOT NULL)"
                )
                row = conn.execute(
                    "SELECT version FROM circuit_breaker_registry_schema_version WHERE id = 1"
                ).fetchone()
                if row is None:
                    conn.execute(
                        "INSERT INTO circuit_breaker_registry_schema_version (id, version) VALUES (1, ?)",
                        (_SCHEMA_VERSION,),
                    )
                else:
                    current_version = int(row["version"] or 0)
                    if current_version < _SCHEMA_VERSION:
                        conn.execute(
                            "UPDATE circuit_breaker_registry_schema_version SET version = ? WHERE id = 1",
                            (_SCHEMA_VERSION,),
                        )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS circuit_breaker_registry (
                        name TEXT PRIMARY KEY,
                        state INTEGER NOT NULL,
                        failure_count INTEGER NOT NULL,
                        success_count INTEGER NOT NULL,
                        last_failure_time REAL,
                        last_state_change_time REAL NOT NULL,
                        half_open_calls INTEGER NOT NULL,
                        current_recovery_timeout REAL NOT NULL,
                        last_trip_failure_count INTEGER NOT NULL,
                        version INTEGER NOT NULL,
                        updated_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cb_registry_updated_at "
                    "ON circuit_breaker_registry(updated_at)"
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS circuit_breaker_probe_leases (
                        lease_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        owner_id TEXT NOT NULL,
                        acquired_at REAL NOT NULL,
                        expires_at REAL NOT NULL
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_cb_probe_leases_name_expires "
                    "ON circuit_breaker_probe_leases(name, expires_at)"
                )

    @staticmethod
    def _row_to_state(row: sqlite3.Row) -> tuple[CircuitBreakerStoredState, int]:
        return (
            CircuitBreakerStoredState(
                state=int(row["state"]),
                failure_count=int(row["failure_count"]),
                success_count=int(row["success_count"]),
                last_failure_time=(
                    None if row["last_failure_time"] is None else float(row["last_failure_time"])
                ),
                last_state_change_time=float(row["last_state_change_time"]),
                half_open_calls=int(row["half_open_calls"]),
                current_recovery_timeout=float(row["current_recovery_timeout"]),
                last_trip_failure_count=int(row["last_trip_failure_count"]),
            ),
            int(row["version"]),
        )

    def load(self, name: str) -> tuple[CircuitBreakerStoredState, int] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT state, failure_count, success_count, last_failure_time, "
                    "last_state_change_time, half_open_calls, current_recovery_timeout, "
                    "last_trip_failure_count, version "
                    "FROM circuit_breaker_registry WHERE name = ?",
                    (name,),
                ).fetchone()
                if row is None:
                    return None
                return self._row_to_state(row)

    def load_all(self) -> dict[str, tuple[CircuitBreakerStoredState, int]]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT name, state, failure_count, success_count, last_failure_time, "
                    "last_state_change_time, half_open_calls, current_recovery_timeout, "
                    "last_trip_failure_count, version "
                    "FROM circuit_breaker_registry"
                ).fetchall()
                return {
                    str(row["name"]): self._row_to_state(row)
                    for row in rows
                }

    def upsert(
        self,
        name: str,
        state: CircuitBreakerStoredState,
        *,
        expected_version: int,
    ) -> int:
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                if expected_version <= 0:
                    cursor = conn.execute(
                        "INSERT OR IGNORE INTO circuit_breaker_registry ("
                        "name, state, failure_count, success_count, last_failure_time, "
                        "last_state_change_time, half_open_calls, current_recovery_timeout, "
                        "last_trip_failure_count, version, updated_at"
                        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                        (
                            name,
                            int(state.state),
                            int(state.failure_count),
                            int(state.success_count),
                            state.last_failure_time,
                            float(state.last_state_change_time),
                            int(state.half_open_calls),
                            float(state.current_recovery_timeout),
                            int(state.last_trip_failure_count),
                            now,
                        ),
                    )
                    if cursor.rowcount and cursor.rowcount > 0:
                        return 1

                cursor = conn.execute(
                    "UPDATE circuit_breaker_registry SET "
                    "state = ?, "
                    "failure_count = ?, "
                    "success_count = ?, "
                    "last_failure_time = ?, "
                    "last_state_change_time = ?, "
                    "half_open_calls = ?, "
                    "current_recovery_timeout = ?, "
                    "last_trip_failure_count = ?, "
                    "version = version + 1, "
                    "updated_at = ? "
                    "WHERE name = ? AND version = ?",
                    (
                        int(state.state),
                        int(state.failure_count),
                        int(state.success_count),
                        state.last_failure_time,
                        float(state.last_state_change_time),
                        int(state.half_open_calls),
                        float(state.current_recovery_timeout),
                        int(state.last_trip_failure_count),
                        now,
                        name,
                        int(expected_version),
                    ),
                )
                if cursor.rowcount and cursor.rowcount > 0:
                    return int(expected_version) + 1

                row = conn.execute(
                    "SELECT version FROM circuit_breaker_registry WHERE name = ?",
                    (name,),
                ).fetchone()
                current_version = None if row is None else int(row["version"])
                raise CircuitBreakerOptimisticLockError(
                    name,
                    expected_version=expected_version,
                    current_version=current_version,
                )

    def delete(self, name: str) -> bool:
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM circuit_breaker_registry WHERE name = ?",
                    (name,),
                )
                conn.execute(
                    "DELETE FROM circuit_breaker_probe_leases WHERE name = ?",
                    (name,),
                )
                return bool(cursor.rowcount and cursor.rowcount > 0)

    def clear(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM circuit_breaker_registry")
                conn.execute("DELETE FROM circuit_breaker_probe_leases")

    # ------------------------------------------------------------------
    # Distributed HALF_OPEN lease contract (stage 3 implementation target)
    # ------------------------------------------------------------------

    def acquire_probe_lease(
        self,
        name: str,
        *,
        max_calls: int,
        ttl_seconds: float,
        owner_id: str,
    ) -> CircuitBreakerProbeLease | None:
        """Acquire a distributed HALF_OPEN probe lease.

        Returns a lease when active, non-expired leases are below ``max_calls``.
        Returns ``None`` when no slot is available.
        """
        safe_max_calls = max(1, int(max_calls))
        ttl = max(0.001, float(ttl_seconds))
        now = time.time()
        expires_at = now + ttl
        lease_id = uuid.uuid4().hex

        with self._lock:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute(
                        "DELETE FROM circuit_breaker_probe_leases "
                        "WHERE name = ? AND expires_at <= ?",
                        (name, now),
                    )
                    row = conn.execute(
                        "SELECT COUNT(1) AS active "
                        "FROM circuit_breaker_probe_leases "
                        "WHERE name = ? AND expires_at > ?",
                        (name, now),
                    ).fetchone()
                    active = int(row["active"] if row is not None else 0)
                    if active >= safe_max_calls:
                        conn.execute("COMMIT")
                        return None

                    conn.execute(
                        "INSERT INTO circuit_breaker_probe_leases ("
                        "lease_id, name, owner_id, acquired_at, expires_at"
                        ") VALUES (?, ?, ?, ?, ?)",
                        (lease_id, name, owner_id, now, expires_at),
                    )
                    conn.execute("COMMIT")
                except Exception:
                    with contextlib.suppress(Exception):
                        conn.execute("ROLLBACK")
                    raise

        return CircuitBreakerProbeLease(
            name=name,
            lease_id=lease_id,
            owner_id=owner_id,
            acquired_at=now,
            expires_at=expires_at,
        )

    def release_probe_lease(self, name: str, lease_id: str) -> bool:
        """Release a previously acquired probe lease."""
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM circuit_breaker_probe_leases "
                    "WHERE name = ? AND lease_id = ?",
                    (name, lease_id),
                )
                return bool(cursor.rowcount and cursor.rowcount > 0)

    def cleanup_expired_probe_leases(self, name: str) -> int:
        """Delete expired probe leases for *name* and return deleted-row count."""
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM circuit_breaker_probe_leases "
                    "WHERE name = ? AND expires_at <= ?",
                    (name, time.time()),
                )
                return int(cursor.rowcount or 0)

    def count_active_probe_leases(self, name: str) -> int:
        """Return number of non-expired probe leases for *name*."""
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM circuit_breaker_probe_leases "
                    "WHERE name = ? AND expires_at <= ?",
                    (name, now),
                )
                row = conn.execute(
                    "SELECT COUNT(1) AS active "
                    "FROM circuit_breaker_probe_leases "
                    "WHERE name = ? AND expires_at > ?",
                    (name, now),
                ).fetchone()
                return int(row["active"] if row is not None else 0)

    def clear_probe_leases(self, name: str) -> int:
        """Delete all probe leases for *name* and return deleted-row count."""
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM circuit_breaker_probe_leases WHERE name = ?",
                    (name,),
                )
                return int(cursor.rowcount or 0)
