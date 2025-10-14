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
from .metrics import (
    ensure_jobs_metrics_registered,
    observe_queue_latency,
    observe_duration,
    increment_retries,
    increment_failures,
    set_queue_gauges,
)


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
    """DB-backed Job Manager with leasing, retries, and cancellation.

    Supports SQLite by default and PostgreSQL when `JOBS_DB_URL` (or `db_url`)
    is provided with a Postgres DSN. Provides helpers to create, list, acquire,
    renew, complete, fail, and cancel jobs in a generic, domain-agnostic way.

    Notes on lease enforcement:
    - Methods that acknowledge or extend work (renew/complete/fail) accept
      optional `worker_id` and `lease_id` parameters. If the environment
      variable `JOBS_ENFORCE_LEASE_ACK` is set to a truthy value, these values
      must match the current job lease or the operation is rejected.
    - By default enforcement is disabled to preserve backward compatibility.
    """

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
        try:
            ensure_jobs_metrics_registered()
        except Exception:
            pass

    # Standard queues across domains
    STANDARD_QUEUES = ("default", "high", "low")

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

    def _update_gauges(self, *, domain: str, queue: str, job_type: Optional[str] = None) -> None:
        try:
            conn = self._connect()
            try:
                if self.backend == "postgres":
                    with self._pg_cursor(conn) as cur:
                        cur.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued'",
                            (domain, queue, job_type),
                        )
                        q = int(cur.fetchone()[0])
                        cur.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='processing'",
                            (domain, queue, job_type),
                        )
                        p = int(cur.fetchone()[0])
                else:
                    q = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='queued'",
                            (domain, queue, job_type),
                        ).fetchone()[0]
                    )
                    p = int(
                        conn.execute(
                            "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='processing'",
                            (domain, queue, job_type),
                        ).fetchone()[0]
                    )
                set_queue_gauges(domain, queue, job_type, q, p, backlog=q)
            finally:
                conn.close()
        except Exception:
            pass

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
        """Create a new job.

        Args:
            domain: Logical domain (e.g., "chatbooks", "prompt_studio").
            queue: Queue name within the domain.
            job_type: Free-form job type string.
            payload: Opaque payload to be interpreted by the worker.
            owner_user_id: Owner of the job for scoping/quotas.
            project_id: Optional project association.
            priority: Lower number means higher priority (default 5).
            max_retries: Maximum automatic retries on failure.
            available_at: Optional schedule time before the job becomes acquirable.
            idempotency_key: If provided, duplicate creates return the same row.

        Returns:
            A dict representing the created (or existing, if idempotent) job row.
        """
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
                                (available_at.strftime("%Y-%m-%d %H:%M:%S") if available_at else None),
                                now,
                                now,
                            ),
                        )
                        row = conn.execute(
                            "SELECT * FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
                        ).fetchone()
                        if row:
                            d = dict(row)
                            try:
                                self._update_gauges(domain=domain, queue=queue, job_type=job_type)
                            except Exception:
                                pass
                            return d
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
                            (available_at.strftime("%Y-%m-%d %H:%M:%S") if available_at else None),
                            now,
                            now,
                        ),
                    )
                    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    d = dict(row) if row else {"id": job_id, "uuid": uuid_val, "status": "queued", "domain": domain, "queue": queue, "job_type": job_type}
                    try:
                        self._update_gauges(domain=domain, queue=queue, job_type=job_type)
                    except Exception:
                        pass
                    return d
        finally:
            conn.close()

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a job by numeric id.

        Returns None if not found. JSON payload/result are normalized to dicts
        for SQLite; Postgres returns native JSON via the driver.
        """
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
        job_type: Optional[str] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filters.

        Args:
            domain: Filter by domain.
            queue: Filter by queue.
            status: Filter by status (queued|processing|completed|failed|cancelled).
            owner_user_id: Filter by owner id.
            limit: Max rows to return (default 100).
        """
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
                if job_type:
                    query += " AND job_type = %s"
                    params.append(job_type)
                if created_after:
                    query += " AND created_at >= %s"
                    params.append(created_after)
                if created_before:
                    query += " AND created_at <= %s"
                    params.append(created_before)
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
                if job_type:
                    query += " AND job_type = ?"
                    params.append(job_type)
                if created_after:
                    query += " AND created_at >= ?"
                    params.append(created_after.isoformat())
                if created_before:
                    query += " AND created_at <= ?"
                    params.append(created_before.isoformat())
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
        """Atomically acquire the next eligible job and start a lease.

        Selection order: priority ASC, available_at/created_at ASC.
        Reclaims expired processing jobs by allowing acquisition when
        `leased_until` is NULL or in the past.
        """
        max_lease = int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600")
        lease_seconds = max(1, min(max_lease, int(lease_seconds)))
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
                        # Acquire and start lease
                        cur.execute(
                            (
                                "UPDATE jobs SET status = 'processing', "
                                "started_at = COALESCE(started_at, NOW()), "
                                "acquired_at = COALESCE(acquired_at, NOW()), "
                                "leased_until = NOW() + (%s || ' seconds')::interval, "
                                "worker_id = %s, lease_id = %s WHERE id = %s"
                            ),
                            (int(lease_seconds), worker_id, str(_uuid.uuid4()), job_id),
                        )
                        cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
                        row2 = cur.fetchone()
                        if not row2:
                            return None
                        d = dict(row2)
                        # Metrics: queue latency
                        try:
                            created_at = d.get("created_at")
                            if isinstance(created_at, str):
                                created_at = _parse_dt(created_at)
                            acquired_at = d.get("acquired_at")
                            if isinstance(acquired_at, str):
                                acquired_at = _parse_dt(acquired_at)
                            observe_queue_latency(d, acquired_at, created_at)
                        except Exception:
                            pass
                        if isinstance(d.get("payload"), str):
                            try:
                                d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
                            except Exception:
                                pass
                        try:
                            self._update_gauges(domain=domain, queue=queue, job_type=d.get("job_type"))
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
                            "UPDATE jobs SET status = 'processing', "
                            "started_at = COALESCE(started_at, DATETIME('now')), "
                            "acquired_at = COALESCE(acquired_at, DATETIME('now')), "
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
                    # Metrics: queue latency
                    try:
                        created_at = d.get("created_at")
                        acquired_at = d.get("acquired_at")
                        observe_queue_latency(d, _parse_dt(acquired_at), _parse_dt(created_at))
                    except Exception:
                        pass
                    try:
                        if isinstance(d.get("payload"), str):
                            d["payload"] = json.loads(d["payload"]) if d["payload"] else {}
                    except Exception:
                        pass
                    try:
                        self._update_gauges(domain=domain, queue=queue, job_type=d.get("job_type"))
                    except Exception:
                        pass
                    return d
        finally:
            conn.close()

    def renew_job_lease(
        self,
        job_id: int,
        *,
        seconds: int,
        worker_id: Optional[str] = None,
        lease_id: Optional[str] = None,
        enforce: Optional[bool] = None,
    ) -> bool:
        """Extend the lease on a processing job.

        If `enforce` is True (or `JOBS_ENFORCE_LEASE_ACK` env is truthy), the
        current `worker_id`/`lease_id` must match to succeed. If values are not
        provided while enforcement is enabled, the operation will be rejected.
        """
        max_lease = int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600")
        seconds = max(1, min(max_lease, int(seconds)))
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1", "true", "yes", "y", "on"}
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if enforce:
                            cur.execute(
                                (
                                    "UPDATE jobs SET leased_until = NOW() + (%s || ' seconds')::interval "
                                    "WHERE id = %s AND status = 'processing' AND worker_id = %s AND lease_id = %s"
                                ),
                                (int(seconds), int(job_id), worker_id, lease_id),
                            )
                            return cur.rowcount > 0
                        else:
                            cur.execute(
                                "UPDATE jobs SET leased_until = NOW() + (%s || ' seconds')::interval WHERE id = %s AND status = 'processing'",
                                (int(seconds), int(job_id)),
                            )
                            return cur.rowcount > 0
            else:
                with conn:
                    if enforce:
                        conn.execute(
                            (
                                "UPDATE jobs SET leased_until = DATETIME('now', ?) "
                                "WHERE id = ? AND status = 'processing' AND worker_id = ? AND lease_id = ?"
                            ),
                            (f"+{seconds} seconds", job_id, worker_id, lease_id),
                        )
                        return conn.total_changes > 0
                    else:
                        conn.execute(
                            "UPDATE jobs SET leased_until = DATETIME('now', ?) WHERE id = ? AND status = 'processing'",
                            (f"+{seconds} seconds", job_id),
                        )
                        return conn.total_changes > 0
        finally:
            conn.close()

    def complete_job(
        self,
        job_id: int,
        *,
        result: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
        lease_id: Optional[str] = None,
        enforce: Optional[bool] = None,
    ) -> bool:
        """Mark a job as completed and clear the lease.

        See `renew_job_lease` for enforcement semantics.
        """
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1", "true", "yes", "y", "on"}
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        # Pre-fetch for metrics
                        cur.execute("SELECT domain, queue, job_type, started_at, acquired_at FROM jobs WHERE id = %s", (int(job_id),))
                        base = cur.fetchone()
                        if enforce:
                            cur.execute(
                                (
                                    "UPDATE jobs SET status = 'completed', result = %s, completed_at = NOW(), "
                                    "leased_until = NULL WHERE id = %s AND worker_id = %s AND lease_id = %s"
                                ),
                                (result, int(job_id), worker_id, lease_id),
                            )
                            return cur.rowcount > 0
                        else:
                            cur.execute(
                                "UPDATE jobs SET status = 'completed', result = %s, completed_at = NOW(), leased_until = NULL WHERE id = %s",
                                (result, int(job_id)),
                            )
                            ok = cur.rowcount > 0
                        # Metrics: duration
                        try:
                            if base and ok:
                                d = dict(base)
                                started_at = d.get("started_at") or d.get("acquired_at")
                                if isinstance(started_at, str):
                                    started_at = _parse_dt(started_at)
                                observe_duration({"domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}, started_at, datetime.utcnow())
                                # Update gauges after terminal state
                                self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                        except Exception:
                            pass
                        return ok
            else:
                with conn:
                    # Pre-fetch for metrics
                    rowm = conn.execute("SELECT domain, queue, job_type, started_at, acquired_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    if enforce:
                        conn.execute(
                            (
                                "UPDATE jobs SET status = 'completed', result = ?, completed_at = DATETIME('now'), "
                                "leased_until = NULL WHERE id = ? AND worker_id = ? AND lease_id = ?"
                            ),
                            (json.dumps(result) if result is not None else None, job_id, worker_id, lease_id),
                        )
                        ok = conn.total_changes > 0
                    else:
                        conn.execute(
                            "UPDATE jobs SET status = 'completed', result = ?, completed_at = DATETIME('now'), leased_until = NULL WHERE id = ?",
                            (json.dumps(result) if result is not None else None, job_id),
                        )
                        ok = conn.total_changes > 0
                    # Metrics: duration
                    try:
                        if rowm and ok:
                            d = dict(rowm)
                            s = _parse_dt(d.get("started_at")) or _parse_dt(d.get("acquired_at"))
                            observe_duration({"domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}, s, datetime.utcnow())
                            self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                    except Exception:
                        pass
                    return ok
        finally:
            conn.close()

    def fail_job(
        self,
        job_id: int,
        *,
        error: str,
        retryable: bool = True,
        backoff_seconds: int = 10,
        worker_id: Optional[str] = None,
        lease_id: Optional[str] = None,
        enforce: Optional[bool] = None,
    ) -> bool:
        """Mark a job as failed; optionally reschedule with backoff if retryable.

        See `renew_job_lease` for enforcement semantics.
        """
        import random
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1", "true", "yes", "y", "on"}
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        # For metrics, fetch labels
                        cur.execute("SELECT domain, queue, job_type FROM jobs WHERE id = %s", (int(job_id),))
                        elem = cur.fetchone()
                        if retryable:
                            cur.execute("SELECT retry_count FROM jobs WHERE id = %s", (int(job_id),))
                            row = cur.fetchone()
                            current = int(row[0]) if row else 0
                            exp_backoff = max(1, int(backoff_seconds * (2 ** current)))
                            jitter = random.randint(0, max(1, exp_backoff // 4))
                            delay = exp_backoff + jitter
                            if enforce:
                                cur.execute(
                                    (
                                        "UPDATE jobs SET status = 'queued', retry_count = retry_count + 1, last_error = %s, error_message = %s, "
                                        "available_at = NOW() + (%s || ' seconds')::interval, leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                        "WHERE id = %s AND retry_count < max_retries AND worker_id = %s AND lease_id = %s"
                                    ),
                                    (error, error, int(delay), int(job_id), worker_id, lease_id),
                                )
                            else:
                                cur.execute(
                                    (
                                        "UPDATE jobs SET status = 'queued', retry_count = retry_count + 1, last_error = %s, error_message = %s, "
                                        "available_at = NOW() + (%s || ' seconds')::interval, leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                        "WHERE id = %s AND retry_count < max_retries"
                                    ),
                                    (error, error, int(delay), int(job_id)),
                                )
                            if cur.rowcount > 0:
                                try:
                                    if elem:
                                        increment_retries(dict(elem))
                                except Exception:
                                    pass
                                return True
                        # terminal failure
                        if enforce:
                            cur.execute(
                                "UPDATE jobs SET status = 'failed', error_message = %s, completed_at = NOW(), leased_until = NULL WHERE id = %s AND worker_id = %s AND lease_id = %s",
                                (error, int(job_id), worker_id, lease_id),
                            )
                        else:
                            cur.execute(
                                "UPDATE jobs SET status = 'failed', error_message = %s, completed_at = NOW(), leased_until = NULL WHERE id = %s",
                                (error, int(job_id)),
                            )
                        ok = cur.rowcount > 0
                        try:
                            if ok and elem:
                                d = dict(elem)
                                increment_failures(d, reason="terminal")
                                self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                        except Exception:
                            pass
                        return ok
            else:
                with conn:
                    # For metrics, fetch labels
                    rowl = conn.execute("SELECT domain, queue, job_type FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    if retryable:
                        # compute jittered backoff based on current retry_count
                        row = conn.execute("SELECT retry_count FROM jobs WHERE id = ?", (job_id,)).fetchone()
                        current = int(row[0]) if row else 0
                        exp_backoff = max(1, int(backoff_seconds * (2 ** current)))
                        jitter = random.randint(0, max(1, exp_backoff // 4))
                        delay = exp_backoff + jitter
                        if enforce:
                            conn.execute(
                                (
                                    "UPDATE jobs SET status = 'queued', retry_count = retry_count + 1, last_error = ?, "
                                    "error_message = ?, available_at = DATETIME('now', ?), leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                    "WHERE id = ? AND retry_count < max_retries AND worker_id = ? AND lease_id = ?"
                                ),
                                (error, error, f"+{delay} seconds", job_id, worker_id, lease_id),
                            )
                        else:
                            conn.execute(
                                (
                                    "UPDATE jobs SET status = 'queued', retry_count = retry_count + 1, last_error = ?, "
                                    "error_message = ?, available_at = DATETIME('now', ?), leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                    "WHERE id = ? AND retry_count < max_retries"
                                ),
                                (error, error, f"+{delay} seconds", job_id),
                            )
                        if conn.total_changes > 0:
                            try:
                                if rowl:
                                    increment_retries(dict(rowl))
                            except Exception:
                                pass
                            return True
                    # terminal failure
                    if enforce:
                        conn.execute(
                            "UPDATE jobs SET status = 'failed', error_message = ?, completed_at = DATETIME('now'), leased_until = NULL WHERE id = ? AND worker_id = ? AND lease_id = ?",
                            (error, job_id, worker_id, lease_id),
                        )
                    else:
                        conn.execute(
                            "UPDATE jobs SET status = 'failed', error_message = ?, completed_at = DATETIME('now'), leased_until = NULL WHERE id = ?",
                            (error, job_id),
                        )
                    ok = conn.total_changes > 0
                    try:
                        if ok and rowl:
                            d = dict(rowl)
                            increment_failures(d, reason="terminal")
                            self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                    except Exception:
                        pass
                    return ok
        finally:
            conn.close()

    def cancel_job(self, job_id: int, *, reason: Optional[str] = None) -> bool:
        """Request cancellation or cancel queued jobs immediately."""
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
                        # Terminally cancel processing jobs as well (more responsive semantics)
                        cur.execute(
                            "UPDATE jobs SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = %s, leased_until = NULL WHERE id = %s AND status = 'processing'",
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
                    # Terminally cancel processing jobs as well (more responsive semantics)
                    conn.execute(
                        "UPDATE jobs SET status = 'cancelled', cancelled_at = DATETIME('now'), cancellation_reason = ?, leased_until = NULL WHERE id = ? AND status = 'processing'",
                        (reason, job_id),
                    )
                    return conn.total_changes > 0
        finally:
            conn.close()

    # Maintenance
    def prune_jobs(self, *, statuses: Optional[List[str]] = None, older_than_days: int = 30) -> int:
        """Delete jobs in given statuses older than the threshold.

        Uses completed_at when present; otherwise falls back to created_at.
        Returns the number of deleted rows.
        """
        statuses = statuses or ["completed", "failed", "cancelled"]
        if not statuses:
            return 0
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        placeholders = ",".join(["%s"] * len(statuses))
                        cur.execute(
                            (
                                f"DELETE FROM jobs WHERE status IN ({placeholders}) AND "
                                "COALESCE(completed_at, created_at) <= NOW() - (%s || ' days')::interval"
                            ),
                            (*statuses, int(older_than_days)),
                        )
                        return cur.rowcount or 0
            else:
                with conn:
                    placeholders = ",".join(["?"] * len(statuses))
                    conn.execute(
                        (
                            f"DELETE FROM jobs WHERE status IN ({placeholders}) AND "
                            "COALESCE(completed_at, created_at) <= DATETIME('now', ?)"
                        ),
                        (*statuses, f"-{int(older_than_days)} days"),
                    )
                    return conn.total_changes or 0
        finally:
            conn.close()

    def get_queue_stats(
        self,
        *,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return counts grouped by domain/queue/job_type.

        Provides queued and processing counts per group.
        """
        conn = self._connect()
        try:
            if self.backend == "postgres":
                where = ["1=1"]
                params: List[Any] = []
                if domain:
                    where.append("domain = %s")
                    params.append(domain)
                if queue:
                    where.append("queue = %s")
                    params.append(queue)
                if job_type:
                    where.append("job_type = %s")
                    params.append(job_type)
                sql = (
                    "SELECT domain, queue, job_type, "
                    "SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS queued, "
                    "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing "
                    f"FROM jobs WHERE {' AND '.join(where)} GROUP BY domain, queue, job_type ORDER BY domain, queue, job_type"
                )
                with self._pg_cursor(conn) as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                return [
                    {
                        "domain": r[0],
                        "queue": r[1],
                        "job_type": r[2],
                        "queued": int(r[3] or 0),
                        "processing": int(r[4] or 0),
                    }
                    for r in rows
                ]
            else:
                where = ["1=1"]
                params2: List[Any] = []
                if domain:
                    where.append("domain = ?")
                    params2.append(domain)
                if queue:
                    where.append("queue = ?")
                    params2.append(queue)
                if job_type:
                    where.append("job_type = ?")
                    params2.append(job_type)
                sql = (
                    "SELECT domain, queue, job_type, "
                    "SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS queued, "
                    "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing "
                    f"FROM jobs WHERE {' AND '.join(where)} GROUP BY domain, queue, job_type ORDER BY domain, queue, job_type"
                )
                rows = conn.execute(sql, params2).fetchall()
                return [
                    {
                        "domain": r[0],
                        "queue": r[1],
                        "job_type": r[2],
                        "queued": int(r[3] or 0),
                        "processing": int(r[4] or 0),
                    }
                    for r in rows
                ]
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
