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
from .pg_migrations import ensure_job_counters_pg
from .metrics import (
    ensure_jobs_metrics_registered,
    observe_queue_latency,
    observe_duration,
    increment_retries,
    increment_failures,
    set_queue_gauges,
    increment_created,
    increment_completed,
    increment_cancelled,
)
from .tracing import job_span
from .event_stream import emit_job_event


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
            try:
                ensure_job_counters_pg(self.db_url)
            except Exception:
                pass
            self.db_path = Path(":memory:")  # unused
        else:
            # Prefer explicit db_path, then env override for tests (JOBS_DB_PATH), otherwise default
            if db_path is not None:
                self.db_path = ensure_jobs_tables(db_path)
            else:
                env_db_path = os.getenv("JOBS_DB_PATH")
                if env_db_path:
                    self.db_path = ensure_jobs_tables(Path(env_db_path))
                else:
                    self.db_path = ensure_jobs_tables(db_path)
        self._conn = None  # Lazily opened per operation
        try:
            ensure_jobs_metrics_registered()
        except Exception:
            pass

    # Standard queues across domains
    STANDARD_QUEUES = ("default", "high", "low")

    def _get_allowed_queues(self, domain: Optional[str] = None) -> List[str]:
        allowed = list(self.STANDARD_QUEUES)
        extra = os.getenv("JOBS_ALLOWED_QUEUES", "").strip()
        if extra:
            allowed.extend([q.strip() for q in extra.split(",") if q.strip()])
        if domain:
            key = f"JOBS_ALLOWED_QUEUES_{str(domain).upper()}"
            extra_d = os.getenv(key, "").strip()
            if extra_d:
                allowed.extend([q.strip() for q in extra_d.split(",") if q.strip()])
        # Deduplicate preserving order
        dedup: List[str] = []
        seen = set()
        for q in allowed:
            if q not in seen:
                dedup.append(q)
                seen.add(q)
        return dedup

    def _assert_invariants(self, row: Dict[str, Any]) -> None:
        try:
            status = str(row.get("status") or "")
            lease_id = row.get("lease_id")
            leased_until = _parse_dt(row.get("leased_until"))
            acquired_at = _parse_dt(row.get("acquired_at"))
            if status != "processing" and lease_id:
                logger.warning(f"Jobs invariant: non-processing job has lease_id (id={row.get('id')}, status={status})")
            if leased_until and acquired_at and leased_until < acquired_at:
                logger.warning(
                    f"Jobs invariant: leased_until < acquired_at (id={row.get('id')}, leased_until={leased_until}, acquired_at={acquired_at})"
                )
        except Exception:
            # Never raise from invariant checks
            pass

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
                counters_enabled = str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}
                if self.backend == "postgres":
                    with self._pg_cursor(conn) as cur:
                        if counters_enabled:
                            cur.execute(
                                "SELECT ready_count, scheduled_count, processing_count FROM job_counters WHERE domain=%s AND queue=%s AND job_type=%s",
                                (domain, queue, job_type),
                            )
                            rowc = cur.fetchone()
                            if rowc:
                                q_ready = int(rowc[0] or 0); q_sched = int(rowc[1] or 0); p = int(rowc[2] or 0)
                            else:
                                q_ready = q_sched = p = 0
                        else:
                            # ready queued (available_at <= now or null)
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued' AND (available_at IS NULL OR available_at <= NOW())",
                                (domain, queue, job_type),
                            )
                            q_ready_row = cur.fetchone()
                            q_ready = int(q_ready_row["c"]) if q_ready_row is not None else 0
                            # scheduled queued (available_at in future)
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued' AND (available_at IS NOT NULL AND available_at > NOW())",
                                (domain, queue, job_type),
                            )
                            q_sched_row = cur.fetchone()
                            q_sched = int(q_sched_row["c"]) if q_sched_row is not None else 0
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='processing'",
                                (domain, queue, job_type),
                            )
                            p_row = cur.fetchone()
                            p = int(p_row["c"]) if p_row is not None else 0
                else:
                    if counters_enabled:
                        rowc = conn.execute(
                            "SELECT ready_count, scheduled_count, processing_count FROM job_counters WHERE domain=? AND queue=? AND job_type=?",
                            (domain, queue, job_type),
                        ).fetchone()
                        if rowc:
                            q_ready = int(rowc[0] or 0); q_sched = int(rowc[1] or 0); p = int(rowc[2] or 0)
                        else:
                            q_ready = q_sched = p = 0
                    else:
                        q_ready = int(
                            conn.execute(
                                "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='queued' AND (available_at IS NULL OR available_at <= DATETIME('now'))",
                                (domain, queue, job_type),
                            ).fetchone()[0]
                        )
                        q_sched = int(
                            conn.execute(
                                "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME('now'))",
                                (domain, queue, job_type),
                            ).fetchone()[0]
                        )
                        p = int(
                            conn.execute(
                                "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND job_type=? AND status='processing'",
                                (domain, queue, job_type),
                            ).fetchone()[0]
                        )
                set_queue_gauges(domain, queue, job_type, q_ready, p, backlog=(q_ready + q_sched), scheduled=q_sched)
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
        request_id: Optional[str] = None,
        trace_id: Optional[str] = None,
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
        # Queue name policy
        allowed_queues = self._get_allowed_queues(domain)
        if queue not in allowed_queues:
            raise ValueError(f"Queue '{queue}' not allowed for domain '{domain}'. Allowed: {allowed_queues}")

        # JSON payload size cap
        max_bytes = int(os.getenv("JOBS_MAX_JSON_BYTES", "1048576") or "1048576")
        truncate = str(os.getenv("JOBS_JSON_TRUNCATE", "")).lower() in {"1", "true", "yes", "y", "on"}
        payload_json = json.dumps(payload)
        payload_bytes = len(payload_json.encode("utf-8"))
        if payload_bytes > max_bytes:
            if truncate:
                payload = {"_truncated": True, "len_bytes": payload_bytes}
                payload_json = json.dumps(payload)
            else:
                raise ValueError(f"Payload too large: {payload_bytes} bytes > limit {max_bytes}")

        # Note: completion_token enforcement applies to finalize paths (complete/fail), not creation.
        conn = self._connect()
        try:
            try:
                with job_span("job.create", job={"uuid": None, "domain": domain, "queue": queue, "job_type": job_type}, attrs={"idempotency_key": idempotency_key}):
                    pass
            except Exception:
                pass
            # Use SQLite-compatible timestamp formatting for reliable comparisons
            now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            uuid_val = str(_uuid.uuid4())
            if not trace_id:
                try:
                    trace_id = str(_uuid.uuid4())
                except Exception:
                    trace_id = None
            # Ensure PG receives timezone-aware timestamps
            from datetime import timezone as _tz
            avail_param = available_at
            if avail_param is not None and getattr(avail_param, "tzinfo", None) is None:
                avail_param = avail_param.replace(tzinfo=_tz.utc)
            # Optional job_type allowlist
            allowed_job_types: List[str] = []
            env_all = os.getenv("JOBS_ALLOWED_JOB_TYPES", "").strip()
            if env_all:
                allowed_job_types.extend([x.strip() for x in env_all.split(",") if x.strip()])
            if domain:
                env_dom = os.getenv(f"JOBS_ALLOWED_JOB_TYPES_{str(domain).upper()}", "").strip()
                if env_dom:
                    allowed_job_types.extend([x.strip() for x in env_dom.split(",") if x.strip()])
            if allowed_job_types and job_type not in allowed_job_types:
                raise ValueError(f"Job type '{job_type}' not allowed for domain '{domain}'. Allowed: {sorted(set(allowed_job_types))}")

            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if idempotency_key:
                            # Cast payload to jsonb explicitly to avoid adapter issues
                            cur.execute(
                                (
                                    "INSERT INTO jobs (uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, created_at, updated_at, request_id, trace_id) "
                                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NULL, 'queued', %s, %s, 0, %s, NOW(), NOW(), %s, %s) "
                                    "ON CONFLICT (domain, queue, job_type, idempotency_key) DO NOTHING RETURNING *"
                                ),
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
                                    avail_param if avail_param else None,
                                    request_id,
                                    trace_id,
                                ),
                            )
                            row = cur.fetchone()
                            was_insert = row is not None
                            if not row:
                                cur.execute(
                                    "SELECT * FROM jobs WHERE domain = %s AND queue = %s AND job_type = %s AND idempotency_key = %s",
                                    (domain, queue, job_type, idempotency_key),
                                )
                                row = cur.fetchone()
                            d = dict(row) if row else {"uuid": uuid_val, "status": "queued", "domain": domain, "queue": queue, "job_type": job_type}
                            try:
                                increment_created({"domain": domain, "queue": queue, "job_type": job_type})
                            except Exception:
                                pass
                            # Counters bump (PG, idempotent insert occurred)
                            try:
                                if was_insert and str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    is_sched = bool(avail_param)
                                    cur.execute(
                                        (
                                            "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(%s,%s,%s,%s,%s,0,0) "
                                            "ON CONFLICT (domain,queue,job_type) DO UPDATE SET ready_count = job_counters.ready_count + EXCLUDED.ready_count, scheduled_count = job_counters.scheduled_count + EXCLUDED.scheduled_count, updated_at = NOW()"
                                        ),
                                        (domain, queue, job_type, 0 if is_sched else 1, 1 if is_sched else 0),
                                    )
                            except Exception:
                                pass
                            try:
                                emit_job_event(
                                    "job.created",
                                    job=d,
                                    attrs={
                                        "idempotent": (not was_insert),
                                        "owner_user_id": d.get("owner_user_id"),
                                        "retry_count": int(d.get("retry_count") or 0),
                                    },
                                )
                            except Exception:
                                pass
                            return d
                        # Non-idempotent insert
                        cur.execute(
                            (
                                "INSERT INTO jobs (uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, created_at, updated_at) "
                                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, NULL, 'queued', %s, %s, 0, %s, NOW(), NOW()) RETURNING *"
                            ),
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
                                avail_param if avail_param else None,
                            ),
                        )
                        row = cur.fetchone()
                        d = dict(row)
                        try:
                            self._assert_invariants(d)
                        except Exception:
                            pass
                        try:
                            increment_created({"domain": domain, "queue": queue, "job_type": job_type})
                        except Exception:
                            pass
                        # Counters bump (PG, non-idempotent path)
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                is_sched = bool(avail_param)
                                cur.execute(
                                    (
                                        "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(%s,%s,%s,%s,%s,0,0) "
                                        "ON CONFLICT (domain,queue,job_type) DO UPDATE SET ready_count = job_counters.ready_count + EXCLUDED.ready_count, scheduled_count = job_counters.scheduled_count + EXCLUDED.scheduled_count, updated_at = NOW()"
                                    ),
                                    (domain, queue, job_type, 0 if is_sched else 1, 1 if is_sched else 0),
                                )
                        except Exception:
                            pass
                        try:
                            emit_job_event(
                                "job.created",
                                job=d,
                                attrs={
                                    "idempotent": False,
                                    "owner_user_id": d.get("owner_user_id"),
                                    "retry_count": int(d.get("retry_count") or 0),
                                },
                            )
                        except Exception:
                            pass
                        return d
            else:
                with conn:
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
                            "SELECT * FROM jobs WHERE domain = ? AND queue = ? AND job_type = ? AND idempotency_key = ?",
                            (domain, queue, job_type, idempotency_key),
                        ).fetchone()
                        if row:
                            d = dict(row)
                            try:
                                self._update_gauges(domain=domain, queue=queue, job_type=job_type)
                                increment_created({"domain": domain, "queue": queue, "job_type": job_type})
                            except Exception:
                                pass
                            try:
                                emit_job_event(
                                    "job.created",
                                    job=d,
                                    attrs={
                                        "idempotent": True,
                                        "owner_user_id": d.get("owner_user_id"),
                                        "retry_count": int(d.get("retry_count") or 0),
                                    },
                                )
                            except Exception:
                                pass
                            return d
                    # Non-idempotent (or no existing row on IGNORE path): normal insert
                    conn.execute(
                        """
                        INSERT INTO jobs (
                          uuid, domain, queue, job_type, owner_user_id, project_id,
                          idempotency_key, payload, result, status, priority, max_retries,
                          retry_count, available_at, created_at, updated_at, request_id, trace_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'queued', ?, ?, 0, ?, ?, ?, ?, ?)
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
                            request_id,
                            trace_id,
                        ),
                    )
                    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    d = dict(row) if row else {"id": job_id, "uuid": uuid_val, "status": "queued", "domain": domain, "queue": queue, "job_type": job_type}
                    try:
                        self._update_gauges(domain=domain, queue=queue, job_type=job_type)
                        increment_created({"domain": domain, "queue": queue, "job_type": job_type})
                    except Exception:
                        pass
                    try:
                        if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                            is_sched = bool(available_at)
                            conn.execute(
                                (
                                    "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?,?,0,0,0) "
                                    "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = ready_count + ?, scheduled_count = scheduled_count + ?, updated_at = DATETIME('now')"
                                ),
                                (domain, queue, job_type, 0 if is_sched else 1, 1 if is_sched else 0, 0 if is_sched else 1, 1 if is_sched else 0),
                            )
                    except Exception:
                        pass
                    try:
                        emit_job_event(
                            "job.created",
                            job={**d, "request_id": request_id, "trace_id": trace_id},
                            attrs={
                                "idempotent": False,
                                "owner_user_id": d.get("owner_user_id"),
                                "retry_count": int(d.get("retry_count") or 0),
                            },
                        )
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
        # Read-only helper; no completion_token semantics apply
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
        sort_by: str = "created_at",
        sort_order: str = "desc",
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
                sort_col = sort_by if sort_by in {"created_at", "priority", "status"} else "created_at"
                sort_ord = "DESC" if str(sort_order).lower() == "desc" else "ASC"
                # Add deterministic tie-breaker on id
                if sort_col == "created_at":
                    query += f" ORDER BY {sort_col} {sort_ord}, id {'DESC' if sort_ord=='DESC' else 'ASC'} LIMIT %s"
                else:
                    query += f" ORDER BY {sort_col} {sort_ord} LIMIT %s"
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
                sort_col = sort_by if sort_by in {"created_at", "priority", "status"} else "created_at"
                sort_ord = "DESC" if str(sort_order).lower() == "desc" else "ASC"
                if sort_col == "created_at":
                    query += f" ORDER BY {sort_col} {sort_ord}, id {'DESC' if sort_ord=='DESC' else 'ASC'} LIMIT ?"
                else:
                    query += f" ORDER BY {sort_col} {sort_ord} LIMIT ?"
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
        # Adaptive default when seconds <= 0 and enabled
        try:
            req = int(lease_seconds)
        except Exception:
            req = 0
        if req <= 0 and str(os.getenv("JOBS_ADAPTIVE_LEASE_ENABLE", "")).lower() in {"1","true","yes","y","on"}:
            try:
                req = self._adaptive_lease_seconds(domain, queue, None)
            except Exception:
                req = 30
        lease_seconds = max(1, min(max_lease, int(req)))
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if str(os.getenv("JOBS_PG_SINGLE_UPDATE_ACQUIRE", "")).lower() in {"1","true","yes","y","on"}:
                            cur.execute(
                                (
                                    "WITH picked AS ("
                                    "  SELECT id FROM jobs WHERE domain=%s AND queue=%s AND ("
                                    "    (status='queued' AND (available_at IS NULL OR available_at <= NOW())) OR"
                                    "    (status='processing' AND (leased_until IS NULL OR leased_until <= NOW()))"
                                    "  )"
                                    + (" AND owner_user_id = %s" if owner_user_id else "") +
                                    "  ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, id ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
                                    ")"
                                    "UPDATE jobs SET status='processing', started_at = COALESCE(started_at, NOW()), acquired_at = COALESCE(acquired_at, NOW()), leased_until = NOW() + (%s || ' seconds')::interval, worker_id = %s, lease_id = %s "
                                    "WHERE id IN (SELECT id FROM picked) RETURNING *"
                                ),
                                ([domain, queue] + ([owner_user_id] if owner_user_id else []) + [int(lease_seconds), worker_id, str(_uuid.uuid4())]),
                            )
                            row2 = cur.fetchone()
                            if not row2:
                                return None
                            d = dict(row2)
                        else:
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
                            # Stable ordering: priority ASC (lower number is higher priority), then available/created asc, then id asc
                            base += " ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, id ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
                            cur.execute(base, params)
                            row = cur.fetchone()
                            if not row:
                                return None
                            job_id = int(row["id"])  # dict_row
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
                        # Counters: adjust queued->processing
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                is_sched = bool(d.get("available_at")) and (_parse_dt(d.get("available_at")) or datetime.utcnow()) > datetime.utcnow()
                                cur.execute(
                                    (
                                        "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(%s,%s,%s,0,0,0,0) "
                                        "ON CONFLICT (domain,queue,job_type) DO UPDATE SET ready_count = job_counters.ready_count + %s, scheduled_count = job_counters.scheduled_count + %s, processing_count = job_counters.processing_count + 1, updated_at = NOW()"
                                    ),
                                    (d.get("domain"), d.get("queue"), d.get("job_type"), -1 if not is_sched else 0, -1 if is_sched else 0),
                                )
                        except Exception:
                            pass
                        try:
                            self._assert_invariants(d)
                        except Exception:
                            pass
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
                        try:
                            with job_span("job.acquire", job=d):
                                pass
                        except Exception:
                            pass
                        try:
                            emit_job_event(
                                "job.acquired",
                                job=d,
                                attrs={
                                    "worker_id": worker_id,
                                    "owner_user_id": d.get("owner_user_id"),
                                    "retry_count": int(d.get("retry_count") or 0),
                                },
                            )
                        except Exception:
                            pass
                        return d
            else:
                with conn:
                    # Optional one-shot acquisition path for SQLite to reduce contention
                    if str(os.getenv("JOBS_SQLITE_SINGLE_UPDATE_ACQUIRE", "")).lower() in {"1","true","yes","y","on"}:
                        lease_id = str(_uuid.uuid4())
                        sub = (
                            "SELECT id FROM jobs WHERE domain = ? AND queue = ? AND ("
                            "  (status = 'queued' AND (available_at IS NULL OR available_at <= DATETIME('now'))) OR"
                            "  (status = 'processing' AND (leased_until IS NULL OR leased_until <= DATETIME('now')))"
                            ")"
                        )
                        params_sub: List[Any] = [domain, queue]
                        if owner_user_id:
                            sub += " AND owner_user_id = ?"
                            params_sub.append(owner_user_id)
                        # Stable ordering mirrors Postgres path
                        sub += " ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, id ASC LIMIT 1"
                        sql = (
                            "UPDATE jobs SET status='processing', "
                            "started_at = COALESCE(started_at, DATETIME('now')), "
                            "acquired_at = COALESCE(acquired_at, DATETIME('now')), "
                            "leased_until = DATETIME('now', ?), worker_id = ?, lease_id = ? "
                            f"WHERE id IN ({sub})"
                        )
                        params_upd: List[Any] = [f"+{lease_seconds} seconds", worker_id, lease_id] + params_sub
                        conn.execute(sql, tuple(params_upd))
                        if conn.total_changes == 0:
                            return None
                        row = conn.execute("SELECT * FROM jobs WHERE lease_id = ?", (lease_id,)).fetchone()
                        if not row:
                            return None
                        d = dict(row)
                        try:
                            self._assert_invariants(d)
                        except Exception:
                            pass
                        # Counters queued->processing
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                is_sched = bool(d.get("available_at")) and (_parse_dt(d.get("available_at")) or datetime.utcnow()) > datetime.utcnow()
                                conn.execute(
                                    (
                                        "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?,?,?,?,?) "
                                        "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = ready_count + ?, scheduled_count = scheduled_count + ?, processing_count = processing_count + 1, updated_at = DATETIME('now')"
                                    ),
                                    (d.get("domain"), d.get("queue"), d.get("job_type"), 0,0,0,0, -1 if not is_sched else 0, -1 if is_sched else 0),
                                )
                        except Exception:
                            pass
                    else:
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
                        # Stable ordering mirrors Postgres path
                        base += " ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, id ASC LIMIT 1"
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
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                is_sched = bool(d.get("available_at")) and (_parse_dt(d.get("available_at")) or datetime.utcnow()) > datetime.utcnow()
                                conn.execute(
                                    (
                                        "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?,?,?,?,?) "
                                        "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = ready_count + ?, scheduled_count = scheduled_count + ?, processing_count = processing_count + 1, updated_at = DATETIME('now')"
                                    ),
                                    (d.get("domain"), d.get("queue"), d.get("job_type"), 0,0,0,0, -1 if not is_sched else 0, -1 if is_sched else 0),
                                )
                        except Exception:
                            pass
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
                    try:
                        with job_span("job.acquire", job=d):
                            pass
                    except Exception:
                        pass
                    try:
                        emit_job_event(
                            "job.acquired",
                            job=d,
                            attrs={
                                "worker_id": worker_id,
                                "owner_user_id": d.get("owner_user_id"),
                                "retry_count": int(d.get("retry_count") or 0),
                            },
                        )
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
        progress_percent: Optional[float] = None,
        progress_message: Optional[str] = None,
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
                            sets = ["leased_until = GREATEST(COALESCE(leased_until, NOW()), NOW() + (%s || ' seconds')::interval)"]
                            params: List[Any] = [int(seconds)]
                            if progress_percent is not None:
                                sets.append("progress_percent = %s")
                                params.append(float(progress_percent))
                            if progress_message is not None:
                                sets.append("progress_message = %s")
                                params.append(str(progress_message))
                            params.extend([int(job_id), worker_id, lease_id])
                            cur.execute(
                                f"UPDATE jobs SET {', '.join(sets)} WHERE id = %s AND status = 'processing' AND worker_id = %s AND lease_id = %s",
                                tuple(params),
                            )
                            ok = cur.rowcount > 0
                            if ok:
                                try:
                                    emit_job_event("job.lease_renewed", job={"id": int(job_id)}, attrs={"seconds": int(seconds)})
                                except Exception:
                                    pass
                            return ok
                        else:
                            sets = ["leased_until = GREATEST(COALESCE(leased_until, NOW()), NOW() + (%s || ' seconds')::interval)"]
                            params2: List[Any] = [int(seconds)]
                            if progress_percent is not None:
                                sets.append("progress_percent = %s")
                                params2.append(float(progress_percent))
                            if progress_message is not None:
                                sets.append("progress_message = %s")
                                params2.append(str(progress_message))
                            cur.execute(
                                f"UPDATE jobs SET {', '.join(sets)} WHERE id = %s AND status = 'processing'",
                                tuple(params2 + [int(job_id)]),
                            )
                            ok2 = cur.rowcount > 0
                            if ok2:
                                try:
                                    emit_job_event("job.lease_renewed", job={"id": int(job_id)}, attrs={"seconds": int(seconds)})
                                except Exception:
                                    pass
                            return ok2
            else:
                with conn:
                    interval = f"+{seconds} seconds"
                    if enforce:
                        # Do not shorten; cap to max(now+cap, current leased_until)
                        sql = (
                            "UPDATE jobs SET "
                            "leased_until = MAX(COALESCE(leased_until, DATETIME('now')), DATETIME('now', ?))"
                        )
                        params3: List[Any] = [interval]
                        if progress_percent is not None:
                            sql += ", progress_percent = ?"
                            params3.append(float(progress_percent))
                        if progress_message is not None:
                            sql += ", progress_message = ?"
                            params3.append(str(progress_message))
                        sql += " WHERE id = ? AND status = 'processing' AND worker_id = ? AND lease_id = ?"
                        params3.extend([job_id, worker_id, lease_id])
                        cur = conn.execute(sql, tuple(params3))
                        ok3 = (cur.rowcount or 0) > 0
                        if ok3:
                            try:
                                emit_job_event("job.lease_renewed", job={"id": int(job_id)}, attrs={"seconds": int(seconds)})
                            except Exception:
                                pass
                        return ok3
                    else:
                        sql = (
                            "UPDATE jobs SET "
                            "leased_until = MAX(COALESCE(leased_until, DATETIME('now')), DATETIME('now', ?))"
                        )
                        params4: List[Any] = [interval]
                        if progress_percent is not None:
                            sql += ", progress_percent = ?"
                            params4.append(float(progress_percent))
                        if progress_message is not None:
                            sql += ", progress_message = ?"
                            params4.append(str(progress_message))
                        sql += " WHERE id = ? AND status = 'processing'"
                        params4.append(job_id)
                        cur = conn.execute(sql, tuple(params4))
                        ok4 = (cur.rowcount or 0) > 0
                        if ok4:
                            try:
                                emit_job_event("job.lease_renewed", job={"id": int(job_id)}, attrs={"seconds": int(seconds)})
                            except Exception:
                                pass
                        return ok4
        finally:
            conn.close()

    def complete_job(
        self,
        job_id: int,
        *,
        result: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
        lease_id: Optional[str] = None,
        completion_token: Optional[str] = None,
        enforce: Optional[bool] = None,
    ) -> bool:
        """Mark a job as completed and clear the lease.

        See `renew_job_lease` for enforcement semantics.
        """
        # Strong exactly-once finalize (optional): require a completion_token when enabled
        if str(os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "")).lower() in {"1", "true", "yes", "y", "on"} and not completion_token:
            raise ValueError("completion_token required by JOBS_REQUIRE_COMPLETION_TOKEN")
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1", "true", "yes", "y", "on"}
        # Cap result size if configured
        max_bytes = int(os.getenv("JOBS_MAX_JSON_BYTES", "1048576") or "1048576")
        truncate = str(os.getenv("JOBS_JSON_TRUNCATE", "")).lower() in {"1", "true", "yes", "y", "on"}
        res_obj = result
        if res_obj is not None:
            # Serialize first; only catch serialization errors, not size checks
            try:
                res_json = json.dumps(res_obj)
            except (TypeError, ValueError):
                # Non-serializable results are handled by DB layer (stored as NULL or fail later)
                res_json = None
            if res_json is not None:
                res_bytes = len(res_json.encode("utf-8"))
                if res_bytes > max_bytes:
                    if truncate:
                        res_obj = {"_truncated": True, "len_bytes": res_bytes}
                    else:
                        raise ValueError(f"Result too large: {res_bytes} bytes > limit {max_bytes}")
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        # Pre-fetch for metrics and idempotency
                        cur.execute("SELECT status, completion_token, worker_id, lease_id, domain, queue, job_type, started_at, acquired_at, trace_id, request_id FROM jobs WHERE id = %s", (int(job_id),))
                        base = cur.fetchone()
                        if base:
                            st = str(base.get("status"))
                            ct = base.get("completion_token")
                            if st in {"completed", "failed", "cancelled", "quarantined"}:
                                # Idempotent acknowledgement when token matches
                                if completion_token and ct and str(ct) == str(completion_token):
                                    return True
                                return False
                        if enforce:
                            cur.execute(
                                (
                                    "UPDATE jobs SET status = 'completed', result = %s::jsonb, completed_at = NOW(), completion_token = %s, "
                                    "leased_until = NULL WHERE id = %s AND status = 'processing' AND worker_id = %s AND lease_id = %s AND (completion_token IS NULL OR completion_token = %s)"
                                ),
                                (json.dumps(res_obj) if res_obj is not None else None, completion_token, int(job_id), worker_id, lease_id, completion_token),
                            )
                            ok = cur.rowcount > 0
                            if not ok and completion_token:
                                # Idempotent retry if already completed with same token (race)
                                cur.execute("SELECT completion_token, status FROM jobs WHERE id = %s", (int(job_id),))
                                chk = cur.fetchone()
                                if chk and str(chk.get("completion_token") or "") == str(completion_token) and str(chk.get("status")) == "completed":
                                    return True
                            return ok
                        else:
                            cur.execute(
                                "UPDATE jobs SET status = 'completed', result = %s::jsonb, completed_at = NOW(), completion_token = COALESCE(completion_token, %s), leased_until = NULL WHERE id = %s AND status = 'processing' AND (completion_token IS NULL OR completion_token = %s)",
                                (json.dumps(res_obj) if res_obj is not None else None, completion_token, int(job_id), completion_token),
                            )
                            ok = cur.rowcount > 0
                        # Metrics: duration + counters
                        try:
                            if base and ok:
                                d = dict(base)
                                started_at = d.get("started_at") or d.get("acquired_at")
                                if isinstance(started_at, str):
                                    started_at = _parse_dt(started_at)
                                observe_duration({"domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type"), "trace_id": d.get("trace_id"), "request_id": d.get("request_id")}, started_at, datetime.utcnow())
                                # Update gauges after terminal state
                                increment_completed({"domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")})
                                self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                                try:
                                    with job_span("job.complete", job=d):
                                        pass
                                except Exception:
                                    pass
                                try:
                                    ev = {"id": int(job_id), "domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}
                                    emit_job_event("job.completed", job=ev)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return ok
            else:
                with conn:
                    # Pre-fetch for metrics + idempotency
                    rowm = conn.execute("SELECT status, completion_token, domain, queue, job_type, started_at, acquired_at, trace_id, request_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    if rowm:
                        st = str(rowm[0])
                        ct = rowm[1]
                        if st in {"completed", "failed", "cancelled", "quarantined"}:
                            if completion_token and ct and str(ct) == str(completion_token):
                                return True
                            return False
                    if enforce:
                        conn.execute(
                            (
                                "UPDATE jobs SET status = 'completed', result = ?, completed_at = DATETIME('now'), completion_token = ?, "
                                "leased_until = NULL WHERE id = ? AND status = 'processing' AND worker_id = ? AND lease_id = ? AND (completion_token IS NULL OR completion_token = ?)"
                            ),
                            (json.dumps(res_obj) if res_obj is not None else None, completion_token, job_id, worker_id, lease_id, completion_token),
                        )
                        ok = conn.total_changes > 0
                        if not ok and completion_token:
                            chk = conn.execute("SELECT completion_token, status FROM jobs WHERE id = ?", (job_id,)).fetchone()
                            if chk and str(chk[0] or "") == str(completion_token) and str(chk[1]) == "completed":
                                return True
                    else:
                        conn.execute(
                            (
                                "UPDATE jobs SET status = 'completed', result = ?, completed_at = DATETIME('now'), completion_token = COALESCE(completion_token, ?), leased_until = NULL "
                                "WHERE id = ? AND status = 'processing' AND (completion_token IS NULL OR completion_token = ?)"
                            ),
                            (json.dumps(res_obj) if res_obj is not None else None, completion_token, job_id, completion_token),
                        )
                        ok = conn.total_changes > 0
                    # Metrics: duration + counters
                    try:
                        if rowm and ok:
                            d = {
                                "domain": rowm[2],
                                "queue": rowm[3],
                                "job_type": rowm[4],
                                "started_at": rowm[5],
                                "acquired_at": rowm[6],
                                "trace_id": rowm[7] if len(rowm) > 7 else None,
                                "request_id": rowm[8] if len(rowm) > 8 else None,
                            }
                            s = _parse_dt(d.get("started_at")) or _parse_dt(d.get("acquired_at"))
                            observe_duration({"domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type"), "trace_id": d.get("trace_id"), "request_id": d.get("request_id")}, s, datetime.utcnow())
                            increment_completed({"domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")})
                            self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                            try:
                                with job_span("job.complete", job=d):
                                    pass
                            except Exception:
                                pass
                            try:
                                ev = {"id": int(job_id), "domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}
                                emit_job_event("job.completed", job=ev)
                            except Exception:
                                pass
                    except Exception:
                        pass
        return ok
        finally:
            conn.close()

    def _adaptive_lease_seconds(self, domain: str, queue: str, job_type: Optional[str]) -> int:
        """Compute adaptive lease seconds based on recent P95 durations with headroom.

        Works for both backends; uses percentile_cont on PG and a simple
        approximate percentile for SQLite.
        """
        headroom = float(os.getenv("JOBS_ADAPTIVE_LEASE_HEADROOM", "1.3") or "1.3")
        window_h = int(os.getenv("JOBS_ADAPTIVE_LEASE_WINDOW_HOURS", "6") or "6")
        min_s = int(os.getenv("JOBS_ADAPTIVE_LEASE_MIN_SECONDS", "15") or "15")
        max_s = int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600")
        value: Optional[float] = None
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    q = (
                        "SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (completed_at - COALESCE(started_at, acquired_at)))) AS p95 "
                        "FROM jobs WHERE completed_at IS NOT NULL AND created_at >= NOW() - (%s || ' hours')::interval AND domain=%s AND queue=%s"
                    )
                    params: List[Any] = [int(window_h), domain, queue]
                    if job_type:
                        q += " AND job_type=%s"; params.append(job_type)
                    cur.execute(q, tuple(params))
                    row = cur.fetchone()
                    if row and (row.get("p95") is not None):
                        value = float(row.get("p95"))
            else:
                query = (
                    "SELECT (julianday(completed_at) - julianday(COALESCE(started_at, acquired_at))) * 86400.0 AS dur "
                    "FROM jobs WHERE completed_at IS NOT NULL AND created_at >= DATETIME('now', ?) AND domain=? AND queue=?"
                )
                params2: List[Any] = [f"-{int(window_h)} hours", domain, queue]
                if job_type:
                    query += " AND job_type=?"; params2.append(job_type)
                vals = [float(r[0]) for r in conn.execute(query, tuple(params2)).fetchall() if r and r[0] is not None]
                if vals:
                    vals.sort()
                    idx = max(0, min(len(vals)-1, int(round(0.95 * (len(vals)-1)))))
                    value = float(vals[idx])
        finally:
            try:
                conn.close()
            except Exception:
                pass
        if not value or value <= 0:
            return max(min_s, 30)
        return max(min_s, min(max_s, int(value * headroom)))

    def batch_renew_leases(self, items: List[Dict[str, Any]], *, enforce: Optional[bool] = None) -> int:
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1","true","yes","y","on"}
        conn = self._connect()
        affected = 0
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        for it in items:
                            secs = max(1, min(int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600"), int(it.get("seconds") or 0)))
                            if enforce:
                                cur.execute(
                                    "UPDATE jobs SET leased_until = GREATEST(COALESCE(leased_until, NOW()), NOW() + (%s || ' seconds')::interval) WHERE id = %s AND status='processing' AND worker_id = %s AND lease_id = %s",
                                    (secs, int(it.get("job_id")), it.get("worker_id"), it.get("lease_id")),
                                )
                            else:
                                cur.execute(
                                    "UPDATE jobs SET leased_until = GREATEST(COALESCE(leased_until, NOW()), NOW() + (%s || ' seconds')::interval) WHERE id = %s AND status='processing'",
                                    (secs, int(it.get("job_id"))),
                                )
                            affected += cur.rowcount or 0
            else:
                with conn:
                    for it in items:
                        secs = max(1, min(int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600"), int(it.get("seconds") or 0)))
                        if enforce:
                            conn.execute(
                                "UPDATE jobs SET leased_until = MAX(COALESCE(leased_until, DATETIME('now')), DATETIME('now', ?)) WHERE id = ? AND status='processing' AND worker_id = ? AND lease_id = ?",
                                (f"+{secs} seconds", int(it.get("job_id")), it.get("worker_id"), it.get("lease_id")),
                            )
                        else:
                            conn.execute(
                                "UPDATE jobs SET leased_until = MAX(COALESCE(leased_until, DATETIME('now')), DATETIME('now', ?)) WHERE id = ? AND status='processing'",
                                (f"+{secs} seconds", int(it.get("job_id"))),
                            )
                        affected += conn.total_changes or 0
            return int(affected)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def batch_complete_jobs(self, items: List[Dict[str, Any]], *, enforce: Optional[bool] = None) -> int:
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1","true","yes","y","on"}
        conn = self._connect()
        done = 0
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        for it in items:
                            res_obj = it.get("result")
                            ctok = it.get("completion_token")
                            if enforce:
                                cur.execute(
                                    "UPDATE jobs SET status='completed', result=%s::jsonb, completed_at = NOW(), completion_token = %s, leased_until = NULL WHERE id=%s AND status='processing' AND worker_id=%s AND lease_id=%s AND (completion_token IS NULL OR completion_token = %s)",
                                    (json.dumps(res_obj) if res_obj is not None else None, ctok, int(it.get("job_id")), it.get("worker_id"), it.get("lease_id"), ctok),
                                )
                            else:
                                cur.execute(
                                    "UPDATE jobs SET status='completed', result=%s::jsonb, completed_at = NOW(), completion_token = COALESCE(completion_token, %s), leased_until = NULL WHERE id=%s AND status='processing' AND (completion_token IS NULL OR completion_token = %s)",
                                    (json.dumps(res_obj) if res_obj is not None else None, ctok, int(it.get("job_id")), ctok),
                                )
                            done += cur.rowcount or 0
            else:
                with conn:
                    for it in items:
                        res_obj = it.get("result")
                        ctok = it.get("completion_token")
                        if enforce:
                            conn.execute(
                                "UPDATE jobs SET status='completed', result=?, completed_at = DATETIME('now'), completion_token = ?, leased_until = NULL WHERE id = ? AND status='processing' AND worker_id = ? AND lease_id = ? AND (completion_token IS NULL OR completion_token = ?)",
                                (json.dumps(res_obj) if res_obj is not None else None, ctok, int(it.get("job_id")), it.get("worker_id"), it.get("lease_id"), ctok),
                            )
                        else:
                            conn.execute(
                                "UPDATE jobs SET status='completed', result=?, completed_at = DATETIME('now'), completion_token = COALESCE(completion_token, ?), leased_until = NULL WHERE id = ? AND status='processing' AND (completion_token IS NULL OR completion_token = ?)",
                                (json.dumps(res_obj) if res_obj is not None else None, ctok, int(it.get("job_id")), ctok),
                            )
                        done += conn.total_changes or 0
            return int(done)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def batch_fail_jobs(self, items: List[Dict[str, Any]], *, enforce: Optional[bool] = None) -> int:
        if str(os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "")).lower() in {"1","true","yes","y","on"}:
            for it in items:
                if not it.get("completion_token"):
                    raise ValueError("completion_token required by JOBS_REQUIRE_COMPLETION_TOKEN")
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1","true","yes","y","on"}
        conn = self._connect()
        cnt = 0
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        for it in items:
                            if enforce:
                                cur.execute(
                                    "UPDATE jobs SET status='failed', last_error=%s, error_message=%s, error_code=%s, completed_at=NOW(), leased_until=NULL, completion_token=%s WHERE id=%s AND status='processing' AND worker_id=%s AND lease_id=%s AND (completion_token IS NULL OR completion_token=%s)",
                                    (it.get("error_code") or it.get("error"), it.get("error"), it.get("error_code"), it.get("completion_token"), int(it.get("job_id")), it.get("worker_id"), it.get("lease_id"), it.get("completion_token")),
                                )
                            else:
                                cur.execute(
                                    "UPDATE jobs SET status='failed', last_error=%s, error_message=%s, error_code=%s, completed_at=NOW(), leased_until=NULL, completion_token=COALESCE(completion_token,%s) WHERE id=%s AND status='processing' AND (completion_token IS NULL OR completion_token=%s)",
                                    (it.get("error_code") or it.get("error"), it.get("error"), it.get("error_code"), it.get("completion_token"), int(it.get("job_id")), it.get("completion_token")),
                                )
                            cnt += cur.rowcount or 0
            else:
                with conn:
                    for it in items:
                        if enforce:
                            conn.execute(
                                "UPDATE jobs SET status='failed', last_error=?, error_message=?, error_code=?, completed_at=DATETIME('now'), leased_until=NULL, completion_token=? WHERE id=? AND status='processing' AND worker_id=? AND lease_id=? AND (completion_token IS NULL OR completion_token=?)",
                                (it.get("error_code") or it.get("error"), it.get("error"), it.get("error_code"), it.get("completion_token"), int(it.get("job_id")), it.get("worker_id"), it.get("lease_id"), it.get("completion_token")),
                            )
                        else:
                            conn.execute(
                                "UPDATE jobs SET status='failed', last_error=?, error_message=?, error_code=?, completed_at=DATETIME('now'), leased_until=NULL, completion_token=COALESCE(completion_token,?) WHERE id=? AND status='processing' AND (completion_token IS NULL OR completion_token=?)",
                                (it.get("error_code") or it.get("error"), it.get("error"), it.get("error_code"), it.get("completion_token"), int(it.get("job_id")), it.get("completion_token")),
                            )
                        cnt += conn.total_changes or 0
            return int(cnt)
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        error_code: Optional[str] = None,
        error_class: Optional[str] = None,
        error_stack: Optional[Dict[str, Any]] = None,
        completion_token: Optional[str] = None,
    ) -> bool:
        """Mark a job as failed; optionally reschedule with backoff if retryable.

        See `renew_job_lease` for enforcement semantics.
        """
        # Strong exactly-once finalize (optional): require a completion_token when enabled
        if str(os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "")).lower() in {"1", "true", "yes", "y", "on"} and not completion_token:
            raise ValueError("completion_token required by JOBS_REQUIRE_COMPLETION_TOKEN")
        import random
        if enforce is None:
            enforce = str(os.getenv("JOBS_ENFORCE_LEASE_ACK", "")).lower() in {"1", "true", "yes", "y", "on"}
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        # For metrics and idempotency
                        cur.execute("SELECT status, completion_token, retry_count, failure_streak_code, failure_streak_count, domain, queue, job_type FROM jobs WHERE id = %s", (int(job_id),))
                        elem = cur.fetchone()
                        if elem:
                            st = str(elem.get("status"))
                            ct = elem.get("completion_token")
                            if st in {"completed", "failed", "cancelled", "quarantined"}:
                                if completion_token and ct and str(ct) == str(completion_token):
                                    return True
                                return False
                        if retryable:
                            cur.execute("SELECT retry_count FROM jobs WHERE id = %s", (int(job_id),))
                            row = cur.fetchone()
                            current = int(row["retry_count"]) if row else 0
                            exp_backoff = max(1, int(backoff_seconds * (2 ** current)))
                            test_mode = str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "y", "on"}
                            if exp_backoff <= 2 or test_mode:
                                jitter = 0
                            else:
                                jitter = random.randint(0, max(1, exp_backoff // 4))
                            delay = exp_backoff + jitter
                            if test_mode and exp_backoff <= 1:
                                delay = 0
                            # Poison message quarantine check: increment failure_streak_* and quarantine if threshold reached
                            thresh = int(os.getenv("JOBS_QUARANTINE_THRESHOLD", "3") or "3")
                            # Update retry path with failure streak bookkeeping
                            if enforce:
                                cur.execute(
                                    (
                                        "UPDATE jobs SET status = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= %s THEN 'quarantined' ELSE 'queued' END, "
                                        "retry_count = retry_count + 1, last_error = %s, error_message = %s, error_code = %s, error_class = %s, error_stack = %s::jsonb, "
                                        "failure_streak_code = CASE WHEN error_code = %s THEN error_code ELSE %s END, "
                                        "failure_streak_count = CASE WHEN error_code = %s THEN COALESCE(failure_streak_count,0) + 1 ELSE 1 END, "
                                        "available_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= %s THEN available_at ELSE NOW() + (%s || ' seconds')::interval END, "
                                        "quarantined_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= %s THEN NOW() ELSE quarantined_at END, "
                                        "leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                        "WHERE id = %s AND status = 'processing' AND retry_count < max_retries AND worker_id = %s AND lease_id = %s"
                                    ),
                                    (
                                        int(thresh),
                                        (error_code or error),
                                        error,
                                        error_code,
                                        error_class,
                                        (json.dumps(error_stack) if error_stack is not None else None),
                                        error_code,
                                        error_code,
                                        error_code,
                                        int(thresh),
                                        int(delay),
                                        int(thresh),
                                        int(job_id),
                                        worker_id,
                                        lease_id,
                                    ),
                                )
                            else:
                                cur.execute(
                                    (
                                        "UPDATE jobs SET status = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= %s THEN 'quarantined' ELSE 'queued' END, "
                                        "retry_count = retry_count + 1, last_error = %s, error_message = %s, error_code = %s, error_class = %s, error_stack = %s::jsonb, "
                                        "failure_streak_code = CASE WHEN error_code = %s THEN error_code ELSE %s END, "
                                        "failure_streak_count = CASE WHEN error_code = %s THEN COALESCE(failure_streak_count,0) + 1 ELSE 1 END, "
                                        "available_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= %s THEN available_at ELSE NOW() + (%s || ' seconds')::interval END, "
                                        "quarantined_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= %s THEN NOW() ELSE quarantined_at END, "
                                        "leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                        "WHERE id = %s AND status = 'processing' AND retry_count < max_retries"
                                    ),
                                    (
                                        int(thresh),
                                        (error_code or error),
                                        error,
                                        error_code,
                                        error_class,
                                        (json.dumps(error_stack) if error_stack is not None else None),
                                        error_code,
                                        error_code,
                                        error_code,
                                        int(thresh),
                                        int(delay),
                                        int(thresh),
                                        int(job_id),
                                    ),
                                )
                            if cur.rowcount > 0:
                                try:
                                    if elem:
                                        increment_retries(dict(elem))
                                        try:
                                            from .metrics import observe_retry_after
                                            observe_retry_after(dict(elem), float(delay))
                                        except Exception:
                                            pass
                                        try:
                                            ev = {"id": int(job_id), "domain": elem.get("domain"), "queue": elem.get("queue"), "job_type": elem.get("job_type")}
                                            emit_job_event(
                                                "job.retry_scheduled",
                                                job=ev,
                                                attrs={
                                                    "backoff_seconds": int(delay),
                                                    "error_code": (error_code or error),
                                                    "retry_count": int(current + 1),
                                                },
                                            )
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                return True
                        # terminal failure
                        if enforce:
                            cur.execute(
                                (
                                    "UPDATE jobs SET status = 'failed', last_error = %s, error_message = %s, error_code = %s, error_class = %s, error_stack = %s::jsonb, completion_token = %s, "
                                    "completed_at = NOW(), leased_until = NULL WHERE id = %s AND status = 'processing' AND worker_id = %s AND lease_id = %s AND (completion_token IS NULL OR completion_token = %s)"
                                ),
                                (
                                    (error_code or error),
                                    error,
                                    error_code,
                                    error_class,
                                    (json.dumps(error_stack) if error_stack is not None else None),
                                    completion_token,
                                    int(job_id),
                                    worker_id,
                                    lease_id,
                                    completion_token,
                                ),
                            )
                        else:
                            cur.execute(
                                (
                                    "UPDATE jobs SET status = 'failed', last_error = %s, error_message = %s, error_code = %s, error_class = %s, error_stack = %s::jsonb, completion_token = COALESCE(completion_token, %s), "
                                    "completed_at = NOW(), leased_until = NULL WHERE id = %s AND status = 'processing' AND (completion_token IS NULL OR completion_token = %s)"
                                ),
                                (
                                    (error_code or error),
                                    error,
                                    error_code,
                                    error_class,
                                    (json.dumps(error_stack) if error_stack is not None else None),
                                    completion_token,
                                    int(job_id),
                                    completion_token,
                                ),
                            )
                        ok = cur.rowcount > 0
                        try:
                            if ok and elem:
                                d = dict(elem)
                                increment_failures(d, reason="terminal")
                                try:
                                    if error_code:
                                        from .metrics import increment_failures_by_code
                                        increment_failures_by_code(d, error_code)
                                except Exception:
                                    pass
                                try:
                                    # Append terminal failure to timeline (no backoff)
                                    try:
                                        cur.execute(
                                            "UPDATE jobs SET failure_timeline = COALESCE(failure_timeline, '[]'::jsonb) || jsonb_build_array(jsonb_build_object('ts', NOW(), 'error_code', %s, 'retry_backoff', 0)) WHERE id = %s",
                                            ((error_code or error), int(job_id)),
                                        )
                                    except Exception:
                                        pass
                                    
                                    with job_span("job.fail", job=d, attrs={"retryable": False, "error_code": error_code}):
                                        pass
                                except Exception:
                                    pass
                                self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                                try:
                                    ev = {"id": int(job_id), "domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}
                                    emit_job_event("job.failed", job=ev, attrs={"error_code": (error_code or error)})
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return ok
            else:
                with conn:
                    # For metrics, fetch labels
                    rowl = conn.execute("SELECT status, completion_token, domain, queue, job_type FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    if rowl:
                        st = str(rowl[0])
                        ct = rowl[1]
                        if st in {"completed", "failed", "cancelled", "quarantined"}:
                            if completion_token and ct and str(ct) == str(completion_token):
                                return True
                            return False
                    if retryable:
                        # compute jittered backoff based on current retry_count
                        row = conn.execute("SELECT retry_count FROM jobs WHERE id = ?", (job_id,)).fetchone()
                        current = int(row[0]) if row else 0
                        exp_backoff = max(1, int(backoff_seconds * (2 ** current)))
                        test_mode = str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "y", "on"}
                        if exp_backoff <= 2 or test_mode:
                            jitter = 0
                        else:
                            jitter = random.randint(0, max(1, exp_backoff // 4))
                        delay = exp_backoff + jitter
                        if test_mode and exp_backoff <= 1:
                            delay = 0
                        thresh = int(os.getenv("JOBS_QUARANTINE_THRESHOLD", "3") or "3")
                        # SQLite retry path with failure streak bookkeeping
                        if enforce:
                            conn.execute(
                                (
                                    "UPDATE jobs SET status = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN 'quarantined' ELSE 'queued' END, "
                                    "retry_count = retry_count + 1, last_error = ?, error_message = ?, error_code = ?, error_class = ?, error_stack = ?, "
                                    "failure_streak_code = CASE WHEN error_code = ? THEN error_code ELSE ? END, "
                                    "failure_streak_count = CASE WHEN error_code = ? THEN COALESCE(failure_streak_count,0) + 1 ELSE 1 END, "
                                    "available_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN available_at ELSE DATETIME('now', ?) END, "
                                    "quarantined_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN DATETIME('now') ELSE quarantined_at END, "
                                    "leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                    "WHERE id = ? AND status = 'processing' AND retry_count < max_retries AND worker_id = ? AND lease_id = ?"
                                ),
                                (
                                    int(thresh),
                                    (error_code or error),
                                    error,
                                    error_code,
                                    error_class,
                                    (json.dumps(error_stack) if error_stack is not None else None),
                                    error_code,
                                    error_code,
                                    error_code,
                                    int(thresh),
                                    f"+{delay} seconds",
                                    int(thresh),
                                    job_id,
                                    worker_id,
                                    lease_id,
                                ),
                            )
                        else:
                            conn.execute(
                                (
                                    "UPDATE jobs SET status = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN 'quarantined' ELSE 'queued' END, "
                                    "retry_count = retry_count + 1, last_error = ?, error_message = ?, error_code = ?, error_class = ?, error_stack = ?, "
                                    "failure_streak_code = CASE WHEN error_code = ? THEN error_code ELSE ? END, "
                                    "failure_streak_count = CASE WHEN error_code = ? THEN COALESCE(failure_streak_count,0) + 1 ELSE 1 END, "
                                    "available_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN available_at ELSE DATETIME('now', ?) END, "
                                    "quarantined_at = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN DATETIME('now') ELSE quarantined_at END, "
                                    "leased_until = NULL, worker_id = NULL, lease_id = NULL "
                                    "WHERE id = ? AND status = 'processing' AND retry_count < max_retries"
                                ),
                                (
                                    int(thresh),
                                    (error_code or error),
                                    error,
                                    error_code,
                                    error_class,
                                    (json.dumps(error_stack) if error_stack is not None else None),
                                    error_code,
                                    error_code,
                                    error_code,
                                    int(thresh),
                                    f"+{delay} seconds",
                                    int(thresh),
                                    job_id,
                                ),
                            )
                        if conn.total_changes > 0:
                            try:
                                if rowl:
                                    dtmp = dict(rowl)
                                    increment_retries(dtmp)
                                    try:
                                        from .metrics import observe_retry_after
                                        observe_retry_after(dtmp, float(delay))
                                    except Exception:
                                        pass
                                    try:
                                        ev = {"id": int(job_id), "domain": dtmp.get("domain"), "queue": dtmp.get("queue"), "job_type": dtmp.get("job_type")}
                                        emit_job_event(
                                            "job.retry_scheduled",
                                            job=ev,
                                            attrs={
                                                "backoff_seconds": int(delay),
                                                "error_code": (error_code or error),
                                                "retry_count": int(current + 1),
                                            },
                                        )
                                    except Exception:
                                        pass
                                    # Append to failure_timeline
                                    try:
                                        row_t = conn.execute("SELECT failure_timeline FROM jobs WHERE id = ?", (job_id,)).fetchone()
                                        timeline_json = row_t[0] if row_t else None
                                        try:
                                            tl = json.loads(timeline_json) if timeline_json else []
                                        except Exception:
                                            tl = []
                                        tl.append({"ts": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), "error_code": (error_code or error), "retry_backoff": int(delay)})
                                        tl = tl[-10:]
                                        conn.execute("UPDATE jobs SET failure_timeline = ? WHERE id = ?", (json.dumps(tl), int(job_id)))
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            return True
                    # terminal failure
                    if enforce:
                        conn.execute(
                            (
                                "UPDATE jobs SET status = 'failed', last_error = ?, error_message = ?, error_code = ?, error_class = ?, error_stack = ?, completion_token = ?, "
                                "completed_at = DATETIME('now'), leased_until = NULL WHERE id = ? AND status = 'processing' AND worker_id = ? AND lease_id = ? AND (completion_token IS NULL OR completion_token = ?)"
                            ),
                            (
                                (error_code or error),
                                error,
                                error_code,
                                error_class,
                                (json.dumps(error_stack) if error_stack is not None else None),
                                completion_token,
                                job_id,
                                worker_id,
                                lease_id,
                                completion_token,
                            ),
                        )
                    else:
                        conn.execute(
                            (
                                "UPDATE jobs SET status = 'failed', last_error = ?, error_message = ?, error_code = ?, error_class = ?, error_stack = ?, completion_token = COALESCE(completion_token, ?), "
                                "completed_at = DATETIME('now'), leased_until = NULL WHERE id = ? AND status = 'processing' AND (completion_token IS NULL OR completion_token = ?)"
                            ),
                            (
                                (error_code or error),
                                error,
                                error_code,
                                error_class,
                                (json.dumps(error_stack) if error_stack is not None else None),
                                completion_token,
                                job_id,
                                completion_token,
                            ),
                        )
                    ok = conn.total_changes > 0
                    try:
                        if ok and rowl:
                            d = dict(rowl)
                            increment_failures(d, reason="terminal")
                            try:
                                if error_code:
                                    from .metrics import increment_failures_by_code
                                    increment_failures_by_code(d, error_code)
                            except Exception:
                                pass
                            # Append terminal failure to timeline (no backoff)
                            try:
                                row_t2 = conn.execute("SELECT failure_timeline FROM jobs WHERE id = ?", (job_id,)).fetchone()
                                timeline_json2 = row_t2[0] if row_t2 else None
                                try:
                                    tl2 = json.loads(timeline_json2) if timeline_json2 else []
                                except Exception:
                                    tl2 = []
                                tl2.append({"ts": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), "error_code": (error_code or error), "retry_backoff": 0})
                                tl2 = tl2[-10:]
                                conn.execute("UPDATE jobs SET failure_timeline = ? WHERE id = ?", (json.dumps(tl2), int(job_id)))
                            except Exception:
                                pass
                            try:
                                with job_span("job.fail", job=d, attrs={"retryable": False, "error_code": error_code}):
                                    pass
                            except Exception:
                                pass
                            self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                            try:
                                ev = {"id": int(job_id), "domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}
                                emit_job_event("job.failed", job=ev, attrs={"error_code": (error_code or error)})
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return ok
        finally:
            conn.close()

    def cancel_job(self, job_id: int, *, reason: Optional[str] = None) -> bool:
        """Request cancellation or cancel queued jobs immediately.

        Emits gauge updates on successful cancellation for the job's domain/queue/job_type.
        """
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        # Capture grouping keys for gauges
                        try:
                            cur.execute("SELECT domain, queue, job_type FROM jobs WHERE id = %s", (int(job_id),))
                            row0 = cur.fetchone()
                        except Exception:
                            row0 = None
                        cur.execute(
                            "UPDATE jobs SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = %s WHERE id = %s AND status = 'queued'",
                            (reason, int(job_id)),
                        )
                        if cur.rowcount > 0:
                            try:
                                if row0:
                                    self._update_gauges(domain=row0["domain"], queue=row0["queue"], job_type=row0["job_type"])
                                    increment_cancelled(dict(row0))
                            except Exception:
                                pass
                            try:
                                if row0:
                                    ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                                    emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                            except Exception:
                                pass
                            return True
                        # Terminally cancel processing jobs as well (more responsive semantics)
                        cur.execute(
                            "UPDATE jobs SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = %s, leased_until = NULL WHERE id = %s AND status = 'processing'",
                            (reason, int(job_id)),
                        )
                        ok = cur.rowcount > 0
                        try:
                            if ok and row0:
                                self._update_gauges(domain=row0["domain"], queue=row0["queue"], job_type=row0["job_type"])
                                increment_cancelled(dict(row0))
                        except Exception:
                            pass
                        try:
                            if ok and row0:
                                ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                                emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                        except Exception:
                            pass
                        return ok
            else:
                with conn:
                    # Capture grouping keys for gauges
                    try:
                        row0 = conn.execute("SELECT domain, queue, job_type FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    except Exception:
                        row0 = None
                    # cancel queued immediately
                    conn.execute(
                        "UPDATE jobs SET status = 'cancelled', cancelled_at = DATETIME('now'), cancellation_reason = ? WHERE id = ? AND status = 'queued'",
                        (reason, job_id),
                    )
                    if conn.total_changes > 0:
                        try:
                            if row0:
                                self._update_gauges(domain=row0["domain"], queue=row0["queue"], job_type=row0["job_type"])
                                increment_cancelled(dict(row0))
                        except Exception:
                            pass
                        try:
                            if row0:
                                ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                                emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                        except Exception:
                            pass
                        return True
                    # Terminally cancel processing jobs as well (more responsive semantics)
                    conn.execute(
                        "UPDATE jobs SET status = 'cancelled', cancelled_at = DATETIME('now'), cancellation_reason = ?, leased_until = NULL WHERE id = ? AND status = 'processing'",
                        (reason, job_id),
                    )
                    ok = conn.total_changes > 0
                    try:
                        if ok and row0:
                            self._update_gauges(domain=row0["domain"], queue=row0["queue"], job_type=row0["job_type"])
                            increment_cancelled(dict(row0))
                    except Exception:
                        pass
                    try:
                        if ok and row0:
                            ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                            emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                    except Exception:
                        pass
                    return ok
        finally:
            conn.close()

    # Maintenance
    def prune_jobs(
        self,
        *,
        statuses: Optional[List[str]] = None,
        older_than_days: int = 30,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
        dry_run: bool = False,
        detail_top_k: int = 0,
    ) -> int:
        """Delete (or count via dry_run) jobs in given statuses older than the threshold.

        Uses completed_at when present; otherwise falls back to created_at.
        Optional filters (domain, queue, job_type) scope the prune to a subset.
        Returns the number of affected rows (or the count for dry_run).
        """
        statuses = statuses or ["completed", "failed", "cancelled"]
        if not statuses:
            return 0
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        where_parts: List[str] = []
                        params: List[Any] = []
                        # statuses
                        placeholders = ",".join(["%s"] * len(statuses))
                        where_parts.append(f"status IN ({placeholders})")
                        params.extend(statuses)
                        # date threshold
                        where_parts.append("COALESCE(completed_at, created_at) <= NOW() - (%s || ' days')::interval")
                        params.append(int(older_than_days))
                        # optional filters
                        if domain:
                            where_parts.append("domain = %s")
                            params.append(domain)
                        if queue:
                            where_parts.append("queue = %s")
                            params.append(queue)
                        if job_type:
                            where_parts.append("job_type = %s")
                            params.append(job_type)
                        where_clause = " WHERE " + " AND ".join(where_parts)
                        if dry_run and detail_top_k > 0:
                            cur.execute(
                                (
                                    f"SELECT domain, queue, job_type, status, COUNT(*) AS c FROM jobs{where_clause} "
                                    "GROUP BY domain, queue, job_type, status ORDER BY c DESC LIMIT %s"
                                ),
                                tuple(params + [int(detail_top_k)]),
                            )
                            # Note: caller doesn't consume this form currently; kept for future extension
                            # We still return the total count below for compatibility
                        if dry_run:
                            cur.execute(f"SELECT COUNT(*) AS c FROM jobs{where_clause}", tuple(params))
                            row = cur.fetchone()
                            return int(row["c"]) if row is not None else 0
                        # Optional archive copy
                        if str(os.getenv("JOBS_ARCHIVE_BEFORE_DELETE", "")).lower() in {"1","true","yes","y","on"}:
                            cur.execute(
                                f"INSERT INTO jobs_archive (id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at) SELECT id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at FROM jobs{where_clause}",
                                tuple(params),
                            )
                        cur.execute(f"DELETE FROM jobs{where_clause}", tuple(params))
                        deleted = cur.rowcount or 0
                        try:
                            emit_job_event(
                                "jobs.pruned",
                                job=None,
                                attrs={
                                    "deleted": int(deleted),
                                    "dry_run": False,
                                    "statuses": ",".join(statuses),
                                    "older_than_days": int(older_than_days),
                                    "domain": domain,
                                    "queue": queue,
                                    "job_type": job_type,
                                },
                            )
                        except Exception:
                            pass
                        return deleted
            else:
                with conn:
                    where_parts: List[str] = []
                    params: List[Any] = []
                    placeholders = ",".join(["?"] * len(statuses))
                    where_parts.append(f"status IN ({placeholders})")
                    params.extend(statuses)
                    # Use julianday() for robust comparisons across string dates
                    where_parts.append("julianday(COALESCE(completed_at, created_at)) <= julianday('now', ?)")
                    params.append(f"-{int(older_than_days)} days")
                    if domain:
                        where_parts.append("domain = ?")
                        params.append(domain)
                    if queue:
                        where_parts.append("queue = ?")
                        params.append(queue)
                    if job_type:
                        where_parts.append("job_type = ?")
                        params.append(job_type)
                    where_clause = " WHERE " + " AND ".join(where_parts)
                    # Diagnostics in TEST_MODE: show which rows match the prune filter (SQLite)
                    try:
                        if str(os.getenv("TEST_MODE", "")).lower() in {"1", "true", "yes", "y", "on"}:
                            dbg_rows = conn.execute(
                                f"SELECT id, status, completed_at, created_at FROM jobs{where_clause}",
                                tuple(params),
                            ).fetchall()
                            all_rows = conn.execute("SELECT id, status, completed_at, created_at FROM jobs", ()).fetchall()
                            logger.debug(
                                f"SQLite prune debug: total={len(all_rows)} sample={[tuple(r) for r in all_rows]}"
                            )
                            logger.debug(
                                f"SQLite prune debug: matches={len(dbg_rows)} statuses={statuses} older_than_days={older_than_days} ids={[int(r[0]) for r in dbg_rows]}"
                            )
                    except Exception:
                        pass
                    # Compute match count up front for accurate reporting
                    cur_cnt = conn.execute(f"SELECT COUNT(*) FROM jobs{where_clause}", tuple(params))
                    row = cur_cnt.fetchone()
                    count = int(row[0]) if row is not None else 0
                    if dry_run:
                        try:
                            emit_job_event(
                                "jobs.pruned",
                                job=None,
                                attrs={
                                    "deleted": int(count),
                                    "dry_run": True,
                                    "statuses": ",".join(statuses),
                                    "older_than_days": int(older_than_days),
                                    "domain": domain,
                                    "queue": queue,
                                    "job_type": job_type,
                                },
                            )
                        except Exception:
                            pass
                        return count
                    # Optional archive copy
                    if str(os.getenv("JOBS_ARCHIVE_BEFORE_DELETE", "")).lower() in {"1","true","yes","y","on"}:
                        conn.execute(
                            f"INSERT INTO jobs_archive (id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at) SELECT id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at FROM jobs{where_clause}",
                            tuple(params),
                        )
                    conn.execute(f"DELETE FROM jobs{where_clause}", tuple(params))
                    deleted = int(count)
                    try:
                        emit_job_event(
                            "jobs.pruned",
                            job=None,
                            attrs={
                                "deleted": int(deleted),
                                "dry_run": False,
                                "statuses": ",".join(statuses),
                                "older_than_days": int(older_than_days),
                                "domain": domain,
                                "queue": queue,
                                "job_type": job_type,
                            },
                        )
                    except Exception:
                        pass
                    return deleted
        finally:
            conn.close()

    def apply_ttl_policies(
        self,
        *,
        age_seconds: Optional[int] = None,
        runtime_seconds: Optional[int] = None,
        action: str = "cancel",
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> int:
        """Apply TTL policies for queued/scheduled (age) and processing (runtime).

        Returns the number of rows affected.
        """
        if action not in {"cancel", "fail"}:
            raise ValueError("action must be 'cancel' or 'fail'")
        age_seconds = (int(age_seconds) if age_seconds is not None else None)
        runtime_seconds = (int(runtime_seconds) if runtime_seconds is not None else None)
        if age_seconds is None and runtime_seconds is None:
            return 0
        conn = self._connect()
        try:
            if self.backend == "postgres":
                # Ensure updates are committed
                with conn:
                    with self._pg_cursor(conn) as cur:
                        affected = 0
                        if age_seconds is not None:
                            where = ["status='queued'", f"created_at <= NOW() - ({int(age_seconds)} || ' seconds')::interval"]
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
                            if action == "cancel":
                                cur.execute(
                                    f"UPDATE jobs SET status='cancelled', cancelled_at = NOW(), cancellation_reason = 'ttl_age' WHERE {' AND '.join(where)}",
                                    tuple(params),
                                )
                            else:
                                cur.execute(
                                    f"UPDATE jobs SET status='failed', error_message = 'ttl_age', completed_at = NOW() WHERE {' AND '.join(where)}",
                                    tuple(params),
                                )
                            affected += cur.rowcount or 0
                        if runtime_seconds is not None:
                            where = ["status='processing'", f"COALESCE(started_at, acquired_at) <= NOW() - ({int(runtime_seconds)} || ' seconds')::interval"]
                            params2: List[Any] = []
                            if domain:
                                where.append("domain = %s")
                                params2.append(domain)
                            if queue:
                                where.append("queue = %s")
                                params2.append(queue)
                            if job_type:
                                where.append("job_type = %s")
                                params2.append(job_type)
                            if action == "cancel":
                                cur.execute(
                                    f"UPDATE jobs SET status='cancelled', cancelled_at = NOW(), cancellation_reason = 'ttl_runtime', leased_until = NULL WHERE {' AND '.join(where)}",
                                    tuple(params2),
                                )
                            else:
                                cur.execute(
                                    f"UPDATE jobs SET status='failed', error_message = 'ttl_runtime', completed_at = NOW(), leased_until = NULL WHERE {' AND '.join(where)}",
                                    tuple(params2),
                                )
                            affected += cur.rowcount or 0
                        try:
                            emit_job_event(
                                "jobs.ttl_sweep",
                                job=None,
                                attrs={
                                    "affected": int(affected),
                                    "action": action,
                                    "age_seconds": int(age_seconds or 0),
                                    "runtime_seconds": int(runtime_seconds or 0),
                                    "domain": domain,
                                    "queue": queue,
                                    "job_type": job_type,
                                },
                            )
                        except Exception:
                            pass
                        return affected
            else:
                # Ensure updates are committed by using an explicit transaction block
                affected2 = 0
                with conn:
                    if age_seconds is not None:
                        where = ["status='queued'", "created_at <= DATETIME('now', ?)" ]
                        params3: List[Any] = [f"-{int(age_seconds)} seconds"]
                        if domain:
                            where.append("domain = ?")
                            params3.append(domain)
                        if queue:
                            where.append("queue = ?")
                            params3.append(queue)
                        if job_type:
                            where.append("job_type = ?")
                            params3.append(job_type)
                        sql = "UPDATE jobs SET " + ("status='cancelled', cancelled_at = DATETIME('now'), cancellation_reason='ttl_age'" if action == "cancel" else "status='failed', error_message='ttl_age', completed_at = DATETIME('now')") + f" WHERE {' AND '.join(where)}"
                        cur = conn.execute(sql, tuple(params3))
                        try:
                            logger.debug(f"TTL(age) SQLite updated rows={cur.rowcount} for where={where} params={params3}")
                        except Exception:
                            pass
                        affected2 += cur.rowcount or 0
                    if runtime_seconds is not None:
                        where = ["status='processing'", "COALESCE(started_at, acquired_at) <= DATETIME('now', ?)"]
                        params4: List[Any] = [f"-{int(runtime_seconds)} seconds"]
                        if domain:
                            where.append("domain = ?")
                            params4.append(domain)
                        if queue:
                            where.append("queue = ?")
                            params4.append(queue)
                        if job_type:
                            where.append("job_type = ?")
                            params4.append(job_type)
                        sql2 = "UPDATE jobs SET " + ("status='cancelled', cancelled_at = DATETIME('now'), cancellation_reason='ttl_runtime', leased_until = NULL" if action == "cancel" else "status='failed', error_message='ttl_runtime', completed_at = DATETIME('now'), leased_until = NULL") + f" WHERE {' AND '.join(where)}"
                        cur2 = conn.execute(sql2, tuple(params4))
                        try:
                            logger.debug(f"TTL(runtime) SQLite updated rows={cur2.rowcount} for where={where} params={params4}")
                        except Exception:
                            pass
                        affected2 += cur2.rowcount or 0
                try:
                    emit_job_event(
                        "jobs.ttl_sweep",
                        job=None,
                        attrs={
                            "affected": int(affected2),
                            "action": action,
                            "age_seconds": int(age_seconds or 0),
                            "runtime_seconds": int(runtime_seconds or 0),
                            "domain": domain,
                            "queue": queue,
                            "job_type": job_type,
                        },
                    )
                except Exception:
                    pass
                return affected2
        finally:
            conn.close()

    def acquire_next_jobs(
        self,
        *,
        domain: str,
        queue: str,
        lease_seconds: int,
        worker_id: str,
        owner_user_id: Optional[str] = None,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """Acquire up to `limit` jobs. Simple loop over acquire_next_job for now."""
        limit = max(1, int(limit))
        out: List[Dict[str, Any]] = []
        for _ in range(limit):
            j = self.acquire_next_job(domain=domain, queue=queue, lease_seconds=lease_seconds, worker_id=worker_id, owner_user_id=owner_user_id)
            if not j:
                break
            out.append(j)
        return out

    def get_queue_stats(
        self,
        *,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return counts grouped by domain/queue/job_type.

        Provides queued (ready), scheduled, and processing counts per group.
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
                    "SUM(CASE WHEN status='queued' AND (available_at IS NULL OR available_at <= NOW()) THEN 1 ELSE 0 END) AS queued, "
                    "SUM(CASE WHEN status='queued' AND (available_at IS NOT NULL AND available_at > NOW()) THEN 1 ELSE 0 END) AS scheduled, "
                    "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing, "
                    "SUM(CASE WHEN status='quarantined' THEN 1 ELSE 0 END) AS quarantined "
                    f"FROM jobs WHERE {' AND '.join(where)} GROUP BY domain, queue, job_type ORDER BY domain, queue, job_type"
                )
                with self._pg_cursor(conn) as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                return [
                    {
                        "domain": r["domain"],
                        "queue": r["queue"],
                        "job_type": r["job_type"],
                        "queued": int((r.get("queued") if isinstance(r, dict) else 0) or 0),
                        "scheduled": int((r.get("scheduled") if isinstance(r, dict) else 0) or 0),
                        "processing": int((r.get("processing") if isinstance(r, dict) else 0) or 0),
                        "quarantined": int((r.get("quarantined") if isinstance(r, dict) else 0) or 0),
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
                    "SUM(CASE WHEN status='queued' AND (available_at IS NULL OR available_at <= DATETIME('now')) THEN 1 ELSE 0 END) AS queued, "
                    "SUM(CASE WHEN status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME('now')) THEN 1 ELSE 0 END) AS scheduled, "
                    "SUM(CASE WHEN status='processing' THEN 1 ELSE 0 END) AS processing, "
                    "SUM(CASE WHEN status='quarantined' THEN 1 ELSE 0 END) AS quarantined "
                    f"FROM jobs WHERE {' AND '.join(where)} GROUP BY domain, queue, job_type ORDER BY domain, queue, job_type"
                )
                rows = conn.execute(sql, params2).fetchall()
                return [
                    {
                        "domain": r[0],
                        "queue": r[1],
                        "job_type": r[2],
                        "queued": int(r[3] or 0),
                        "scheduled": int(r[4] or 0),
                        "processing": int(r[5] or 0),
                        "quarantined": int(r[6] or 0),
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

    def integrity_sweep(
        self,
        *,
        fix: bool = False,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> Dict[str, int]:
        """Validate and optionally repair impossible states.

        - non_processing_with_lease: status != processing but lease_id/worker_id/leased_until set
        - processing_expired: processing with missing/expired lease
        If fix=True, clears stale lease fields on non-processing and resets expired processing to queued.
        """
        conn = self._connect()
        try:
            res = {"non_processing_with_lease": 0, "processing_expired": 0, "fixed": 0}
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    where_np = ["status <> 'processing'", "(lease_id IS NOT NULL OR worker_id IS NOT NULL OR leased_until IS NOT NULL)"]
                    where_pr = ["status = 'processing'", "(leased_until IS NULL OR leased_until <= NOW())"]
                    params_np: List[Any] = []
                    params_pr: List[Any] = []
                    if domain:
                        where_np.append("domain = %s"); params_np.append(domain)
                        where_pr.append("domain = %s"); params_pr.append(domain)
                    if queue:
                        where_np.append("queue = %s"); params_np.append(queue)
                        where_pr.append("queue = %s"); params_pr.append(queue)
                    if job_type:
                        where_np.append("job_type = %s"); params_np.append(job_type)
                        where_pr.append("job_type = %s"); params_pr.append(job_type)
                    cur.execute(f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where_np)}", tuple(params_np))
                    res["non_processing_with_lease"] = int(cur.fetchone()[0])
                    cur.execute(f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where_pr)}", tuple(params_pr))
                    res["processing_expired"] = int(cur.fetchone()[0])
                    if fix:
                        # Clear leases for non-processing
                        cur.execute(
                            f"UPDATE jobs SET lease_id = NULL, leased_until = NULL, worker_id = NULL WHERE {' AND '.join(where_np)}",
                            tuple(params_np),
                        )
                        res["fixed"] += cur.rowcount or 0
                        # Reset expired processing to queued
                        cur.execute(
                            f"UPDATE jobs SET status='queued', leased_until = NULL, worker_id = NULL, lease_id = NULL WHERE {' AND '.join(where_pr)}",
                            tuple(params_pr),
                        )
                        res["fixed"] += cur.rowcount or 0
            else:
                where_np = ["status <> 'processing'", "(lease_id IS NOT NULL OR worker_id IS NOT NULL OR leased_until IS NOT NULL)"]
                where_pr = ["status = 'processing'", "(leased_until IS NULL OR leased_until <= DATETIME('now'))"]
                params_np: List[Any] = []
                params_pr: List[Any] = []
                if domain:
                    where_np.append("domain = ?"); params_np.append(domain)
                    where_pr.append("domain = ?"); params_pr.append(domain)
                if queue:
                    where_np.append("queue = ?"); params_np.append(queue)
                    where_pr.append("queue = ?"); params_pr.append(queue)
                if job_type:
                    where_np.append("job_type = ?"); params_np.append(job_type)
                    where_pr.append("job_type = ?"); params_pr.append(job_type)
                cur = conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where_np)}", tuple(params_np))
                res["non_processing_with_lease"] = int(cur.fetchone()[0])
                cur2 = conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where_pr)}", tuple(params_pr))
                res["processing_expired"] = int(cur2.fetchone()[0])
                if fix:
                    with conn:
                        conn.execute(
                            f"UPDATE jobs SET lease_id = NULL, leased_until = NULL, worker_id = NULL WHERE {' AND '.join(where_np)}",
                            tuple(params_np),
                        )
                        res["fixed"] += conn.total_changes or 0
                        conn.execute(
                            f"UPDATE jobs SET status='queued', leased_until = NULL, worker_id = NULL, lease_id = NULL WHERE {' AND '.join(where_pr)}",
                            tuple(params_pr),
                        )
                        res["fixed"] += conn.total_changes or 0
            try:
                emit_job_event(
                    "jobs.integrity_sweep",
                    job=None,
                    attrs={
                        "fixed": int(res.get("fixed", 0)),
                        "non_processing_with_lease": int(res.get("non_processing_with_lease", 0)),
                        "processing_expired": int(res.get("processing_expired", 0)),
                        "domain": domain,
                        "queue": queue,
                        "job_type": job_type,
                        "fix": bool(fix),
                    },
                )
            except Exception:
                pass
            return res
        finally:
            try:
                conn.close()
            except Exception:
                pass
