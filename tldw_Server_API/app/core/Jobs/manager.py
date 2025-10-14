from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid as _uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

from .migrations import ensure_jobs_tables
from .pg_migrations import ensure_jobs_tables_pg


def _parse_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    try:
        # Accept ISO8601 or SQLite default format
        s = str(v).replace("Z", "+00:00")
        # Try fromisoformat
        return datetime.fromisoformat(s)
    except Exception:
        return None


class JobManager:
    """SQLite-backed Job Manager with leasing and basic cancellation."""

    def __init__(self, db_path: Optional[Path] = None, *, backend: Optional[str] = None, db_url: Optional[str] = None):
        """Initialize JobManager.

        Currently supports SQLite. A future path will add Postgres support via db_url.
        """
        # Determine backend from explicit arg or env URL
        if backend is None:
            env_url = os.getenv("JOBS_DB_URL", "")
            if (db_url and str(db_url).startswith("postgres")) or env_url.startswith("postgres"):
                self.backend = "postgres"
                self.db_url = db_url or env_url
            else:
                self.backend = "sqlite"
                self.db_url = db_url
        else:
            self.backend = backend.lower()
            self.db_url = db_url
        # Ensure schema for selected backend
        if self.backend == "postgres":
            if not (self.db_url and str(self.db_url).startswith("postgres")):
                raise ValueError("Postgres backend selected but no valid db_url provided; set JOBS_DB_URL or pass db_url")
            ensure_jobs_tables_pg(self.db_url)
            self.db_path = Path(":memory:")  # unused
        else:
            self.db_path = ensure_jobs_tables(db_path)
        self._conn = None  # Lazily opened per operation

    # Connection helper
    def _connect(self):
        if self.backend == "postgres":
            import psycopg
            return psycopg.connect(self.db_url)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _pg_cursor(self, conn):
        from psycopg.rows import dict_row  # type: ignore
        return conn.cursor(row_factory=dict_row)

    # CRUD / queries
    def create_job(
        self,
        *,
        domain: str,
        queue: str,
        job_type: str,
        payload: Dict[str, Any],
        owner_user_id: Optional[str],
        project_id: Optional[int] = None,
        priority: int = 5,
        max_retries: int = 3,
        available_at: Optional[datetime] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self._connect()
        try:
            now = datetime.utcnow().isoformat()
            uuid_val = str(_uuid.uuid4())
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if idempotency_key:
                            cur.execute(
                                (
                                    "INSERT INTO jobs (uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, created_at, updated_at) "
                                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, 'queued', %s, %s, 0, %s, NOW(), NOW()) "
                                    "ON CONFLICT (idempotency_key) DO NOTHING RETURNING *"
                                ),
                                (
                                    uuid_val,
                                    domain,
                                    queue,
                                    job_type,
                                    owner_user_id,
                                    project_id,
                                    idempotency_key,
                                    payload,
                                    priority,
                                    max_retries,
                                    available_at if available_at else None,
                                ),
                            )
                            row = cur.fetchone()
                            if not row:
                                cur.execute("SELECT * FROM jobs WHERE idempotency_key = %s", (idempotency_key,))
                                row = cur.fetchone()
                            return dict(row) if row else {"uuid": uuid_val, "status": "queued"}
                        # Non-idempotent insert
                        cur.execute(
                            (
                                "INSERT INTO jobs (uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, created_at, updated_at) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, 'queued', %s, %s, 0, %s, NOW(), NOW()) RETURNING *"
                            ),
                            (
                                uuid_val,
                                domain,
                                queue,
                                job_type,
                                owner_user_id,
                                project_id,
                                idempotency_key,
                                payload,
                                priority,
                                max_retries,
                                available_at if available_at else None,
                            ),
                        )
                        row = cur.fetchone()
                        return dict(row)
            else:
                with conn:
                    payload_json = json.dumps(payload)
                    if idempotency_key:
                        # Idempotent create: attempt INSERT OR IGNORE, then SELECT by key
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO jobs (
                              uuid, domain, queue, job_type, owner_user_id, project_id,
                              idempotency_key, payload, result, status, priority, max_retries,
                              retry_count, available_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'queued', ?, ?, 0, ?, ?, ?)
                            """,
                            (
                                uuid_val,
                                domain,
                                queue,
                                job_type,
                                owner_user_id,
                                project_id,
                                idempotency_key,
                                payload_json,
                                priority,
                                max_retries,
                                available_at.isoformat() if available_at else None,
                                now,
                                now,
                            ),
                        )
                        row = conn.execute(
                            "SELECT * FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
                        ).fetchone()
                        if row:
                            return dict(row)
                    # Non-idempotent (or no existing row on IGNORE path): normal insert
                    conn.execute(
                        """
                        INSERT INTO jobs (
                          uuid, domain, queue, job_type, owner_user_id, project_id,
                          idempotency_key, payload, result, status, priority, max_retries,
                          retry_count, available_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'queued', ?, ?, 0, ?, ?, ?)
                        """,
                        (
                            uuid_val,
                            domain,
                            queue,
                            job_type,
                            owner_user_id,
                            project_id,
                            idempotency_key,
                            json.dumps(payload),
                            priority,
                            max_retries,
                            available_at.isoformat() if available_at else None,
                            now,
                            now,
                        ),
                    )
                    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    return dict(row) if row else {"id": job_id, "uuid": uuid_val, "status": "queued"}
        finally:
            conn.close()

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    cur.execute("SELECT * FROM jobs WHERE id = %s", (int(job_id),))
                    row = cur.fetchone()
                if not row:
                    return None
                d = dict(row)
                return d
            else:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if not row:
                    return None
                d = dict(row)
                try:
                    if isinstance(d.get("payload"), str):
                        d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
                    if isinstance(d.get("result"), str):
                        d["result"] = json.loads(d["result"]) if d["result"] else None
                except Exception:
                    pass
                return d
        finally:
            conn.close()

    def list_jobs(
        self,
        *,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        status: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            if self.backend == "postgres":
                query = "SELECT * FROM jobs WHERE 1=1"
                params: List[Any] = []
                if domain:
                    query += " AND domain = %s"
                    params.append(domain)
                if queue:
                    query += " AND queue = %s"
                    params.append(queue)
                if status:
                    query += " AND status = %s"
                    params.append(status)
                if owner_user_id:
                    query += " AND owner_user_id = %s"
                    params.append(owner_user_id)
                query += " ORDER BY created_at DESC LIMIT %s"
                params.append(limit)
                with self._pg_cursor(conn) as cur:
                    cur.execute(query, params)
                    rows = cur.fetchall()
                out = [dict(r) for r in rows]
                return out
            else:
                query = "SELECT * FROM jobs WHERE 1=1"
                params: List[Any] = []
                if domain:
                    query += " AND domain = ?"
                    params.append(domain)
                if queue:
                    query += " AND queue = ?"
                    params.append(queue)
                if status:
                    query += " AND status = ?"
                    params.append(status)
                if owner_user_id:
                    query += " AND owner_user_id = ?"
                    params.append(owner_user_id)
                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(query, params).fetchall()
                out: List[Dict[str, Any]] = []
                for r in rows:
                    d = dict(r)
                    try:
                        if isinstance(d.get("payload"), str):
                            d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
                        if isinstance(d.get("result"), str):
                            d["result"] = json.loads(d["result"]) if d["result"] else None
                    except Exception:
                        pass
                    out.append(d)
                return out
        finally:
            conn.close()

    def acquire_next_job(
        self,
        *,
        domain: str,
        queue: str,
        lease_seconds: int,
        worker_id: str,
        owner_user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        max_lease = int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600")
        lease_seconds = max(5, min(max_lease, int(lease_seconds)))
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        base = (
                            "SELECT id FROM jobs WHERE domain = %s AND queue = %s AND ("
                            "  (status = 'queued' AND (available_at IS NULL OR available_at <= NOW())) OR"
                            "  (status = 'processing' AND (leased_until IS NULL OR leased_until <= NOW()))"
                            ")"
                        )
                        params: List[Any] = [domain, queue]
                        if owner_user_id:
                            base += " AND owner_user_id = %s"
                            params.append(owner_user_id)
                        base += " ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
                        cur.execute(base, params)
                        row = cur.fetchone()
                        if not row:
                            return None
                        job_id = int(row[0])
                        cur.execute(
                            (
                                "UPDATE jobs SET status = 'processing', started_at = COALESCE(started_at, NOW()), "
                                "leased_until = NOW() + (%s || ' seconds')::interval, worker_id = %s, lease_id = %s WHERE id = %s"
                            ),
                            (int(lease_seconds), worker_id, str(_uuid.uuid4()), job_id),
                        )
                        cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
                        row2 = cur.fetchone()
                        if not row2:
                            return None
                        d = dict(row2)
                        if isinstance(d.get("payload"), str):
                            try:
                                d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
                            except Exception:
                                pass
                        return d
            else:
                with conn:
                    # Consider queued jobs and reclaim expired processing leases (SQLite)
                    base = (
                        "SELECT id FROM jobs WHERE domain = ? AND queue = ? AND ("
                        "  (status = 'queued' AND (available_at IS NULL OR available_at <= DATETIME('now'))) OR"
                        "  (status = 'processing' AND (leased_until IS NULL OR leased_until <= DATETIME('now')))"
                        ")"
                    )
                    params: List[Any] = [domain, queue]
                    if owner_user_id:
                        base += " AND owner_user_id = ?"
                        params.append(owner_user_id)
                    base += " ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, created_at ASC LIMIT 1"
                    row = conn.execute(base, params).fetchone()
                    if not row:
                        return None
                    job_id = row[0]
                    # Transition to processing with lease; allow both queued and expired processing
                    conn.execute(
                        (
                            "UPDATE jobs SET status = 'processing', started_at = COALESCE(started_at, DATETIME('now')), "
                            "leased_until = DATETIME('now', ?), worker_id = ?, lease_id = ? "
                            "WHERE id = ? AND (status = 'queued' OR (status = 'processing' AND (leased_until IS NULL OR leased_until <= DATETIME('now'))))"
                        ),
                        (f"+{lease_seconds} seconds", worker_id, str(_uuid.uuid4()), job_id),
                    )
                    if conn.total_changes == 0:
                        return None
                    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    if not row:
                        return None
                    d = dict(row)
                    try:
                        if isinstance(d.get("payload"), str):
                            d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
                    except Exception:
                        pass
                    return d
        finally:
            conn.close()

    def renew_job_lease(self, job_id: int, *, seconds: int) -> bool:
        max_lease = int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600")
        seconds = max(1, min(max_lease, int(seconds)))
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        cur.execute(
                            "UPDATE jobs SET leased_until = NOW() + (%s || ' seconds')::interval WHERE id = %s AND status = 'processing'",
                            (int(seconds), int(job_id)),
                        )
                        return cur.rowcount > 0
            else:
                with conn:
                    conn.execute(
                        "UPDATE jobs SET leased_until = DATETIME('now', ?) WHERE id = ? AND status = 'processing'",
                        (f"+{seconds} seconds", job_id),
                    )
                    return conn.total_changes > 0
        finally:
            conn.close()

    def complete_job(self, job_id: int, *, result: Optional[Dict[str, Any]] = None) -> bool:
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        cur.execute(
                            "UPDATE jobs SET status = 'completed', result = %s, completed_at = NOW(), leased_until = NULL WHERE id = %s",
                            (result, int(job_id)),
                        )
                        return cur.rowcount > 0
            else:
                with conn:
                    conn.execute(
                        "UPDATE jobs SET status = 'completed', result = ?, completed_at = DATETIME('now'), leased_until = NULL WHERE id = ?",
                        (json.dumps(result) if result is not None else None, job_id),
                    )
                    return conn.total_changes > 0
        finally:
            conn.close()

    def fail_job(self, job_id: int, *, error: str, retryable: bool = True, backoff_seconds: int = 10) -> bool:
        import random
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if retryable:
                            cur.execute("SELECT retry_count FROM jobs WHERE id = %s", (int(job_id),))
                            row = cur.fetchone()
                            current = int(row[0]) if row else 0
                            exp_backoff = max(1, int(backoff_seconds * (2 ** current)))
                            jitter = random.randint(0, max(1, exp_backoff // 4))
                            delay = exp_backoff + jitter
                            cur.execute(
                                (
                                    "UPDATE jobs SET status = 'queued', retry_count = retry_count + 1, last_error = %s, error_message = %s, "
                                    "available_at = NOW() + (%s || ' seconds')::interval, leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                    "WHERE id = %s AND retry_count < max_retries"
                                ),
                                (error, error, int(delay), int(job_id)),
                            )
                            if cur.rowcount > 0:
                                return True
                        # terminal failure
                        cur.execute(
                            "UPDATE jobs SET status = 'failed', error_message = %s, completed_at = NOW(), leased_until = NULL WHERE id = %s",
                            (error, int(job_id)),
                        )
                        return cur.rowcount > 0
            else:
                with conn:
                    if retryable:
                        # compute jittered backoff based on current retry_count
                        row = conn.execute("SELECT retry_count FROM jobs WHERE id = ?", (job_id,)).fetchone()
                        current = int(row[0]) if row else 0
                        exp_backoff = max(1, int(backoff_seconds * (2 ** current)))
                        jitter = random.randint(0, max(1, exp_backoff // 4))
                        delay = exp_backoff + jitter
                        conn.execute(
                            (
                                "UPDATE jobs SET status = 'queued', retry_count = retry_count + 1, last_error = ?, "
                                "error_message = ?, available_at = DATETIME('now', ?), leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                "WHERE id = ? AND retry_count < max_retries"
                            ),
                            (error, error, f"+{delay} seconds", job_id),
                        )
                        if conn.total_changes > 0:
                            return True
                    # terminal failure
                    conn.execute(
                        "UPDATE jobs SET status = 'failed', error_message = ?, completed_at = DATETIME('now'), leased_until = NULL WHERE id = ?",
                        (error, job_id),
                    )
                    return conn.total_changes > 0
        finally:
            conn.close()

    def cancel_job(self, job_id: int, *, reason: Optional[str] = None) -> bool:
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        cur.execute(
                            "UPDATE jobs SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = %s WHERE id = %s AND status = 'queued'",
                            (reason, int(job_id)),
                        )
                        if cur.rowcount > 0:
                            return True
                        cur.execute(
                            "UPDATE jobs SET cancel_requested_at = NOW(), cancellation_reason = %s WHERE id = %s AND status = 'processing'",
                            (reason, int(job_id)),
                        )
                        return cur.rowcount > 0
            else:
                with conn:
                    # cancel queued immediately
                    conn.execute(
                        "UPDATE jobs SET status = 'cancelled', cancelled_at = DATETIME('now'), cancellation_reason = ? WHERE id = ? AND status = 'queued'",
                        (reason, job_id),
                    )
                    if conn.total_changes > 0:
                        return True
                    # request cancellation if processing
                    conn.execute(
                        "UPDATE jobs SET cancel_requested_at = DATETIME('now'), cancellation_reason = ? WHERE id = ? AND status = 'processing'",
                        (reason, job_id),
                    )
                    return conn.total_changes > 0
        finally:
            conn.close()

    def finalize_cancelled(self, job_id: int, *, reason: Optional[str] = None) -> bool:
        """Mark a job as cancelled terminally, regardless of prior cancel request.

        Intended to be called by workers when they observe a cancel requested during processing.
        """
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        cur.execute(
                            "UPDATE jobs SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = %s, leased_until = NULL WHERE id = %s",
                            (reason, int(job_id)),
                        )
                        return cur.rowcount > 0
            else:
                with conn:
                    conn.execute(
                        "UPDATE jobs SET status = 'cancelled', cancelled_at = DATETIME('now'), cancellation_reason = ?, leased_until = NULL WHERE id = ?",
                        (reason, job_id),
                    )
                    return conn.total_changes > 0
        finally:
            conn.close()
