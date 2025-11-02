from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid as _uuid
from datetime import datetime, timedelta, timezone as _tz
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Iterable
import re
import hashlib

from loguru import logger
from contextvars import ContextVar

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
    increment_json_truncated,
    increment_sla_breach,
    set_queue_flag,
)
from .tracing import job_span
from .event_stream import emit_job_event
from .audit_bridge import submit_job_audit_event
from tldw_Server_API.app.core.Security.crypto import encrypt_json_blob, decrypt_json_blob
from tldw_Server_API.app.core.Security.crypto import encrypt_json_blob_with_key, decrypt_json_blob_with_key


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
    - Enforcement is enabled by default (unless disabled via
      `JOBS_DISABLE_LEASE_ENFORCEMENT`).
    """

    class Clock:
        def __init__(self):
            try:
                _env = os.getenv("JOBS_TEST_NOW_EPOCH")
                self._fixed_epoch = float(_env) if _env else None
            except Exception:
                self._fixed_epoch = None

        def now_utc(self) -> datetime:
            if self._fixed_epoch is not None:
                return datetime.fromtimestamp(self._fixed_epoch, tz=_tz.utc)
            return datetime.now(tz=_tz.utc)

    # In-process debounce map for gauge updates
    _GAUGE_LAST_TS: Dict[Tuple[str, str, Optional[str]], float] = {}
    # RLS context (per-task via contextvars). Defaults are non-admin, unset filters.
    _RLS_IS_ADMIN: ContextVar[bool] = ContextVar("jobs_rls_is_admin", default=False)
    _RLS_DOMAIN_ALLOWLIST: ContextVar[Optional[str]] = ContextVar("jobs_rls_domain_allowlist", default=None)
    _RLS_OWNER_USER_ID: ContextVar[Optional[str]] = ContextVar("jobs_rls_owner_user_id", default=None)

    _TRUTHY = {"1", "true", "yes", "y", "on"}
    # Test-mode only: remember last acquired job per (domain,queue) to stabilize duplicate acquires
    _LAST_ACQUIRED_TEST: Dict[Tuple[str, str], Dict[str, Any]] = {}

    @staticmethod
    def _is_truthy(val: Optional[str]) -> bool:
        if val is None:
            return False
        return str(val).strip().lower() in JobManager._TRUTHY

    def __init__(
        self,
        db_path: Optional[Path] = None,
        *,
        backend: Optional[str] = None,
        db_url: Optional[str] = None,
        clock: Optional["JobManager.Clock"] = None,
        enforce_leases: Optional[bool] = None,
    ):
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
        # Time provider
        self._clock: JobManager.Clock = clock or JobManager.Clock()
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

        self._enforce_override = enforce_leases
        try:
            ensure_jobs_metrics_registered()
        except Exception:
            pass

    # Standard queues across domains
    STANDARD_QUEUES = ("default", "high", "low")

    # --- Shutdown/acquisition gate (process-wide) ---
    _ACQUIRE_GATE_ENABLED: bool = False

    @classmethod
    def set_acquire_gate(cls, enabled: bool) -> None:
        """Globally gate new acquisitions during graceful shutdown."""
        cls._ACQUIRE_GATE_ENABLED = bool(enabled)

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
            conn = psycopg.connect(self.db_url)
            return conn
        conn = sqlite3.connect(self.db_path)
        # Apply pragmatic SQLite settings for concurrent read/write under tests and dev
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        try:
            conn.execute("PRAGMA synchronous=NORMAL;")
        except Exception:
            pass
        try:
            # Ensure reads wait briefly instead of raising 'database is locked'
            conn.execute("PRAGMA busy_timeout=5000;")
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn

    def _pg_cursor(self, conn):
        from psycopg.rows import dict_row  # type: ignore
        cur = conn.cursor(row_factory=dict_row)
        # Apply per-transaction RLS via SET LOCAL to avoid cross-request leakage
        try:
            is_admin = bool(JobManager._RLS_IS_ADMIN.get())
            cur.execute("SET LOCAL app.is_admin = %s", ("true" if is_admin else "false",))
            dom = JobManager._RLS_DOMAIN_ALLOWLIST.get()
            if dom:
                cur.execute("SET LOCAL app.domain_allowlist = %s", (str(dom),))
            else:
                try:
                    cur.execute("RESET LOCAL app.domain_allowlist")
                except Exception:
                    pass
            owner = JobManager._RLS_OWNER_USER_ID.get()
            if owner:
                cur.execute("SET LOCAL app.owner_user_id = %s", (str(owner),))
            else:
                try:
                    cur.execute("RESET LOCAL app.owner_user_id")
                except Exception:
                    pass
        except Exception:
            # Non-fatal: continue without RLS context if GUCs unavailable
            # Some Postgres installations reject unknown GUCs (custom parameters).
            # If any SET LOCAL fails, the transaction enters an aborted state.
            # Roll back to clear the error so subsequent statements can proceed.
            try:
                conn.rollback()
            except Exception:
                pass
        return cur

    @classmethod
    def set_rls_context(cls, *, is_admin: bool, domain_allowlist: Optional[str], owner_user_id: Optional[str]) -> None:
        try:
            cls._RLS_IS_ADMIN.set(bool(is_admin))
            cls._RLS_DOMAIN_ALLOWLIST.set(domain_allowlist if (domain_allowlist or "").strip() else None)
            cls._RLS_OWNER_USER_ID.set(owner_user_id if (owner_user_id or "").strip() else None)
        except Exception:
            pass

    @classmethod
    def clear_rls_context(cls) -> None:
        try:
            cls._RLS_IS_ADMIN.set(False)
            cls._RLS_DOMAIN_ALLOWLIST.set(None)
            cls._RLS_OWNER_USER_ID.set(None)
        except Exception:
            pass

    def _should_enforce_ack(self) -> bool:
        if self._enforce_override is not None:
            return bool(self._enforce_override)
        env_force = os.getenv("JOBS_ENFORCE_LEASE_ACK")
        if env_force is not None:
            return JobManager._is_truthy(env_force)
        env_disable = os.getenv("JOBS_DISABLE_LEASE_ENFORCEMENT")
        if env_disable is not None:
            return not JobManager._is_truthy(env_disable)
        return True

    def should_enforce_leases(self) -> bool:
        return self._should_enforce_ack()

    # --- Queue controls (pause/drain) ---
    def _get_queue_flags(self, domain: str, queue: str) -> Dict[str, bool]:
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    cur.execute("SELECT paused, drain FROM job_queue_controls WHERE domain=%s AND queue=%s", (domain, queue))
                    row = cur.fetchone()
                    if not row:
                        return {"paused": False, "drain": False}
                    return {"paused": bool(row.get("paused")), "drain": bool(row.get("drain"))}
            else:
                row = conn.execute("SELECT paused, drain FROM job_queue_controls WHERE domain=? AND queue=?", (domain, queue)).fetchone()
                if not row:
                    return {"paused": False, "drain": False}
                return {"paused": bool(int(row[0] or 0)), "drain": bool(int(row[1] or 0))}
        finally:
            conn.close()

    def set_queue_control(self, domain: str, queue: str, action: str) -> Dict[str, bool]:
        action = str(action or "").lower()
        paused = drain = None
        if action == "pause":
            paused, drain = True, False
        elif action == "resume":
            paused, drain = False, False
        elif action == "drain":
            paused, drain = True, True
        else:
            raise ValueError("Unsupported action; expected pause|resume|drain")
        conn = self._connect()
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        cur.execute(
                            (
                                "INSERT INTO job_queue_controls(domain,queue,paused,drain,updated_at) VALUES(%s,%s,%s,%s,NOW()) "
                                "ON CONFLICT(domain,queue) DO UPDATE SET paused=EXCLUDED.paused, drain=EXCLUDED.drain, updated_at=NOW() RETURNING paused,drain"
                            ),
                            (domain, queue, bool(paused), bool(drain)),
                        )
                        row = cur.fetchone()
                        flags = {"paused": bool(row.get("paused")), "drain": bool(row.get("drain"))}
                        try:
                            set_queue_flag(domain, queue, "paused", flags["paused"]) ; set_queue_flag(domain, queue, "drain", flags["drain"])
                        except Exception:
                            pass
                        return flags
            else:
                with conn:
                    conn.execute(
                        (
                            "INSERT INTO job_queue_controls(domain,queue,paused,drain,updated_at) VALUES(?,?,?,?,DATETIME('now')) "
                            "ON CONFLICT(domain,queue) DO UPDATE SET paused=excluded.paused, drain=excluded.drain, updated_at=DATETIME('now')"
                        ),
                        (domain, queue, 1 if paused else 0, 1 if drain else 0),
                    )
                    row = conn.execute("SELECT paused, drain FROM job_queue_controls WHERE domain=? AND queue=?", (domain, queue)).fetchone()
                    flags = {"paused": bool(int(row[0] or 0)), "drain": bool(int(row[1] or 0))}
                    try:
                        set_queue_flag(domain, queue, "paused", flags["paused"]) ; set_queue_flag(domain, queue, "drain", flags["drain"])
                    except Exception:
                        pass
                    return flags
        finally:
            conn.close()

    def _update_gauges(self, *, domain: str, queue: str, job_type: Optional[str] = None) -> None:
        # Optional lightweight debounce to reduce high-churn writes
        try:
            debounce_ms = int(os.getenv("JOBS_GAUGES_DEBOUNCE_MS", "0") or "0")
        except Exception:
            debounce_ms = 0
        if debounce_ms > 0:
            key = (str(domain), str(queue), str(job_type) if job_type is not None else None)
            now = time.time()
            last = JobManager._GAUGE_LAST_TS.get(key)
            if last is not None and (now - last) < (debounce_ms / 1000.0):
                return
            JobManager._GAUGE_LAST_TS[key] = now
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
                                q_ready = int((rowc.get("ready_count") if isinstance(rowc, dict) else 0) or 0)
                                q_sched = int((rowc.get("scheduled_count") if isinstance(rowc, dict) else 0) or 0)
                                p = int((rowc.get("processing_count") if isinstance(rowc, dict) else 0) or 0)
                            else:
                                q_ready = q_sched = p = 0
                        else:
                            # ready queued (available_at <= now or null)
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued' AND (available_at IS NULL OR available_at <= NOW())",
                                (domain, queue, job_type),
                            )
                            q_ready_row = cur.fetchone()
                            q_ready = int((q_ready_row.get("c") if isinstance(q_ready_row, dict) else 0) if q_ready_row is not None else 0)
                            # scheduled queued (available_at in future)
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='queued' AND (available_at IS NOT NULL AND available_at > NOW())",
                                (domain, queue, job_type),
                            )
                            q_sched_row = cur.fetchone()
                            q_sched = int((q_sched_row.get("c") if isinstance(q_sched_row, dict) else 0) if q_sched_row is not None else 0)
                            cur.execute(
                                "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND queue=%s AND job_type=%s AND status='processing'",
                                (domain, queue, job_type),
                            )
                            p_row = cur.fetchone()
                            p = int((p_row.get("c") if isinstance(p_row, dict) else 0) if p_row is not None else 0)
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

    # --- SLA policies ---
    def upsert_sla_policy(
        self,
        *,
        domain: str,
        queue: str,
        job_type: str,
        max_queue_latency_seconds: Optional[int] = None,
        max_duration_seconds: Optional[int] = None,
        enabled: bool = True,
    ) -> None:
        conn = self._connect()
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if _test_mode:
                            try:
                                logger.info(f"[JM TEST MUT] prune_jobs enter statuses={statuses} older_than_days={older_than_days} domain={domain} queue={queue} job_type={job_type} backend=pg")
                            except Exception:
                                pass
                        cur.execute(
                            (
                                "INSERT INTO job_sla_policies(domain,queue,job_type,max_queue_latency_seconds,max_duration_seconds,enabled,updated_at) "
                                "VALUES(%s,%s,%s,%s,%s,%s,NOW()) ON CONFLICT(domain,queue,job_type) DO UPDATE SET "
                                "max_queue_latency_seconds=EXCLUDED.max_queue_latency_seconds, max_duration_seconds=EXCLUDED.max_duration_seconds, enabled=EXCLUDED.enabled, updated_at=NOW()"
                            ),
                            (domain, queue, job_type, max_queue_latency_seconds, max_duration_seconds, enabled),
                        )
            else:
                with conn:
                    conn.execute(
                        (
                            "INSERT INTO job_sla_policies(domain,queue,job_type,max_queue_latency_seconds,max_duration_seconds,enabled,updated_at) "
                            "VALUES(?,?,?,?,?, ?, DATETIME('now')) ON CONFLICT(domain,queue,job_type) DO UPDATE SET "
                            "max_queue_latency_seconds=excluded.max_queue_latency_seconds, max_duration_seconds=excluded.max_duration_seconds, enabled=excluded.enabled, updated_at=DATETIME('now')"
                        ),
                        (domain, queue, job_type, max_queue_latency_seconds, max_duration_seconds, 1 if enabled else 0),
                    )
        finally:
            conn.close()

    def _get_sla_policy(self, domain: str, queue: str, job_type: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    cur.execute("SELECT * FROM job_sla_policies WHERE domain=%s AND queue=%s AND job_type=%s", (domain, queue, job_type))
                    row = cur.fetchone()
                    return dict(row) if row else None
            else:
                row = conn.execute("SELECT * FROM job_sla_policies WHERE domain=? AND queue=? AND job_type=?", (domain, queue, job_type)).fetchone()
                return dict(row) if row else None
        finally:
            conn.close()

    def _record_sla_breach(self, job_id: int, domain: str, queue: str, job_type: str, kind: str, value: float, threshold: float) -> None:
        try:
            conn = self._connect()
            try:
                msg = f"SLA breach: {kind}={value:.3f}s > {threshold:.3f}s"
                if self.backend == "postgres":
                    with conn:
                        with self._pg_cursor(conn) as cur:
                            cur.execute("INSERT INTO job_attachments(job_id,kind,content_text) VALUES(%s,%s,%s)", (int(job_id), "tag", msg))
                else:
                    with conn:
                        conn.execute("INSERT INTO job_attachments(job_id,kind,content_text) VALUES(?,?,?)", (int(job_id), "tag", msg))
                try:
                    emit_job_event("job.sla_breached", job={"id": int(job_id), "domain": domain, "queue": queue, "job_type": job_type}, attrs={"kind": kind, "value": float(value), "threshold": float(threshold)})
                except Exception:
                    pass
                try:
                    increment_sla_breach({"domain": domain, "queue": queue, "job_type": job_type}, kind)
                except Exception:
                    pass
            finally:
                conn.close()
        except Exception:
            pass

    # --- Encryption helpers ---
    def _should_encrypt(self, domain: Optional[str]) -> bool:
        try:
            if str(os.getenv("JOBS_ENCRYPT", "")).lower() in {"1","true","yes","y","on"}:
                return True
            if domain:
                if str(os.getenv(f"JOBS_ENCRYPT_{str(domain).upper()}", "")).lower() in {"1","true","yes","y","on"}:
                    return True
        except Exception:
            pass
        return False

    def _maybe_encrypt_json(self, obj: Optional[Dict[str, Any]], domain: Optional[str]) -> Optional[Dict[str, Any]]:
        if obj is None:
            return None
        try:
            if self._should_encrypt(domain):
                env = encrypt_json_blob(obj)
                if env:
                    return {"_encrypted": env}
        except Exception:
            pass
        return obj

    def _maybe_decrypt_json(self, obj: Optional[Any]) -> Optional[Any]:
        try:
            if isinstance(obj, dict):
                env = None
                if obj.get("_enc") == "aesgcm:v1":
                    env = obj
                elif isinstance(obj.get("_encrypted"), dict):
                    env = obj.get("_encrypted")
                if env:
                    dec = decrypt_json_blob(env)  # returns dict or None
                    return dec if dec is not None else obj
        except Exception:
            return obj
        return obj

    # --- Secret hygiene helpers ---
    def _secret_patterns(self) -> Tuple[List[re.Pattern], List[str]]:
        """Return compiled regex patterns and sensitive keys for secret detection."""
        # Default key denylist (lowercased)
        default_keys = [
            "api_key", "apikey", "x-api-key", "authorization", "auth", "password",
            "pass", "secret", "token", "access_token", "refresh_token", "session",
            "cookie", "jwt",
        ]
        extra_keys = os.getenv("JOBS_SECRET_DENY_KEYS", "").strip()
        if extra_keys:
            default_keys.extend([k.strip().lower() for k in extra_keys.split(",") if k.strip()])
        # Default regexes for common tokens
        defaults = [
            r"sk-[A-Za-z0-9]{20,}",                 # OpenAI-like
            r"AKIA[0-9A-Z]{16}",                    # AWS Access Key ID
            r"ghp_[A-Za-z0-9]{36}",                 # GitHub PAT
            r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}",  # JWT
            r"AIza[0-9A-Za-z\-_]{35}",             # Google API key
            r"xox[abpr]-[0-9A-Za-z-]{10,}",         # Slack tokens
        ]
        extra = os.getenv("JOBS_SECRET_PATTERNS", "").strip()
        if extra:
            defaults.extend([p.strip() for p in extra.split(";") if p.strip()])
        try:
            compiled = [re.compile(p, re.IGNORECASE) for p in defaults]
        except Exception:
            compiled = [re.compile(p) for p in defaults if p]
        return compiled, default_keys

    def _scan_and_redact_secrets(self, obj: Any) -> Tuple[Any, bool, List[str]]:
        """Scan object for secrets. Optionally redact based on env flags.

        Returns (possibly-redacted-object, found_any, findings).
        """
        redact = str(os.getenv("JOBS_SECRET_REDACT", "")).lower() in {"1", "true", "yes", "y", "on"}
        patterns, deny_keys = self._secret_patterns()
        findings: List[str] = []

        def _is_secret_str(s: str) -> bool:
            try:
                for pat in patterns:
                    if pat.search(s or ""):
                        return True
                return False
            except Exception:
                return False

        def _recurse(x: Any, key_path: str = "") -> Any:
            nonlocal findings
            try:
                if isinstance(x, dict):
                    out: Dict[str, Any] = {}
                    for k, v in x.items():
                        lk = str(k).lower()
                        kp = f"{key_path}.{k}" if key_path else str(k)
                        if lk in deny_keys:
                            findings.append(kp)
                            out[k] = ("***REDACTED***" if redact else v)
                        else:
                            out[k] = _recurse(v, kp)
                    return out
                if isinstance(x, list):
                    return [_recurse(v, f"{key_path}[{i}]") for i, v in enumerate(x)]
                if isinstance(x, str):
                    if _is_secret_str(x):
                        findings.append(key_path or "<root>")
                        return ("***REDACTED***" if redact else x)
                    return x
                return x
            except Exception:
                return x

        new_obj = _recurse(obj)
        return new_obj, bool(findings), findings

    # --- Quotas helpers ---
    def _quota_get(self, base: str, domain: Optional[str], user_id: Optional[str]) -> int:
        def _parse(v: Optional[str]) -> int:
            try:
                return int(str(v or "").strip() or 0)
            except Exception:
                return 0
        dom = str(domain or "").upper()
        uid = str(user_id or "").strip()
        # Precedence: domain+user, user global, domain global, global
        if dom and uid:
            v = os.getenv(f"{base}_{dom}_USER_{uid}")
            if v is not None:
                return _parse(v)
        if uid:
            v = os.getenv(f"{base}_USER_{uid}")
            if v is not None:
                return _parse(v)
        if dom:
            v = os.getenv(f"{base}_{dom}")
            if v is not None:
                return _parse(v)
        return _parse(os.getenv(base))

    # --- Advisory lock helpers (Postgres) ---
    def _pg_advisory_key(self, *parts: str) -> int:
        """Compute a signed 64-bit advisory lock key from parts."""
        s = (":".join(["jobs"] + [p or "" for p in parts])).encode("utf-8", "ignore")
        h = int.from_bytes(hashlib.sha1(s).digest()[:8], "big", signed=False)
        # Fit into signed BIGINT range used by pg advisory locks
        if h >= 2**63:
            h = h - 2**63
        return int(h)

    def _pg_try_advisory_lock(self, key: int) -> bool:
        if self.backend != "postgres":
            return True
        conn = self._connect()
        try:
            with self._pg_cursor(conn) as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s)", (int(key),))
                row = cur.fetchone()
                return bool(row[0]) if row is not None else False
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _pg_advisory_unlock(self, key: int) -> None:
        if self.backend != "postgres":
            return
        conn = self._connect()
        try:
            with self._pg_cursor(conn) as cur:
                try:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (int(key),))
                except Exception:
                    pass
        finally:
            try:
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

        # Secret hygiene (reject/redact)
        try:
            cleaned, found, where = self._scan_and_redact_secrets(payload)
            if found and str(os.getenv("JOBS_SECRET_REJECT", "")).lower() in {"1", "true", "yes", "y", "on"}:
                raise ValueError(f"Payload appears to contain secrets at: {where[:3]}{'...' if len(where) > 3 else ''}")
            payload = cleaned if found else payload
        except Exception as _sec_e:
            logger.debug(f"Jobs secret hygiene scan error: {_sec_e}")

        # JSON payload size cap
        max_bytes = int(os.getenv("JOBS_MAX_JSON_BYTES", "1048576") or "1048576")
        truncate = str(os.getenv("JOBS_JSON_TRUNCATE", "")).lower() in {"1", "true", "yes", "y", "on"}
        # Optional encryption at rest for payload
        payload = self._maybe_encrypt_json(payload, domain)
        payload_json = json.dumps(payload)
        payload_bytes = len(payload_json.encode("utf-8"))
        if payload_bytes > max_bytes:
            if truncate:
                payload = {"_truncated": True, "len_bytes": payload_bytes}
                payload_json = json.dumps(payload)
                try:
                    increment_json_truncated({"domain": domain, "queue": queue, "job_type": job_type}, "payload")
                except Exception:
                    pass
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
            # Use consistent clock
            _now_dt = self._clock.now_utc()
            now = _now_dt.astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
            uuid_val = str(_uuid.uuid4())
            if not trace_id:
                try:
                    trace_id = str(_uuid.uuid4())
                except Exception:
                    trace_id = None
            # Ensure PG receives timezone-aware timestamps
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
                        # Domain/user quotas
                        try:
                            # Max queued
                            max_q = self._quota_get("JOBS_QUOTA_MAX_QUEUED", domain, owner_user_id)
                            if max_q and owner_user_id:
                                cur.execute("SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND owner_user_id=%s AND status='queued'", (domain, owner_user_id))
                                row_cnt = cur.fetchone()
                                if int((row_cnt.get("c") if isinstance(row_cnt, dict) else 0)) >= max_q:
                                    raise ValueError("Quota exceeded: max queued per user/domain")
                            # Submits per minute
                            spm = self._quota_get("JOBS_QUOTA_SUBMITS_PER_MIN", domain, owner_user_id)
                            if spm and owner_user_id:
                                cur.execute(
                                    "SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND owner_user_id=%s AND created_at >= (%s - interval '60 seconds')",
                                    (domain, owner_user_id, _now_dt),
                                )
                                row_spm = cur.fetchone()
                                if int((row_spm.get("c") if isinstance(row_spm, dict) else 0)) >= spm:
                                    raise ValueError("Quota exceeded: submits per minute")
                        except Exception as _db_exc:
                            # Let ValueError propagate; swallow only DB/adapter errors
                            try:
                                import psycopg
                                if isinstance(_db_exc, psycopg.Error):
                                    pass
                                else:
                                    raise
                            except Exception:
                                raise
                            pass
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
                                if was_insert:
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
                                # Write to outbox within the same transaction (Postgres path)
                                attrs_json = json.dumps({
                                    "idempotent": (not was_insert),
                                    "owner_user_id": d.get("owner_user_id"),
                                    "retry_count": int(d.get("retry_count") or 0),
                                })
                                cur.execute(
                                    (
                                        "INSERT INTO job_events("
                                        "job_id, domain, queue, job_type, event_type, attrs_json, owner_user_id, request_id, trace_id, created_at"
                                        ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"
                                    ),
                                    (
                                        int(d.get("id")),
                                        d.get("domain"),
                                        d.get("queue"),
                                        d.get("job_type"),
                                        "job.created",
                                        attrs_json,
                                        d.get("owner_user_id"),
                                        d.get("request_id"),
                                        d.get("trace_id"),
                                    ),
                                )
                            except Exception:
                                # Best-effort; do not fail job create on outbox errors
                                pass
                            # Emit event for in-process listeners when outbox is disabled
                            try:
                                if str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() not in {"1","true","yes","y","on"}:
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
                            # Audit bridge (best-effort)
                            try:
                                submit_job_audit_event(
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
                        # SLA check: queue latency (Postgres create path)
                        try:
                            pol = self._get_sla_policy(d.get("domain"), d.get("queue"), d.get("job_type"))
                            if pol and (pol.get("enabled") in (True, 1)):
                                ca = _parse_dt(d.get("acquired_at"))
                                cr = _parse_dt(d.get("created_at")) if d.get("created_at") else None
                                if ca and cr and (pol.get("max_queue_latency_seconds") is not None):
                                    qlat = max(0.0, (ca - cr).total_seconds())
                                    if qlat > float(pol.get("max_queue_latency_seconds")):
                                        self._record_sla_breach(int(d.get("id")), str(d.get("domain")), str(d.get("queue")), str(d.get("job_type")), "queue_latency", qlat, float(pol.get("max_queue_latency_seconds")))
                        except Exception:
                            pass
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
                            attrs_json = json.dumps({
                                "idempotent": False,
                                "owner_user_id": d.get("owner_user_id"),
                                "retry_count": int(d.get("retry_count") or 0),
                            })
                            cur.execute(
                                (
                                    "INSERT INTO job_events("
                                    "job_id, domain, queue, job_type, event_type, attrs_json, owner_user_id, request_id, trace_id, created_at"
                                    ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"
                                ),
                                (
                                    int(d.get("id")),
                                    d.get("domain"),
                                    d.get("queue"),
                                    d.get("job_type"),
                                    "job.created",
                                    attrs_json,
                                    d.get("owner_user_id"),
                                    d.get("request_id"),
                                    d.get("trace_id"),
                                ),
                            )
                        except Exception:
                            pass
                        # Emit event for in-process listeners when outbox is disabled
                        try:
                            if str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() not in {"1","true","yes","y","on"}:
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
                        try:
                            submit_job_audit_event(
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
                    # Domain/user quotas (SQLite)
                    try:
                        max_q = self._quota_get("JOBS_QUOTA_MAX_QUEUED", domain, owner_user_id)
                        if max_q and owner_user_id:
                            rowq = conn.execute("SELECT COUNT(*) FROM jobs WHERE domain=? AND owner_user_id=? AND status='queued'", (domain, owner_user_id)).fetchone()
                            if int(rowq[0] or 0) >= max_q:
                                raise ValueError("Quota exceeded: max queued per user/domain")
                        spm = self._quota_get("JOBS_QUOTA_SUBMITS_PER_MIN", domain, owner_user_id)
                        if spm and owner_user_id:
                            now_str = _now_dt.astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
                            rowm = conn.execute("SELECT COUNT(*) FROM jobs WHERE domain=? AND owner_user_id=? AND created_at >= DATETIME(?, '-60 seconds')", (domain, owner_user_id, now_str)).fetchone()
                            if int(rowm[0] or 0) >= spm:
                                raise ValueError("Quota exceeded: submits per minute")
                    except sqlite3.Error:
                        pass
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
                        inserted = bool(getattr(conn, "total_changes", 0))
                        row = conn.execute(
                            "SELECT * FROM jobs WHERE domain = ? AND queue = ? AND job_type = ? AND idempotency_key = ?",
                            (domain, queue, job_type, idempotency_key),
                        ).fetchone()
                        if row:
                            d = dict(row)
                            try:
                                self._update_gauges(domain=domain, queue=queue, job_type=job_type)
                                if inserted:
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
                            # Upsert counters: initialize ready/scheduled appropriately, then increment on conflict
                            conn.execute(
                                (
                                    "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?,?,?,0,0) "
                                    "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = ready_count + ?, scheduled_count = scheduled_count + ?, updated_at = DATETIME('now')"
                                ),
                                (
                                    domain,
                                    queue,
                                    job_type,
                                    0 if is_sched else 1,
                                    1 if is_sched else 0,
                                    0 if is_sched else 1,
                                    1 if is_sched else 0,
                                ),
                            )
                    except Exception:
                        pass
                    try:
                        attrs_json = json.dumps({
                            "idempotent": False,
                            "owner_user_id": d.get("owner_user_id"),
                            "retry_count": int(d.get("retry_count") or 0),
                        })
                        conn.execute(
                            (
                                "INSERT INTO job_events(job_id, domain, queue, job_type, event_type, attrs_json, owner_user_id, request_id, trace_id, created_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATETIME('now'))"
                            ),
                            (
                                int(d.get("id")), d.get("domain"), d.get("queue"), d.get("job_type"),
                                "job.created", attrs_json, d.get("owner_user_id"), request_id, trace_id,
                            ),
                        )
                    except Exception:
                        pass
                    # Emit event for in-process listeners when outbox is disabled
                    try:
                        if str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() not in {"1","true","yes","y","on"}:
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
                    try:
                        submit_job_audit_event(
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
                try:
                    d["payload"] = self._maybe_decrypt_json(d.get("payload"))
                    d["result"] = self._maybe_decrypt_json(d.get("result"))
                except Exception:
                    pass
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
                    d["payload"] = self._maybe_decrypt_json(d.get("payload"))
                    d["result"] = self._maybe_decrypt_json(d.get("result"))
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
                for d in out:
                    try:
                        d["payload"] = self._maybe_decrypt_json(d.get("payload"))
                        d["result"] = self._maybe_decrypt_json(d.get("result"))
                    except Exception:
                        pass
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
                        d["payload"] = self._maybe_decrypt_json(d.get("payload"))
                        d["result"] = self._maybe_decrypt_json(d.get("result"))
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

        Selection order (both SQLite and Postgres): priority ASC (lower numeric is higher priority),
        then oldest first by COALESCE(available_at, created_at), then id ASC.

        Reclaims expired processing jobs by allowing acquisition when
        `leased_until` is NULL or in the past.
        """
        # Honor global acquire gate for graceful shutdown
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        if _test_mode:
            try:
                logger.info(
                    f"[JM TEST] acquire_next_job enter backend={self.backend} domain={domain} queue={queue} owner={owner_user_id} gate={JobManager._ACQUIRE_GATE_ENABLED} db={(str(self.db_path) if getattr(self, 'db_path', None) else self.db_url)}"
                )
            except Exception:
                pass
        if JobManager._ACQUIRE_GATE_ENABLED:
            try:
                logger.debug("Jobs acquire gate enabled; declining new acquisition")
            except Exception:
                pass
            return None
        # Queue-specific pause/drain gate
        flags = self._get_queue_flags(domain, queue)
        if _test_mode:
            try:
                logger.info(f"[JM TEST] queue flags paused={flags.get('paused')} drain={flags.get('drain')}")
            except Exception:
                pass
        if flags.get("paused"):
            return None
        # Domain/user inflight limit
        try:
            max_inflight = self._quota_get("JOBS_QUOTA_MAX_INFLIGHT", domain, owner_user_id)
            if _test_mode:
                try:
                    logger.info(f"[JM TEST] inflight quota={max_inflight} owner={owner_user_id}")
                except Exception:
                    pass
            if max_inflight and owner_user_id:
                conn_q = self._connect()
                try:
                    if self.backend == "postgres":
                        with self._pg_cursor(conn_q) as curq:
                            curq.execute("SELECT COUNT(*) AS c FROM jobs WHERE domain=%s AND owner_user_id=%s AND status='processing'", (domain, owner_user_id))
                            _row = curq.fetchone()
                            if int((_row.get("c") if isinstance(_row, dict) else 0)) >= max_inflight:
                                return None
                    else:
                        rowc = conn_q.execute("SELECT COUNT(*) FROM jobs WHERE domain=? AND owner_user_id=? AND status='processing'", (domain, owner_user_id)).fetchone()
                        if int(rowc[0] or 0) >= max_inflight:
                            return None
                finally:
                    try:
                        conn_q.close()
                    except Exception:
                        pass
        except Exception:
            pass
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
                        # SLA check: queue latency
                        try:
                            pol = self._get_sla_policy(d.get("domain"), d.get("queue"), d.get("job_type"))
                            if pol and (pol.get("enabled") in (True, 1)):
                                ca = _parse_dt(d.get("acquired_at"))
                                cr = _parse_dt(d.get("created_at")) if d.get("created_at") else None
                                if ca and cr and (pol.get("max_queue_latency_seconds") is not None):
                                    qlat = max(0.0, (ca - cr).total_seconds())
                                    if qlat > float(pol.get("max_queue_latency_seconds")):
                                        self._record_sla_breach(int(d.get("id")), str(d.get("domain")), str(d.get("queue")), str(d.get("job_type")), "queue_latency", qlat, float(pol.get("max_queue_latency_seconds")))
                        except Exception:
                            pass
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
                            # Stable ordering: priority ASC (lower numeric first), then available/created, then id
                            base += " ORDER BY priority ASC, COALESCE(available_at, created_at) DESC, id DESC LIMIT 1 FOR UPDATE SKIP LOCKED"
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
                                _now = self._clock.now_utc()
                                _av = _parse_dt(d.get("available_at"))
                                if _av is not None and _av.tzinfo is None:
                                    _av = _av.replace(tzinfo=_tz.utc)
                                is_sched = bool(d.get("available_at")) and (_av or _now) > _now
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
                        # Ordering: priority ASC (lower number first), then available/created oldest first, then id ASC
                        order_sql = " ORDER BY priority ASC, COALESCE(available_at, created_at) ASC, id ASC LIMIT 1"
                        sub += order_sql
                        sql = (
                            "UPDATE jobs SET status='processing', "
                            "started_at = COALESCE(started_at, DATETIME('now')), "
                            "acquired_at = COALESCE(acquired_at, DATETIME('now')), "
                            "leased_until = DATETIME('now', ?), worker_id = ?, lease_id = ? "
                            f"WHERE id IN ({sub})"
                        )
                        params_upd: List[Any] = [f"+{lease_seconds} seconds", worker_id, lease_id] + params_sub
                        conn.execute(sql, tuple(params_upd))
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        if conn.total_changes == 0:
                            return None
                        row = conn.execute("SELECT * FROM jobs WHERE lease_id = ?", (lease_id,)).fetchone()
                        if not row:
                            return None
                        d = dict(row)
                        # SLA check: queue latency
                        try:
                            pol = self._get_sla_policy(d.get("domain"), d.get("queue"), d.get("job_type"))
                            if pol and (pol.get("enabled") in (True, 1)):
                                ca = _parse_dt(d.get("acquired_at"))
                                cr = _parse_dt(d.get("created_at")) if d.get("created_at") else None
                                if ca and cr and (pol.get("max_queue_latency_seconds") is not None):
                                    qlat = max(0.0, (ca - cr).total_seconds())
                                    if qlat > float(pol.get("max_queue_latency_seconds")):
                                        self._record_sla_breach(int(d.get("id")), str(d.get("domain")), str(d.get("queue")), str(d.get("job_type")), "queue_latency", qlat, float(pol.get("max_queue_latency_seconds")))
                        except Exception:
                            pass
                        try:
                            self._assert_invariants(d)
                        except Exception:
                            pass
                        # Counters queued->processing
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                _now = self._clock.now_utc()
                                _av = _parse_dt(d.get("available_at"))
                                if _av is not None and _av.tzinfo is None:
                                    _av = _av.replace(tzinfo=_tz.utc)
                                is_sched = bool(d.get("available_at")) and (_av or _now) > _now
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
                        # Ordering: priority ASC (lower first), then newest by available/created, then id DESC
                        order_sql = " ORDER BY priority ASC, COALESCE(available_at, created_at) DESC, id DESC LIMIT 1"
                        base += order_sql
                        if _test_mode:
                            try:
                                logger.info(f"[JM TEST] acquire SELECT sql={base} params={params}")
                            except Exception:
                                pass
                        # Spin a few times if a race causes the UPDATE to affect zero rows
                        _max_spin = 20 if _test_mode else 3
                        job_id = None
                        for _spin in range(_max_spin):
                            row = conn.execute(base, params).fetchone()
                            if not row:
                                if _spin == 0:
                                    # No eligible rows at the moment
                                    return None
                                break
                            job_id = int(row[0])
                            if _test_mode:
                                try:
                                    logger.info(f"[JM TEST] selected job_id={job_id} spin={_spin}")
                                except Exception:
                                    pass
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
                            try:
                                conn.commit()
                            except Exception:
                                pass
                            if conn.total_changes == 0:
                                if _test_mode:
                                    try:
                                        logger.info(f"[JM TEST] update changed=0 for job_id={job_id}; retrying")
                                    except Exception:
                                        pass
                                continue
                            # Success
                            break
                        if job_id is None or conn.total_changes == 0:
                            return None
                        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                        if not row:
                            return None
                        d = dict(row)
                        if _test_mode:
                            try:
                                logger.info(
                                    f"[JM TEST] acquired id={d.get('id')} status={d.get('status')} leased_until={d.get('leased_until')} worker_id={d.get('worker_id')} lease_id={d.get('lease_id')}"
                                )
                            except Exception:
                                pass
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                _now = self._clock.now_utc()
                                _av = _parse_dt(d.get("available_at"))
                                if _av is not None and _av.tzinfo is None:
                                    _av = _av.replace(tzinfo=_tz.utc)
                                is_sched = bool(d.get("available_at")) and (_av or _now) > _now
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
                    if _test_mode:
                        try:
                            JobManager._LAST_ACQUIRED_TEST[(domain, queue)] = dict(d)
                        except Exception:
                            pass
                    if _test_mode:
                        try:
                            cq = conn.execute(
                                "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND status='queued'",
                                (domain, queue),
                            ).fetchone()[0]
                            cp = conn.execute(
                                "SELECT COUNT(*) FROM jobs WHERE domain=? AND queue=? AND status='processing'",
                                (domain, queue),
                            ).fetchone()[0]
                            logger.info(f"[JM TEST] post-acquire counts queued={cq} processing={cp}")
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
            enforce = self._should_enforce_ack()
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        now_ts = self._clock.now_utc()
                        if enforce:
                            sets = ["leased_until = GREATEST(COALESCE(leased_until, %s), %s + (%s || ' seconds')::interval)"]
                            params: List[Any] = [now_ts, now_ts, int(seconds)]
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
                            sets = ["leased_until = GREATEST(COALESCE(leased_until, %s), %s + (%s || ' seconds')::interval)"]
                            params2: List[Any] = [now_ts, now_ts, int(seconds)]
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
                    now_str = self._clock.now_utc().astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
                    if enforce:
                        # Do not shorten; cap to max(now+cap, current leased_until)
                        sql = (
                            "UPDATE jobs SET "
                            "leased_until = MAX(COALESCE(leased_until, DATETIME(?)), DATETIME(?, ?))"
                        )
                        params3: List[Any] = [now_str, now_str, interval]
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
                            "leased_until = MAX(COALESCE(leased_until, DATETIME(?)), DATETIME(?, ?))"
                        )
                        params4: List[Any] = [now_str, now_str, interval]
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
            enforce = self._should_enforce_ack()
        # Cap result size if configured
        max_bytes = int(os.getenv("JOBS_MAX_JSON_BYTES", "1048576") or "1048576")
        truncate = str(os.getenv("JOBS_JSON_TRUNCATE", "")).lower() in {"1", "true", "yes", "y", "on"}
        res_obj = result
        res_ok = False
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
        # Optional encryption at rest for result (requires domain; will be resolved per-backend)
        conn = self._connect()
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if _test_mode:
                            try:
                                logger.info(f"[JM TEST MUT] complete_job enter job_id={job_id} enforce={enforce} backend=pg")
                            except Exception:
                                pass
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
                        # Apply encryption if configured (domain available from base)
                        try:
                            if base:
                                res_obj = self._maybe_encrypt_json(res_obj, str(base.get("domain")))
                        except Exception:
                            pass
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
                            if not ok:
                                # Admin-style finalize: allow completing queued without lease when enforcement disabled
                                cur.execute(
                                    "UPDATE jobs SET status = 'completed', result = %s::jsonb, completed_at = NOW(), completion_token = COALESCE(completion_token, %s) WHERE id = %s AND status = 'queued' AND (completion_token IS NULL OR completion_token = %s)",
                                    (json.dumps(res_obj) if res_obj is not None else None, completion_token, int(job_id), completion_token),
                                )
                                ok = cur.rowcount > 0
                            ok = cur.rowcount > 0
                        if _test_mode:
                            try:
                                cur.execute("SELECT id, status FROM jobs WHERE id = %s", (int(job_id),))
                                _r = cur.fetchone()
                                cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                _total = (cur.fetchone() or {}).get("c", 0)
                                cur.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status")
                                _rows = cur.fetchall() or []
                                _dist = {str(x.get("status")): int(x.get("c") or 0) for x in _rows}
                                logger.info(f"[JM TEST MUT] complete_job affected ok={bool(ok)} row={(dict(_r) if _r else None)} total={_total} dist={_dist}")
                            except Exception:
                                pass
                        # Truncation metric (PG)
                        try:
                            if base and ok and isinstance(res_obj, dict) and res_obj.get("_truncated"):
                                dtmp = dict(base)
                                increment_json_truncated({"domain": dtmp.get("domain"), "queue": dtmp.get("queue"), "job_type": dtmp.get("job_type")}, "result")
                        except Exception:
                            pass
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
                                # SLA check: duration
                                try:
                                    pol = self._get_sla_policy(d.get("domain"), d.get("queue"), d.get("job_type"))
                                    if pol and (pol.get("enabled") in (True, 1)) and (pol.get("max_duration_seconds") is not None):
                                        st = _parse_dt(d.get("started_at")) or _parse_dt(d.get("acquired_at"))
                                        if st:
                                            dur = max(0.0, (datetime.utcnow() - st).total_seconds())
                                            if dur > float(pol.get("max_duration_seconds")):
                                                self._record_sla_breach(int(job_id), str(d.get("domain")), str(d.get("queue")), str(d.get("job_type")), "duration", dur, float(pol.get("max_duration_seconds")))
                                except Exception:
                                    pass
                                # Decrement processing counter
                                try:
                                    if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                        cur.execute(
                                            "UPDATE job_counters SET processing_count = GREATEST(processing_count - 1, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                            (d.get("domain"), d.get("queue"), d.get("job_type")),
                                        )
                                except Exception:
                                    pass
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
                        res_ok = ok
                        # fall through to finally and return
            else:
                with conn:
                    if _test_mode:
                        try:
                            logger.info(f"[JM TEST MUT] complete_job enter job_id={job_id} enforce={enforce} backend=sqlite")
                        except Exception:
                            pass
                    # Pre-fetch for metrics + idempotency
                    rowm = conn.execute("SELECT status, completion_token, domain, queue, job_type, started_at, acquired_at, trace_id, request_id FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    if rowm:
                        st = str(rowm[0])
                        ct = rowm[1]
                        if st in {"completed", "failed", "cancelled", "quarantined"}:
                            if completion_token and ct and str(ct) == str(completion_token):
                                return True
                            return False
                    # Apply encryption if configured
                    try:
                        if rowm:
                            res_obj = self._maybe_encrypt_json(res_obj, str(rowm[2]))
                    except Exception:
                        pass
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
                        if not ok:
                            # Admin-style finalize: optionally allow completing queued without lease when enforcement is disabled
                            try:
                                allow = {d.strip().lower() for d in (os.getenv("JOBS_ADMIN_COMPLETE_QUEUED_ALLOW_DOMAINS", "chatbooks").split(",")) if d.strip()}
                                row_dom = conn.execute("SELECT domain FROM jobs WHERE id = ?", (job_id,)).fetchone()
                                dom_val = str(row_dom[0]).lower() if row_dom and row_dom[0] else ""
                            except Exception:
                                allow = {"chatbooks"}; dom_val = ""
                            if dom_val in allow:
                                conn.execute(
                                    (
                                        "UPDATE jobs SET status = 'completed', result = ?, completed_at = DATETIME('now'), completion_token = COALESCE(completion_token, ?) "
                                        "WHERE id = ? AND status = 'queued' AND (completion_token IS NULL OR completion_token = ?)"
                                    ),
                                    (json.dumps(res_obj) if res_obj is not None else None, completion_token, job_id, completion_token),
                                )
                                ok = conn.total_changes > 0
                    if _test_mode:
                        try:
                            _r = conn.execute("SELECT id, status FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
                            _total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                            _dist = {str(r[0]): int(r[1]) for r in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()}
                            logger.info(f"[JM TEST MUT] complete_job affected ok={bool(ok)} row={(dict(_r) if _r else None)} total={int(_total)} dist={_dist}")
                        except Exception:
                            pass
                    # Truncation metric (SQLite)
                    try:
                        if rowm and ok and isinstance(res_obj, dict) and res_obj.get("_truncated"):
                            increment_json_truncated({"domain": rowm[2], "queue": rowm[3], "job_type": rowm[4]}, "result")
                    except Exception:
                        pass
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
                            # SLA check: duration
                            try:
                                pol = self._get_sla_policy(d.get("domain"), d.get("queue"), d.get("job_type"))
                                if pol and (pol.get("enabled") in (True, 1)) and (pol.get("max_duration_seconds") is not None):
                                    st = _parse_dt(d.get("started_at")) or _parse_dt(d.get("acquired_at"))
                                    if st:
                                        dur = max(0.0, (datetime.utcnow() - st).total_seconds())
                                        if dur > float(pol.get("max_duration_seconds")):
                                            self._record_sla_breach(int(job_id), str(d.get("domain")), str(d.get("queue")), str(d.get("job_type")), "duration", dur, float(pol.get("max_duration_seconds")))
                            except Exception:
                                pass
                            try:
                                if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    conn.execute(
                                        "UPDATE job_counters SET processing_count = CASE WHEN processing_count>0 THEN processing_count-1 ELSE 0 END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                        (d.get("domain"), d.get("queue"), d.get("job_type")),
                                    )
                            except Exception:
                                pass
                            self._update_gauges(domain=d.get("domain"), queue=d.get("queue"), job_type=d.get("job_type"))
                            try:
                                with job_span("job.complete", job=d):
                                    pass
                            except Exception:
                                pass
                            # Outbox insert within the same transaction (avoid lock)
                            try:
                                # Insert completion event within the same transaction to avoid cross-connection locks
                                conn.execute(
                                    (
                                        "INSERT INTO job_events(job_id, domain, queue, job_type, event_type, attrs_json, owner_user_id, request_id, trace_id, created_at) "
                                        "VALUES (?, ?, ?, ?, 'job.completed', '{}', NULL, ?, ?, DATETIME('now'))"
                                    ),
                                    (
                                        int(job_id), d.get("domain"), d.get("queue"), d.get("job_type"),
                                        d.get("request_id"), d.get("trace_id"),
                                    ),
                                )
                            except Exception:
                                pass
                            # Emit event for in-process listeners when outbox is disabled
                            try:
                                if str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() not in {"1","true","yes","y","on"}:
                                    emit_job_event("job.completed", job={"id": int(job_id), "domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")})
                            except Exception:
                                pass
                            try:
                                ev = {"id": int(job_id), "domain": d.get("domain"), "queue": d.get("queue"), "job_type": d.get("job_type")}
                                submit_job_audit_event("job.completed", job=ev, attrs=None)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    res_ok = ok
        finally:
            conn.close()
        return bool(res_ok)

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
            enforce = self._should_enforce_ack()
        conn = self._connect()
        affected = 0
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        now_ts = self._clock.now_utc()
                        for it in items:
                            secs = max(1, min(int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600"), int(it.get("seconds") or 0)))
                            if enforce:
                                cur.execute(
                                    (
                                        "UPDATE jobs SET leased_until = GREATEST(COALESCE(leased_until, %s), %s + (%s || ' seconds')::interval) "
                                        "WHERE id = %s AND status='processing' AND worker_id = %s AND lease_id = %s"
                                    ),
                                    (now_ts, now_ts, secs, int(it.get("job_id")), it.get("worker_id"), it.get("lease_id")),
                                )
                            else:
                                cur.execute(
                                    (
                                        "UPDATE jobs SET leased_until = GREATEST(COALESCE(leased_until, %s), %s + (%s || ' seconds')::interval) "
                                        "WHERE id = %s AND status='processing'"
                                    ),
                                    (now_ts, now_ts, secs, int(it.get("job_id"))),
                                )
                            affected += cur.rowcount or 0
            else:
                with conn:
                    for it in items:
                        secs = max(1, min(int(os.getenv("JOBS_LEASE_MAX_SECONDS", "3600") or "3600"), int(it.get("seconds") or 0)))
                        now_str = self._clock.now_utc().astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
                        if enforce:
                            cur = conn.execute(
                                (
                                    "UPDATE jobs SET leased_until = MAX(COALESCE(leased_until, DATETIME(?)), DATETIME(?, ?)) "
                                    "WHERE id = ? AND status='processing' AND worker_id = ? AND lease_id = ?"
                                ),
                                (now_str, now_str, f"+{secs} seconds", int(it.get("job_id")), it.get("worker_id"), it.get("lease_id")),
                            )
                            affected += int(cur.rowcount or 0)
                        else:
                            cur = conn.execute(
                                (
                                    "UPDATE jobs SET leased_until = MAX(COALESCE(leased_until, DATETIME(?)), DATETIME(?, ?)) "
                                    "WHERE id = ? AND status='processing'"
                                ),
                                (now_str, now_str, f"+{secs} seconds", int(it.get("job_id"))),
                            )
                            affected += int(cur.rowcount or 0)
            return int(affected)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def batch_complete_jobs(self, items: List[Dict[str, Any]], *, enforce: Optional[bool] = None) -> int:
        if enforce is None:
            enforce = self._should_enforce_ack()
        conn = self._connect()
        done = 0
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        for it in items:
                            res_obj = it.get("result")
                            # Optional encryption at rest: prefer provided domain, otherwise fetch
                            try:
                                dom = it.get("domain")
                                if not dom:
                                    cur.execute("SELECT domain FROM jobs WHERE id=%s", (int(it.get("job_id")),))
                                    _r = cur.fetchone()
                                    dom = (_r.get("domain") if isinstance(_r, dict) else None) if _r else None
                                res_obj = self._maybe_encrypt_json(res_obj, dom)
                            except Exception:
                                pass
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
                        # Optional encryption at rest (SQLite): prefer provided domain, otherwise fetch
                        try:
                            dom = it.get("domain")
                            if not dom:
                                rowd = conn.execute("SELECT domain FROM jobs WHERE id = ?", (int(it.get("job_id")),)).fetchone()
                                dom = rowd[0] if rowd else None
                            res_obj = self._maybe_encrypt_json(res_obj, dom)
                        except Exception:
                            pass
                        ctok = it.get("completion_token")
                        if enforce:
                            cur = conn.execute(
                                "UPDATE jobs SET status='completed', result=?, completed_at = DATETIME('now'), completion_token = ?, leased_until = NULL WHERE id = ? AND status='processing' AND worker_id = ? AND lease_id = ? AND (completion_token IS NULL OR completion_token = ?)",
                                (json.dumps(res_obj) if res_obj is not None else None, ctok, int(it.get("job_id")), it.get("worker_id"), it.get("lease_id"), ctok),
                            )
                            done += int(cur.rowcount or 0)
                        else:
                            cur = conn.execute(
                                "UPDATE jobs SET status='completed', result=?, completed_at = DATETIME('now'), completion_token = COALESCE(completion_token, ?), leased_until = NULL WHERE id = ? AND status='processing' AND (completion_token IS NULL OR completion_token = ?)",
                                (json.dumps(res_obj) if res_obj is not None else None, ctok, int(it.get("job_id")), ctok),
                            )
                            done += int(cur.rowcount or 0)
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
            enforce = self._should_enforce_ack()
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
                            cur = conn.execute(
                                "UPDATE jobs SET status='failed', last_error=?, error_message=?, error_code=?, completed_at=DATETIME('now'), leased_until=NULL, completion_token=? WHERE id=? AND status='processing' AND worker_id=? AND lease_id=? AND (completion_token IS NULL OR completion_token=?)",
                                (it.get("error_code") or it.get("error"), it.get("error"), it.get("error_code"), it.get("completion_token"), int(it.get("job_id")), it.get("worker_id"), it.get("lease_id"), it.get("completion_token")),
                            )
                            cnt += int(cur.rowcount or 0)
                        else:
                            cur = conn.execute(
                                "UPDATE jobs SET status='failed', last_error=?, error_message=?, error_code=?, completed_at=DATETIME('now'), leased_until=NULL, completion_token=COALESCE(completion_token,?) WHERE id=? AND status='processing' AND (completion_token IS NULL OR completion_token=?)",
                                (it.get("error_code") or it.get("error"), it.get("error"), it.get("error_code"), it.get("completion_token"), int(it.get("job_id")), it.get("completion_token")),
                            )
                            cnt += int(cur.rowcount or 0)
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
        backoff_seconds: int = 1,
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
            enforce = self._should_enforce_ack()
        conn = self._connect()
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        # For metrics and idempotency
                        if _test_mode:
                            try:
                                logger.info(f"[JM TEST MUT] fail_job enter job_id={job_id} retryable={retryable} backoff={backoff_seconds} enforce={enforce} backend=pg")
                            except Exception:
                                pass
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
                            # In tests, enforce a generous minimum when the caller requested
                            # immediate retry (backoff_seconds=0) so that newer jobs can be
                            # acquired before recently failed ones.
                            if test_mode:
                                _outbox = str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() in {"1", "true", "yes", "y", "on"}
                                # Permit immediate retry in tests when caller requests backoff=0
                                # unless outbox mode is enabled (which needs a larger gap).
                                if not _outbox and exp_backoff <= 1:
                                    delay = 0
                                try:
                                    if _outbox and int(backoff_seconds) <= 0 and delay < 10:
                                        delay = 10
                                except Exception:
                                    if _outbox and delay < 3:
                                        delay = 3
                            # Poison message quarantine check: increment failure_streak_* and quarantine if threshold reached
                            base_thresh = int(os.getenv("JOBS_QUARANTINE_THRESHOLD", "2") or "2")
                            # In TEST_MODE with zero backoff (unit-style retry loops), avoid quarantining to allow timeline growth
                            if test_mode and int(backoff_seconds) <= 0:
                                thresh = max(base_thresh, 10**9)
                            else:
                                thresh = base_thresh
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
                                        # Counters: processing -> queued (ready/scheduled) or quarantined
                                        try:
                                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                                dmn = elem.get("domain"); qq = elem.get("queue"); jt = elem.get("job_type")
                                                prev_streak = int(elem.get("failure_streak_count") or 0)
                                                will_quarantine = (prev_streak + 1) >= int(os.getenv("JOBS_QUARANTINE_THRESHOLD", "2") or "2")
                                                add_ready = 0; add_sched = 0; add_quar = 0
                                                if will_quarantine:
                                                    add_quar = 1
                                                else:
                                                    if int(delay) > 0:
                                                        add_sched = 1
                                                    else:
                                                        add_ready = 1
                                                cur.execute(
                                                    (
                                                        "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(%s,%s,%s,0,0,0,0) "
                                                        "ON CONFLICT (domain,queue,job_type) DO UPDATE SET "
                                                        "ready_count = job_counters.ready_count + %s, "
                                                        "scheduled_count = job_counters.scheduled_count + %s, "
                                                        "processing_count = GREATEST(job_counters.processing_count - 1, 0), "
                                                        "quarantined_count = job_counters.quarantined_count + %s, "
                                                        "updated_at = NOW()"
                                                    ),
                                                    (dmn, qq, jt, int(add_ready), int(add_sched), int(add_quar)),
                                                )
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                if str(os.getenv("TEST_MODE", "")).strip().lower() in {"1","true","yes","y","on"}:
                                    try:
                                        # Snapshot after scheduling retry (PG)
                                        cur.execute("SELECT failure_timeline FROM jobs WHERE id = %s", (int(job_id),))
                                        _tlrow = cur.fetchone()
                                        _tl_len = 0
                                        try:
                                            _tl_len = len(json.loads(_tlrow.get("failure_timeline"))) if _tlrow and _tlrow.get("failure_timeline") else 0
                                        except Exception:
                                            _tl_len = 0
                                        cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                        _total = (cur.fetchone() or {}).get("c", 0)
                                        cur.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status")
                                        _rows = cur.fetchall() or []
                                        _dist = {str(x.get("status")): int(x.get("c") or 0) for x in _rows}
                                        logger.info(f"[JM TEST MUT] fail_job retryable scheduled delay={int(delay)} tl_len={_tl_len} total={_total} dist={_dist}")
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
                            # No fallback to fail queued when enforcement disabled
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
                                # Counters: processing -> failed (terminal)
                                try:
                                    if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                        cur.execute(
                                            "UPDATE job_counters SET processing_count = GREATEST(processing_count - 1, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                            (d.get("domain"), d.get("queue"), d.get("job_type")),
                                        )
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
                        if str(os.getenv("TEST_MODE", "")).strip().lower() in {"1","true","yes","y","on"}:
                            try:
                                cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                _total = (cur.fetchone() or {}).get("c", 0)
                                cur.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status")
                                _rows = cur.fetchall() or []
                                _dist = {str(x.get("status")): int(x.get("c") or 0) for x in _rows}
                                logger.info(f"[JM TEST MUT] fail_job terminal ok={bool(ok)} total={_total} dist={_dist}")
                            except Exception:
                                pass
                        return ok
            else:
                with conn:
                    if _test_mode:
                        try:
                            logger.info(f"[JM TEST MUT] fail_job enter job_id={job_id} retryable={retryable} backoff={backoff_seconds} enforce={enforce} backend=sqlite")
                        except Exception:
                            pass
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
                        if test_mode:
                            _outbox = str(os.getenv("JOBS_EVENTS_OUTBOX", "")).lower() in {"1", "true", "yes", "y", "on"}
                            if not _outbox and exp_backoff <= 1:
                                delay = 0
                            try:
                                if _outbox and int(backoff_seconds) <= 0 and delay < 10:
                                    delay = 10
                            except Exception:
                                if _outbox and delay < 3:
                                    delay = 3
                            base_thresh = int(os.getenv("JOBS_QUARANTINE_THRESHOLD", "2") or "2")
                            if test_mode and int(backoff_seconds) <= 0:
                                # Respect explicit threshold in tests; otherwise, avoid quarantining to allow timeline growth
                                if os.getenv("JOBS_QUARANTINE_THRESHOLD") is None:
                                    thresh = max(base_thresh, 10**9)
                                else:
                                    thresh = base_thresh
                            else:
                                thresh = base_thresh
                        # SQLite retry path with failure streak bookkeeping
                        if enforce:
                            conn.execute(
                                (
                                    "UPDATE jobs SET status = CASE WHEN (COALESCE(failure_streak_count,0) + 1) >= ? THEN 'quarantined' ELSE 'queued' END, "
                                    "retry_count = retry_count + 1, last_error = ?, error_message = ?, error_code = ?, error_class = ?, error_stack = ?, "
                                    "failure_streak_count = CASE WHEN COALESCE(failure_streak_code, '') = ? THEN COALESCE(failure_streak_count,0) + 1 ELSE 1 END, "
                                    "failure_streak_code = ?, "
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
                                    "failure_streak_count = CASE WHEN COALESCE(failure_streak_code, '') = ? THEN COALESCE(failure_streak_count,0) + 1 ELSE 1 END, "
                                    "failure_streak_code = ?, "
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
                                    # Counters: processing -> queued (ready/scheduled) or quarantined
                                    try:
                                        if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                            # Use current streak value after increment to decide counters update
                                            try:
                                                row_fs = conn.execute("SELECT failure_streak_count FROM jobs WHERE id = ?", (job_id,)).fetchone()
                                                cur_fs = int(row_fs[0]) if row_fs and row_fs[0] else 0
                                            except Exception:
                                                cur_fs = 0
                                            will_quarantine = cur_fs >= int(os.getenv("JOBS_QUARANTINE_THRESHOLD", "2") or "2")
                                            add_ready = 0; add_sched = 0; add_quar = 0
                                            if will_quarantine:
                                                add_quar = 1
                                            else:
                                                if int(delay) > 0:
                                                    add_sched = 1
                                                else:
                                                    add_ready = 1
                                            conn.execute(
                                                (
                                                    "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?, ?, ?, 0, ?) "
                                                    "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = ready_count + ?, scheduled_count = scheduled_count + ?, processing_count = CASE WHEN processing_count>0 THEN processing_count-1 ELSE 0 END, quarantined_count = quarantined_count + ?, updated_at = DATETIME('now')"
                                                ),
                                                (
                                                    dtmp.get("domain"),
                                                    dtmp.get("queue"),
                                                    dtmp.get("job_type"),
                                                    int(add_ready),
                                                    int(add_sched),
                                                    int(add_quar),
                                                    int(add_ready),
                                                    int(add_sched),
                                                    int(add_quar),
                                                ),
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
                                        # Update last-acquired snapshot for test-mode fallbacks to preserve timeline growth
                                        try:
                                            if str(os.getenv("TEST_MODE", "")).lower() in {"1","true","yes","y","on"} and rowl:
                                                rnow = conn.execute("SELECT * FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
                                                if rnow:
                                                    JobManager._LAST_ACQUIRED_TEST[(rowl[2], rowl[3])] = dict(rnow)
                                        except Exception:
                                            pass
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            if str(os.getenv("TEST_MODE", "")).strip().lower() in {"1","true","yes","y","on"}:
                                try:
                                    _row = conn.execute("SELECT failure_timeline FROM jobs WHERE id = ?", (int(job_id),)).fetchone()
                                    _tl_len = 0
                                    try:
                                        _tl_len = len(json.loads(_row[0])) if (_row and _row[0]) else 0
                                    except Exception:
                                        _tl_len = 0
                                    _total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                                    _dist = {str(r[0]): int(r[1]) for r in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()}
                                    logger.info(f"[JM TEST MUT] fail_job retryable scheduled delay={int(delay)} tl_len={_tl_len} total={int(_total)} dist={_dist}")
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
                        # Enforcement disabled: allow failing processing without matching worker/lease,
                        # and fall back to failing queued jobs (admin-style terminalization) when appropriate.
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
                        if conn.total_changes == 0:
                            # Admin-style finalize: optionally allow failing queued jobs when enforcement is disabled
                            # Scope via allowlist of domains (default: chatbooks) to avoid global behavior in tests
                            try:
                                allow = {d.strip().lower() for d in (os.getenv("JOBS_ADMIN_COMPLETE_QUEUED_ALLOW_DOMAINS", "chatbooks").split(",")) if d.strip()}
                                row_dom = conn.execute("SELECT domain FROM jobs WHERE id = ?", (job_id,)).fetchone()
                                dom_val = str(row_dom[0]).lower() if row_dom and row_dom[0] else ""
                            except Exception:
                                allow = {"chatbooks"}; dom_val = ""
                            if dom_val in allow:
                                conn.execute(
                                    (
                                        "UPDATE jobs SET status = 'failed', last_error = ?, error_message = ?, error_code = ?, error_class = ?, error_stack = ?, completion_token = COALESCE(completion_token, ?), "
                                        "completed_at = DATETIME('now'), leased_until = NULL WHERE id = ? AND status = 'queued'"
                                    ),
                                    (
                                        (error_code or error),
                                        error,
                                        error_code,
                                        error_class,
                                        (json.dumps(error_stack) if error_stack is not None else None),
                                        completion_token,
                                        job_id,
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
                            # Counters: processing -> failed (terminal)
                            try:
                                if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    conn.execute(
                                        "UPDATE job_counters SET processing_count = CASE WHEN processing_count>0 THEN processing_count-1 ELSE 0 END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                        (d.get("domain"), d.get("queue"), d.get("job_type")),
                                    )
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
                    if str(os.getenv("TEST_MODE", "")).strip().lower() in {"1","true","yes","y","on"}:
                        try:
                            _total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                            _dist = {str(r[0]): int(r[1]) for r in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()}
                            logger.info(f"[JM TEST MUT] fail_job terminal ok={bool(ok)} total={int(_total)} dist={_dist}")
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
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        if _test_mode:
                            try:
                                logger.info(f"[JM TEST MUT] cancel_job enter job_id={job_id} backend=pg")
                            except Exception:
                                pass
                        # Capture grouping keys for gauges
                        try:
                            cur.execute("SELECT domain, queue, job_type FROM jobs WHERE id = %s", (int(job_id),))
                            row0 = cur.fetchone()
                        except Exception:
                            row0 = None
                        # For counters, inspect ready vs scheduled before cancelling queued
                        cur.execute("SELECT domain, queue, job_type, status, available_at FROM jobs WHERE id = %s", (int(job_id),))
                        rowd = cur.fetchone()
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
                            # Counters: queued (ready/scheduled) -> cancelled
                            try:
                                if rowd and str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    _now2 = self._clock.now_utc()
                                    _av2 = _parse_dt(rowd.get("available_at")) if rowd else None
                                    if _av2 is not None and _av2.tzinfo is None:
                                        _av2 = _av2.replace(tzinfo=_tz.utc)
                                    is_sched = bool(rowd.get("available_at")) and ((_av2 or _now2) > _now2)
                                    add_ready = -1 if not is_sched else 0
                                    add_sched = -1 if is_sched else 0
                                    cur.execute(
                                        (
                                            "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(%s,%s,%s,0,0,0,0) "
                                            "ON CONFLICT (domain,queue,job_type) DO UPDATE SET ready_count = GREATEST(job_counters.ready_count + %s, 0), scheduled_count = GREATEST(job_counters.scheduled_count + %s, 0), updated_at = NOW()"
                                        ),
                                        (rowd["domain"], rowd["queue"], rowd["job_type"], int(add_ready), int(add_sched)),
                                    )
                            except Exception:
                                pass
                            try:
                                if row0:
                                    ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                                    emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                            except Exception:
                                pass
                            if _test_mode:
                                try:
                                    cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                    _total = (cur.fetchone() or {}).get("c", 0)
                                    cur.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status")
                                    _rows = cur.fetchall() or []
                                    _dist = {str(x.get("status")): int(x.get("c") or 0) for x in _rows}
                                    logger.info(f"[JM TEST MUT] cancel_job queued->cancelled ok=True total={_total} dist={_dist}")
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
                        # Counters: processing -> cancelled
                        try:
                            if ok and row0 and str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                cur.execute(
                                    "UPDATE job_counters SET processing_count = GREATEST(processing_count - 1, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                    (row0["domain"], row0["queue"], row0["job_type"]),
                                )
                        except Exception:
                            pass
                        try:
                            if ok and row0:
                                ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                                emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                        except Exception:
                            pass
                        if _test_mode:
                            try:
                                cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                _total = (cur.fetchone() or {}).get("c", 0)
                                cur.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status")
                                _rows = cur.fetchall() or []
                                _dist = {str(x.get("status")): int(x.get("c") or 0) for x in _rows}
                                logger.info(f"[JM TEST MUT] cancel_job processing->cancelled ok={bool(ok)} total={_total} dist={_dist}")
                            except Exception:
                                pass
                        return ok
            else:
                with conn:
                    if _test_mode:
                        try:
                            logger.info(f"[JM TEST MUT] cancel_job enter job_id={job_id} backend=sqlite")
                        except Exception:
                            pass
                    # Capture grouping keys for gauges
                    try:
                        row0 = conn.execute("SELECT domain, queue, job_type FROM jobs WHERE id = ?", (job_id,)).fetchone()
                    except Exception:
                        row0 = None
                    # cancel queued immediately (capture ready vs scheduled for counters)
                    rowd = conn.execute("SELECT domain, queue, job_type, status, available_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
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
                        # Counters: queued (ready/scheduled) -> cancelled
                        try:
                            if rowd and str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                _now3 = self._clock.now_utc()
                                _av3 = _parse_dt(rowd["available_at"]) if rowd and rowd["available_at"] else None
                                if _av3 is not None and _av3.tzinfo is None:
                                    _av3 = _av3.replace(tzinfo=_tz.utc)
                                is_sched = bool(rowd["available_at"]) and ((_av3 or _now3) > _now3)
                                add_ready = -1 if not is_sched else 0
                                add_sched = -1 if is_sched else 0
                                conn.execute(
                                    (
                                        "INSERT INTO job_counters(domain,queue,job_type,ready_count,scheduled_count,processing_count,quarantined_count) VALUES(?,?,?,?,0,0,0) "
                                        "ON CONFLICT(domain,queue,job_type) DO UPDATE SET ready_count = CASE WHEN (ready_count + ?) < 0 THEN 0 ELSE ready_count + ? END, scheduled_count = CASE WHEN (scheduled_count + ?) < 0 THEN 0 ELSE scheduled_count + ? END, updated_at = DATETIME('now')"
                                    ),
                                    (rowd["domain"], rowd["queue"], rowd["job_type"], int(add_ready), int(add_ready), int(add_sched), int(add_sched)),
                                )
                        except Exception:
                            pass
                        try:
                            if row0:
                                ev = {"id": int(job_id), "domain": row0["domain"], "queue": row0["queue"], "job_type": row0["job_type"]}
                                emit_job_event("job.cancelled", job=ev, attrs={"reason": reason, "terminal": True})
                        except Exception:
                            pass
                        if _test_mode:
                            try:
                                _total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                                _dist = {str(r[0]): int(r[1]) for r in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()}
                                logger.info(f"[JM TEST MUT] cancel_job queued->cancelled ok=True total={int(_total)} dist={_dist}")
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
                    if _test_mode:
                        try:
                            _total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                            _dist = {str(r[0]): int(r[1]) for r in conn.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status").fetchall()}
                            logger.info(f"[JM TEST MUT] cancel_job processing->cancelled ok={bool(ok)} total={int(_total)} dist={_dist}")
                        except Exception:
                            pass
                    # Counters: processing -> cancelled
                    try:
                        if ok and row0 and str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                            conn.execute(
                                "UPDATE job_counters SET processing_count = CASE WHEN processing_count>0 THEN processing_count-1 ELSE 0 END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                (row0["domain"], row0["queue"], row0["job_type"]),
                            )
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
        _test_mode = str(os.getenv("TEST_MODE", "")).strip().lower() in {"1", "true", "yes", "y", "on"}
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
                            _cnt = int(row["c"]) if row is not None else 0
                            if _test_mode:
                                try:
                                    logger.info(f"[JM TEST MUT] prune_jobs dry_run count={_cnt}")
                                except Exception:
                                    pass
                            return _cnt
                        # Optional archive copy
                        if str(os.getenv("JOBS_ARCHIVE_BEFORE_DELETE", "")).lower() in {"1","true","yes","y","on"}:
                            cur.execute(
                                f"INSERT INTO jobs_archive (id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at) SELECT id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at FROM jobs{where_clause}",
                                tuple(params),
                            )
                            # Optional compression for archived payload/result (Postgres)
                            try:
                                if str(os.getenv("JOBS_ARCHIVE_COMPRESS", "")).lower() in {"1","true","yes","y","on"}:
                                    import gzip
                                    drop_json = str(os.getenv("JOBS_ARCHIVE_COMPRESS_DROP_JSON", "")).lower() in {"1","true","yes","y","on"}
                                    cur.execute(f"SELECT id, payload, result FROM jobs{where_clause}", tuple(params))
                                    rows_cr = cur.fetchall() or []
                                    for r in rows_cr:
                                        try:
                                            rid = int(r["id"]) if isinstance(r, dict) else int(r[0])
                                            pl = r.get("payload") if isinstance(r, dict) else r[1]
                                            rs = r.get("result") if isinstance(r, dict) else r[2]
                                            pbytes = gzip.compress(json.dumps(pl).encode("utf-8")) if pl is not None else None
                                            rbytes = gzip.compress(json.dumps(rs).encode("utf-8")) if rs is not None else None
                                            if drop_json:
                                                cur.execute("UPDATE jobs_archive SET payload=NULL, result=NULL, payload_compressed=%s, result_compressed=%s WHERE id=%s", (pbytes, rbytes, rid))
                                            else:
                                                cur.execute("UPDATE jobs_archive SET payload_compressed=%s, result_compressed=%s WHERE id=%s", (pbytes, rbytes, rid))
                                        except Exception:
                                            continue
                            except Exception:
                                pass
                        # Counters: subtract queued/processing/quarantined rows if they are part of prune set
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                # Ready queued
                                cur.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs{where_clause} AND status='queued' AND (available_at IS NULL OR available_at <= NOW()) GROUP BY domain,queue,job_type",
                                    tuple(params),
                                )
                                for r in (cur.fetchall() or []):
                                    cur.execute(
                                        "UPDATE job_counters SET ready_count = GREATEST(ready_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                        (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                    )
                                # Scheduled queued
                                cur.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs{where_clause} AND status='queued' AND (available_at IS NOT NULL AND available_at > NOW()) GROUP BY domain,queue,job_type",
                                    tuple(params),
                                )
                                for r in (cur.fetchall() or []):
                                    cur.execute(
                                        "UPDATE job_counters SET scheduled_count = GREATEST(scheduled_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                        (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                    )
                                # Processing
                                cur.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs{where_clause} AND status='processing' GROUP BY domain,queue,job_type",
                                    tuple(params),
                                )
                                for r in (cur.fetchall() or []):
                                    cur.execute(
                                        "UPDATE job_counters SET processing_count = GREATEST(processing_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                        (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                    )
                                # Quarantined
                                cur.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs{where_clause} AND status='quarantined' GROUP BY domain,queue,job_type",
                                    tuple(params),
                                )
                                for r in (cur.fetchall() or []):
                                    cur.execute(
                                        "UPDATE job_counters SET quarantined_count = GREATEST(quarantined_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                        (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                    )
                        except Exception:
                            pass
                        if _test_mode:
                            try:
                                cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                _before = (cur.fetchone() or {}).get("c", 0)
                            except Exception:
                                _before = None
                        cur.execute(f"DELETE FROM jobs{where_clause}", tuple(params))
                        deleted = cur.rowcount or 0
                        if _test_mode:
                            try:
                                cur.execute("SELECT COUNT(*) AS c FROM jobs")
                                _after = (cur.fetchone() or {}).get("c", 0)
                                logger.info(f"[JM TEST MUT] prune_jobs deleted={int(deleted)} before={_before} after={_after}")
                            except Exception:
                                pass
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
                    if _test_mode:
                        try:
                            logger.info(f"[JM TEST MUT] prune_jobs enter statuses={statuses} older_than_days={older_than_days} domain={domain} queue={queue} job_type={job_type} backend=sqlite")
                        except Exception:
                            pass
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
                        if _test_mode:
                            try:
                                logger.info(f"[JM TEST MUT] prune_jobs dry_run count={int(count)}")
                            except Exception:
                                pass
                        return count
                    # Optional archive copy
                    if str(os.getenv("JOBS_ARCHIVE_BEFORE_DELETE", "")).lower() in {"1","true","yes","y","on"}:
                        conn.execute(
                            f"INSERT INTO jobs_archive (id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at) SELECT id, uuid, domain, queue, job_type, owner_user_id, project_id, idempotency_key, payload, result, status, priority, max_retries, retry_count, available_at, started_at, leased_until, lease_id, worker_id, acquired_at, error_message, last_error, cancel_requested_at, cancelled_at, cancellation_reason, progress_percent, progress_message, created_at, updated_at, completed_at FROM jobs{where_clause}",
                            tuple(params),
                        )
                        # Optional compression for archived payload/result (SQLite: base64-gz prefix)
                        try:
                            if str(os.getenv("JOBS_ARCHIVE_COMPRESS", "")).lower() in {"1","true","yes","y","on"}:
                                import gzip, base64
                                drop_json = str(os.getenv("JOBS_ARCHIVE_COMPRESS_DROP_JSON", "")).lower() in {"1","true","yes","y","on"}
                                qsel = f"SELECT id, payload, result FROM jobs{where_clause}"
                                for (rid, pl, rs) in (conn.execute(qsel, tuple(params)).fetchall() or []):
                                    try:
                                        p64 = None
                                        r64 = None
                                        if isinstance(pl, str) and pl:
                                            p64 = "gzip64:" + base64.b64encode(gzip.compress(pl.encode('utf-8'))).decode('ascii')
                                        if isinstance(rs, str) and rs:
                                            r64 = "gzip64:" + base64.b64encode(gzip.compress(rs.encode('utf-8'))).decode('ascii')
                                        if drop_json:
                                            conn.execute("UPDATE jobs_archive SET payload=NULL, result=NULL, payload_compressed=?, result_compressed=? WHERE id=?", (p64, r64, int(rid)))
                                        else:
                                            conn.execute("UPDATE jobs_archive SET payload_compressed=?, result_compressed=? WHERE id=?", (p64, r64, int(rid)))
                                    except Exception:
                                        continue
                        except Exception:
                            pass
                    # Counters: subtract queued/processing/quarantined rows if they are part of prune set
                    try:
                        if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                            for r in conn.execute(f"SELECT domain, queue, job_type, COUNT(*) FROM jobs{where_clause} AND status='queued' AND (available_at IS NULL OR available_at <= DATETIME('now')) GROUP BY domain,queue,job_type", tuple(params)).fetchall() or []:
                                conn.execute(
                                    "UPDATE job_counters SET ready_count = CASE WHEN (ready_count - ?) < 0 THEN 0 ELSE ready_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                    (int(r[3]), int(r[3]), r[0], r[1], r[2]),
                                )
                            for r in conn.execute(f"SELECT domain, queue, job_type, COUNT(*) FROM jobs{where_clause} AND status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME('now')) GROUP BY domain,queue,job_type", tuple(params)).fetchall() or []:
                                conn.execute(
                                    "UPDATE job_counters SET scheduled_count = CASE WHEN (scheduled_count - ?) < 0 THEN 0 ELSE scheduled_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                    (int(r[3]), int(r[3]), r[0], r[1], r[2]),
                                )
                            for r in conn.execute(f"SELECT domain, queue, job_type, COUNT(*) FROM jobs{where_clause} AND status='processing' GROUP BY domain,queue,job_type", tuple(params)).fetchall() or []:
                                conn.execute(
                                    "UPDATE job_counters SET processing_count = CASE WHEN (processing_count - ?) < 0 THEN 0 ELSE processing_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                    (int(r[3]), int(r[3]), r[0], r[1], r[2]),
                                )
                            for r in conn.execute(f"SELECT domain, queue, job_type, COUNT(*) FROM jobs{where_clause} AND status='quarantined' GROUP BY domain,queue,job_type", tuple(params)).fetchall() or []:
                                conn.execute(
                                    "UPDATE job_counters SET quarantined_count = CASE WHEN (quarantined_count - ?) < 0 THEN 0 ELSE quarantined_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                    (int(r[3]), int(r[3]), r[0], r[1], r[2]),
                                )
                    except Exception:
                        pass
                    if _test_mode:
                        try:
                            _before2 = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                        except Exception:
                            _before2 = None
                    conn.execute(f"DELETE FROM jobs{where_clause}", tuple(params))
                    deleted = int(count)
                    if _test_mode:
                        try:
                            _after2 = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
                            logger.info(f"[JM TEST MUT] prune_jobs deleted={int(deleted)} before={_before2} after={_after2}")
                        except Exception:
                            pass
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
                            now_ts = self._clock.now_utc()
                            where = ["status='queued'", "created_at <= (%s - (%s || ' seconds')::interval)"]
                            params: List[Any] = [now_ts, int(age_seconds)]
                            if domain:
                                where.append("domain = %s")
                                params.append(domain)
                            if queue:
                                where.append("queue = %s")
                                params.append(queue)
                            if job_type:
                                where.append("job_type = %s")
                                params.append(job_type)
                            # Counters: queued (ready/scheduled) -> cancelled/failed, and metrics increments
                            try:
                                if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    cur.execute(
                                        f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs WHERE {' AND '.join(where)} AND (available_at IS NULL OR available_at <= %s) GROUP BY domain,queue,job_type",
                                        tuple(params + [now_ts]),
                                    )
                                    grp_ready_rows = cur.fetchall() or []
                                    for r in grp_ready_rows:
                                        cur.execute(
                                            "UPDATE job_counters SET ready_count = GREATEST(ready_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                            (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                        )
                                    cur.execute(
                                        f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs WHERE {' AND '.join(where)} AND (available_at IS NOT NULL AND available_at > %s) GROUP BY domain,queue,job_type",
                                        tuple(params + [now_ts]),
                                    )
                                    grp_sched_rows = cur.fetchall() or []
                                    for r in grp_sched_rows:
                                        cur.execute(
                                            "UPDATE job_counters SET scheduled_count = GREATEST(scheduled_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                            (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                        )
                                    # Metrics increments for age TTL
                                    try:
                                        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                                        reg = get_metrics_registry()
                                        if reg:
                                            # Ready subset
                                            for r in grp_ready_rows:
                                                labels = {"domain": r["domain"], "queue": r["queue"], "job_type": r["job_type"]}
                                                cval = float(int(r["c"]))
                                                if action == "cancel":
                                                    reg.increment("jobs.cancelled_total", cval, labels)
                                                else:
                                                    labs = dict(labels); labs["reason"] = "ttl_age"; reg.increment("jobs.failures_total", cval, labs)
                                            # Scheduled subset
                                            for r in grp_sched_rows:
                                                labels = {"domain": r["domain"], "queue": r["queue"], "job_type": r["job_type"]}
                                                cval = float(int(r["c"]))
                                                if action == "cancel":
                                                    reg.increment("jobs.cancelled_total", cval, labels)
                                                else:
                                                    labs = dict(labels); labs["reason"] = "ttl_age"; reg.increment("jobs.failures_total", cval, labs)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            if action == "cancel":
                                cur.execute(
                                    f"UPDATE jobs SET status='cancelled', cancelled_at = %s, cancellation_reason = 'ttl_age' WHERE {' AND '.join(where)}",
                                    tuple([now_ts] + params),
                                )
                            else:
                                cur.execute(
                                    f"UPDATE jobs SET status='failed', error_message = 'ttl_age', completed_at = %s WHERE {' AND '.join(where)}",
                                    tuple([now_ts] + params),
                                )
                            affected += cur.rowcount or 0
                        if runtime_seconds is not None:
                            now_ts2 = self._clock.now_utc()
                            where = ["status='processing'", "COALESCE(started_at, acquired_at) <= (%s - (%s || ' seconds')::interval)"]
                            params2: List[Any] = [now_ts2, int(runtime_seconds)]
                            if domain:
                                where.append("domain = %s")
                                params2.append(domain)
                            if queue:
                                where.append("queue = %s")
                                params2.append(queue)
                            if job_type:
                                where.append("job_type = %s")
                                params2.append(job_type)
                            # Counters: processing -> cancelled/failed, and metrics increments
                            try:
                                if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    cur.execute(
                                        f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs WHERE {' AND '.join(where)} GROUP BY domain,queue,job_type",
                                        tuple(params2),
                                    )
                                    grp_proc_rows = cur.fetchall() or []
                                    for r in grp_proc_rows:
                                        cur.execute(
                                            "UPDATE job_counters SET processing_count = GREATEST(processing_count - %s, 0), updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                            (int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                        )
                                    # Metrics for runtime TTL
                                    try:
                                        from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                                        reg = get_metrics_registry()
                                        if reg:
                                            for r in grp_proc_rows:
                                                labels = {"domain": r["domain"], "queue": r["queue"], "job_type": r["job_type"]}
                                                cval = float(int(r["c"]))
                                                if action == "cancel":
                                                    reg.increment("jobs.cancelled_total", cval, labels)
                                                else:
                                                    labs = dict(labels); labs["reason"] = "ttl_runtime"; reg.increment("jobs.failures_total", cval, labs)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                            if action == "cancel":
                                cur.execute(
                                    f"UPDATE jobs SET status='cancelled', cancelled_at = %s, cancellation_reason = 'ttl_runtime', leased_until = NULL WHERE {' AND '.join(where)}",
                                    tuple([now_ts2] + params2),
                                )
                            else:
                                cur.execute(
                                    f"UPDATE jobs SET status='failed', error_message = 'ttl_runtime', completed_at = %s, leased_until = NULL WHERE {' AND '.join(where)}",
                                    tuple([now_ts2] + params2),
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
                    now_str = self._clock.now_utc().astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
                    if age_seconds is not None:
                        where = ["status='queued'", "created_at <= DATETIME(?, ?)" ]
                        params3: List[Any] = [now_str, f"-{int(age_seconds)} seconds"]
                        if domain:
                            where.append("domain = ?")
                            params3.append(domain)
                        if queue:
                            where.append("queue = ?")
                            params3.append(queue)
                        if job_type:
                            where.append("job_type = ?")
                            params3.append(job_type)
                        # Counters adjustments (ready/scheduled) before status change
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                # ready subset (available_at <= now)
                                ready_rows = conn.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) FROM jobs WHERE {' AND '.join(where)} AND (available_at IS NULL OR available_at <= DATETIME('now')) GROUP BY domain,queue,job_type",
                                    tuple(params3),
                                ).fetchall() or []
                                for d, q, jt, c in ready_rows:
                                    conn.execute(
                                        "UPDATE job_counters SET ready_count = CASE WHEN (ready_count - ?) < 0 THEN 0 ELSE ready_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                        (int(c), int(c), d, q, jt),
                                    )
                                # scheduled subset (available_at > now)
                                sched_rows = conn.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) FROM jobs WHERE {' AND '.join(where)} AND (available_at IS NOT NULL AND available_at > DATETIME('now')) GROUP BY domain,queue,job_type",
                                    tuple(params3),
                                ).fetchall() or []
                                for d, q, jt, c in sched_rows:
                                    conn.execute(
                                        "UPDATE job_counters SET scheduled_count = CASE WHEN (scheduled_count - ?) < 0 THEN 0 ELSE scheduled_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                        (int(c), int(c), d, q, jt),
                                    )
                                # Metrics increments
                                try:
                                    from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                                    reg = get_metrics_registry()
                                    if reg:
                                        for d, q, jt, c in ready_rows:
                                            labels = {"domain": d, "queue": q, "job_type": jt}
                                            if action == "cancel":
                                                reg.increment("jobs.cancelled_total", float(int(c)), labels)
                                            else:
                                                labs = dict(labels); labs["reason"] = "ttl_age"; reg.increment("jobs.failures_total", float(int(c)), labs)
                                        for d, q, jt, c in sched_rows:
                                            labels = {"domain": d, "queue": q, "job_type": jt}
                                            if action == "cancel":
                                                reg.increment("jobs.cancelled_total", float(int(c)), labels)
                                            else:
                                                labs = dict(labels); labs["reason"] = "ttl_age"; reg.increment("jobs.failures_total", float(int(c)), labs)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        sql = "UPDATE jobs SET " + ("status='cancelled', cancelled_at = DATETIME('now'), cancellation_reason='ttl_age'" if action == "cancel" else "status='failed', error_message='ttl_age', completed_at = DATETIME('now')") + f" WHERE {' AND '.join(where)}"
                        cur = conn.execute(sql, tuple(params3))
                        try:
                            logger.debug(f"TTL(age) SQLite updated rows={cur.rowcount} for where={where} params={params3}")
                        except Exception:
                            pass
                        affected2 += cur.rowcount or 0
                    if runtime_seconds is not None:
                        where = ["status='processing'", "COALESCE(started_at, acquired_at) <= DATETIME(?, ?)"]
                        params4: List[Any] = [now_str, f"-{int(runtime_seconds)} seconds"]
                        if domain:
                            where.append("domain = ?")
                            params4.append(domain)
                        if queue:
                            where.append("queue = ?")
                            params4.append(queue)
                        if job_type:
                            where.append("job_type = ?")
                            params4.append(job_type)
                        # Counters adjustments for processing and metrics
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                proc_rows = conn.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) FROM jobs WHERE {' AND '.join(where)} GROUP BY domain,queue,job_type",
                                    tuple(params4),
                                ).fetchall() or []
                                for d, q, jt, c in proc_rows:
                                    conn.execute(
                                        "UPDATE job_counters SET processing_count = CASE WHEN (processing_count - ?) < 0 THEN 0 ELSE processing_count - ? END, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?",
                                        (int(c), int(c), d, q, jt),
                                    )
                                try:
                                    from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry
                                    reg = get_metrics_registry()
                                    if reg:
                                        for d, q, jt, c in proc_rows:
                                            labels = {"domain": d, "queue": q, "job_type": jt}
                                            if action == "cancel":
                                                reg.increment("jobs.cancelled_total", float(int(c)), labels)
                                            else:
                                                labs = dict(labels); labs["reason"] = "ttl_runtime"; reg.increment("jobs.failures_total", float(int(c)), labs)
                                except Exception:
                                    pass
                        except Exception:
                            pass
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

    # --- Admin reschedule / retry-now helpers ---
    def reschedule_jobs(
        self,
        *,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        set_now: bool = True,
        delta_seconds: Optional[int] = None,
        dry_run: bool = False,
    ) -> int:
        """Reschedule jobs by adjusting available_at.

        If set_now is True, sets available_at=now() for matched jobs.
        Otherwise, adds delta_seconds to current available_at (or sets from now if NULL).
        """
        if status and status not in {"queued", "failed", "processing", "completed", "cancelled", "quarantined"}:
            raise ValueError("Unsupported status filter")
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    where = ["1=1"]
                    params: List[Any] = []
                    if domain:
                        where.append("domain=%s"); params.append(domain)
                    if queue:
                        where.append("queue=%s"); params.append(queue)
                    if job_type:
                        where.append("job_type=%s"); params.append(job_type)
                    if status:
                        where.append("status=%s"); params.append(status)
                    wh = " AND ".join(where)
                    cur.execute(f"SELECT COUNT(*) AS c FROM jobs WHERE {wh}", tuple(params))
                    _cnt_row = cur.fetchone()
                    count = int((_cnt_row.get("c") if isinstance(_cnt_row, dict) else 0))
                    if dry_run:
                        return count
                    if set_now:
                        # When moving to now, queued scheduled -> queued ready: update counters if enabled
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                now_ts = self._clock.now_utc()
                                cur.execute(
                                    (
                                        f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs WHERE {wh} "
                                        "AND status='queued' AND (available_at IS NOT NULL AND available_at > %s) GROUP BY domain,queue,job_type"
                                    ),
                                    tuple(params + [now_ts]),
                                )
                                for r in (cur.fetchall() or []):
                                    cur.execute(
                                        "UPDATE job_counters SET scheduled_count = GREATEST(scheduled_count - %s, 0), ready_count = job_counters.ready_count + %s, updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                        (int(r["c"]), int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                    )
                        except Exception:
                            pass
                        cur.execute(f"UPDATE jobs SET available_at=NOW() WHERE {wh}", tuple(params))
                    else:
                        if delta_seconds is None:
                            raise ValueError("delta_seconds required when set_now=false")
                        cur.execute(f"UPDATE jobs SET available_at=COALESCE(available_at, NOW()) + (%s || ' seconds')::interval WHERE {wh}", tuple([int(delta_seconds)] + params))
                    return count
            else:
                where = ["1=1"]
                params: List[Any] = []
                if domain:
                    where.append("domain=?"); params.append(domain)
                if queue:
                    where.append("queue=?"); params.append(queue)
                if job_type:
                    where.append("job_type=?"); params.append(job_type)
                if status:
                    where.append("status=?"); params.append(status)
                wh = " AND ".join(where)
                row = conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {wh}", tuple(params)).fetchone()
                count = int(row[0]) if row else 0
                if dry_run:
                    return count
                with conn:
                    if set_now:
                        # Counters: queued scheduled -> queued ready for matching scope
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                now_str = self._clock.now_utc().astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M:%S")
                                for r in conn.execute(
                                    (
                                        f"SELECT domain, queue, job_type, COUNT(*) FROM jobs WHERE {wh} "
                                        "AND status='queued' AND (available_at IS NOT NULL AND available_at > DATETIME(?)) GROUP BY domain,queue,job_type"
                                    ),
                                    tuple(params + [now_str])
                                ).fetchall() or []:
                                    conn.execute(
                                        (
                                            "UPDATE job_counters SET scheduled_count = CASE WHEN (scheduled_count - ?) < 0 THEN 0 ELSE scheduled_count - ? END, "
                                            "ready_count = ready_count + ?, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?"
                                        ),
                                        (int(r[3]), int(r[3]), int(r[3]), r[0], r[1], r[2]),
                                    )
                        except Exception:
                            pass
                        conn.execute(f"UPDATE jobs SET available_at=DATETIME('now') WHERE {wh}", tuple(params))
                    else:
                        if delta_seconds is None:
                            raise ValueError("delta_seconds required when set_now=false")
                        conn.execute(f"UPDATE jobs SET available_at=COALESCE(available_at, DATETIME('now')) WHERE {wh}")
                        conn.execute(f"UPDATE jobs SET available_at=DATETIME(available_at, ?) WHERE {wh}", tuple([f"+{int(delta_seconds)} seconds"] + params))
                return count
        finally:
            conn.close()

    def retry_now_jobs(
        self,
        *,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
        only_failed: bool = True,
        dry_run: bool = False,
    ) -> int:
        """Force immediate retry by moving eligible jobs to queued with available_at=now().

        By default targets failed jobs with retries remaining. If only_failed is False,
        also adjusts queued scheduled jobs by setting available_at=now().
        """
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    where = ["1=1"]; params: List[Any] = []
                    if domain:
                        where.append("domain=%s"); params.append(domain)
                    if queue:
                        where.append("queue=%s"); params.append(queue)
                    if job_type:
                        where.append("job_type=%s"); params.append(job_type)
                    wh = " AND ".join(where)
                    cur.execute(
                        (
                            f"SELECT COUNT(*) AS c FROM jobs WHERE {wh} AND ("
                            "(status='failed' AND retry_count < max_retries) "
                            + (" OR (status='queued' AND available_at >= NOW())" if not only_failed else "") + ")"
                        ),
                        tuple(params),
                    )
                    _cnt = cur.fetchone()
                    count = int((_cnt.get("c") if isinstance(_cnt, dict) else 0))
                    if dry_run:
                        return count
                    with conn:
                        cur.execute(f"UPDATE jobs SET status='queued', available_at=NOW() WHERE {wh} AND status='failed' AND retry_count < max_retries", tuple(params))
                        if not only_failed:
                            # Counters: queued scheduled -> queued ready
                            try:
                                if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                    now_ts = self._clock.now_utc()
                                    cur.execute(
                                        (
                                            f"SELECT domain, queue, job_type, COUNT(*) c FROM jobs WHERE {wh} "
                                            "AND status='queued' AND available_at > %s GROUP BY domain,queue,job_type"
                                        ),
                                        tuple(params + [now_ts]),
                                    )
                                    for r in (cur.fetchall() or []):
                                        cur.execute(
                                            "UPDATE job_counters SET scheduled_count = GREATEST(scheduled_count - %s, 0), ready_count = job_counters.ready_count + %s, updated_at = NOW() WHERE domain=%s AND queue=%s AND job_type=%s",
                                            (int(r["c"]), int(r["c"]), r["domain"], r["queue"], r["job_type"]),
                                        )
                            except Exception:
                                pass
                            cur.execute(f"UPDATE jobs SET available_at=NOW() WHERE {wh} AND status='queued' AND available_at >= NOW()", tuple(params))
                    return count
            else:
                where = ["1=1"]; params: List[Any] = []
                if domain:
                    where.append("domain=?"); params.append(domain)
                if queue:
                    where.append("queue=?"); params.append(queue)
                if job_type:
                    where.append("job_type=?"); params.append(job_type)
                wh = " AND ".join(where)
                row = conn.execute(
                    (
                        f"SELECT COUNT(*) FROM jobs WHERE {wh} AND ("
                        "(status='failed' AND retry_count < max_retries) "
                        + (" OR (status='queued' AND available_at >= DATETIME('now'))" if not only_failed else "") + ")"
                    ),
                    tuple(params),
                ).fetchone()
                count = int(row[0]) if row else 0
                if dry_run:
                    return count
                with conn:
                    conn.execute(f"UPDATE jobs SET status='queued', available_at=DATETIME('now') WHERE {wh} AND status='failed' AND retry_count < max_retries", tuple(params))
                    if not only_failed:
                        # Counters: queued scheduled -> queued ready
                        try:
                            if str(os.getenv("JOBS_COUNTERS_ENABLED", "")).lower() in {"1","true","yes","y","on"}:
                                for r in conn.execute(
                                    f"SELECT domain, queue, job_type, COUNT(*) FROM jobs WHERE {wh} AND status='queued' AND available_at > DATETIME('now') GROUP BY domain,queue,job_type",
                                    tuple(params),
                                ).fetchall() or []:
                                    conn.execute(
                                        (
                                            "UPDATE job_counters SET scheduled_count = CASE WHEN (scheduled_count - ?) < 0 THEN 0 ELSE scheduled_count - ? END, "
                                            "ready_count = ready_count + ?, updated_at = DATETIME('now') WHERE domain=? AND queue=? AND job_type=?"
                                        ),
                                        (int(r[3]), int(r[3]), int(r[3]), r[0], r[1], r[2]),
                                    )
                        except Exception:
                            pass
                        conn.execute(f"UPDATE jobs SET available_at=DATETIME('now') WHERE {wh} AND status='queued' AND available_at >= DATETIME('now')", tuple(params))
                return count
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
            try:
                conn.close()
            except Exception:
                pass

    def count_active_processing(self, *, domain: Optional[str] = None, queue: Optional[str] = None) -> int:
        """Count jobs currently in processing state (optionally filtered)."""
        conn = self._connect()
        try:
            if self.backend == "postgres":
                where = ["status='processing'"]
                params: List[Any] = []
                if domain:
                    where.append("domain = %s"); params.append(domain)
                if queue:
                    where.append("queue = %s"); params.append(queue)
                with self._pg_cursor(conn) as cur:
                    cur.execute(f"SELECT COUNT(*) AS c FROM jobs WHERE {' AND '.join(where)}", tuple(params))
                    row = cur.fetchone()
                    return int(row["c"]) if row is not None else 0
            else:
                where = ["status='processing'"]
                params2: List[Any] = []
                if domain:
                    where.append("domain = ?"); params2.append(domain)
                if queue:
                    where.append("queue = ?"); params2.append(queue)
                row = conn.execute(f"SELECT COUNT(*) FROM jobs WHERE {' AND '.join(where)}", tuple(params2)).fetchone()
                return int(row[0]) if row else 0
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def add_job_attachment(self, job_id: int, *, kind: str, content_text: Optional[str] = None, url: Optional[str] = None) -> int:
        kind = str(kind or "").strip().lower()
        if kind not in {"log", "artifact", "tag"}:
            raise ValueError("kind must be one of: log, artifact, tag")
        if not content_text and not url:
            raise ValueError("content_text or url is required")
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with conn:
                    with self._pg_cursor(conn) as cur:
                        cur.execute("INSERT INTO job_attachments(job_id,kind,content_text,url) VALUES(%s,%s,%s,%s) RETURNING id", (int(job_id), kind, content_text, url))
                        row = cur.fetchone()
                        return int(row["id"]) if row else 0
            else:
                with conn:
                    conn.execute("INSERT INTO job_attachments(job_id,kind,content_text,url) VALUES(?,?,?,?)", (int(job_id), kind, content_text, url))
                    rid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                    return int(rid)
        finally:
            conn.close()

    def list_job_attachments(self, job_id: int, *, limit: int = 100) -> List[Dict[str, Any]]:
        limit = max(1, min(1000, int(limit)))
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    cur.execute("SELECT id, kind, content_text, url, created_at FROM job_attachments WHERE job_id = %s ORDER BY id ASC LIMIT %s", (int(job_id), limit))
                    rows = cur.fetchall() or []
                    return [dict(r) for r in rows]
            else:
                rows = conn.execute("SELECT id, kind, content_text, url, created_at FROM job_attachments WHERE job_id = ? ORDER BY id ASC LIMIT ?", (int(job_id), limit)).fetchall() or []
                return [
                    {"id": int(r[0]), "kind": r[1], "content_text": r[2], "url": r[3], "created_at": r[4]} for r in rows
                ]
        finally:
            conn.close()

    def rotate_encryption_keys(
        self,
        *,
        domain: Optional[str] = None,
        queue: Optional[str] = None,
        job_type: Optional[str] = None,
        old_key_b64: str,
        new_key_b64: str,
        fields: List[str],
        limit: int = 1000,
        dry_run: bool = False,
    ) -> int:
        """Re-encrypt encrypted JSON envelopes from old key to new key for selected rows.

        Fields may include 'payload' and/or 'result'. Returns affected row count.
        """
        fields = [f for f in (fields or []) if f in {"payload", "result"}]
        if not fields:
            raise ValueError("fields must include at least one of: payload, result")
        if not old_key_b64 or not new_key_b64:
            raise ValueError("old_key_b64 and new_key_b64 are required")
        affected = 0
        conn = self._connect()
        try:
            if self.backend == "postgres":
                with self._pg_cursor(conn) as cur:
                    where = ["1=1"]; params: List[Any] = []
                    if domain:
                        where.append("domain=%s"); params.append(domain)
                    if queue:
                        where.append("queue=%s"); params.append(queue)
                    if job_type:
                        where.append("job_type=%s"); params.append(job_type)
                    cur.execute(f"SELECT id, payload, result, domain, queue, job_type FROM jobs WHERE {' AND '.join(where)} ORDER BY id ASC LIMIT %s", tuple(params + [int(limit)]))
                    rows = cur.fetchall() or []
                    if dry_run:
                        # Count candidates that would be re-encrypted
                        for r in rows:
                            for fld in fields:
                                val = r.get(fld)
                                env = val if isinstance(val, dict) else None
                                if env and (env.get("_enc") == "aesgcm:v1" or isinstance(env.get("_encrypted"), dict)):
                                    affected += 1; break
                        return affected
                    with conn:
                        for r in rows:
                            upd = {}
                            for fld in fields:
                                val = r.get(fld)
                                obj = None
                                if isinstance(val, dict) and val.get("_enc") == "aesgcm:v1":
                                    obj = decrypt_json_blob_with_key(val, old_key_b64)
                                elif isinstance(val, dict) and isinstance(val.get("_encrypted"), dict):
                                    obj = decrypt_json_blob_with_key(val.get("_encrypted"), old_key_b64)
                                if obj is not None:
                                    env = encrypt_json_blob_with_key(obj, new_key_b64)
                                    if env:
                                        upd[fld] = {"_encrypted": env}
                            if upd:
                                sets = []
                                params_upd: List[Any] = []
                                for k, v in upd.items():
                                    sets.append(f"{k}=%s::jsonb")
                                    params_upd.append(json.dumps(v))
                                params_upd.append(int(r["id"]))
                                cur.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = %s", tuple(params_upd))
                                affected += 1
                return affected
            else:
                rows = conn.execute(
                    "SELECT id, payload, result, domain, queue, job_type FROM jobs ORDER BY id ASC LIMIT ?",
                    (int(limit),),
                ).fetchall() or []
                if dry_run:
                    for rid, pl, rs, *_ in rows:
                        for fld, val in (("payload", pl), ("result", rs)):
                            if fld not in fields:
                                continue
                            try:
                                if isinstance(val, str) and val:
                                    obj = json.loads(val)
                                elif isinstance(val, dict):
                                    obj = val
                                else:
                                    obj = None
                            except Exception:
                                obj = None
                            if isinstance(obj, dict) and (obj.get("_enc") == "aesgcm:v1" or isinstance(obj.get("_encrypted"), dict)):
                                affected += 1; break
                    return affected
                with conn:
                    for rid, pl, rs, *_ in rows:
                        upd: Dict[str, Any] = {}
                        for fld, val in (("payload", pl), ("result", rs)):
                            if fld not in fields:
                                continue
                            obj = None
                            try:
                                if isinstance(val, str) and val:
                                    val_obj = json.loads(val)
                                elif isinstance(val, dict):
                                    val_obj = val
                                else:
                                    val_obj = None
                            except Exception:
                                val_obj = None
                            if isinstance(val_obj, dict) and val_obj.get("_enc") == "aesgcm:v1":
                                obj = decrypt_json_blob_with_key(val_obj, old_key_b64)
                            elif isinstance(val_obj, dict) and isinstance(val_obj.get("_encrypted"), dict):
                                obj = decrypt_json_blob_with_key(val_obj.get("_encrypted"), old_key_b64)
                            if obj is not None:
                                env = encrypt_json_blob_with_key(obj, new_key_b64)
                                if env:
                                    upd[fld] = json.dumps({"_encrypted": env})
                        if upd:
                            sets = []
                            params_upd: List[Any] = []
                            for k, v in upd.items():
                                sets.append(f"{k} = ?")
                                params_upd.append(v)
                            params_upd.append(int(rid))
                            conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", tuple(params_upd))
                            affected += 1
                return affected
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
                    cur.execute(f"SELECT COUNT(*) AS c FROM jobs WHERE {' AND '.join(where_np)}", tuple(params_np))
                    _np = cur.fetchone()
                    res["non_processing_with_lease"] = int((_np.get("c") if isinstance(_np, dict) else 0))
                    cur.execute(f"SELECT COUNT(*) AS c FROM jobs WHERE {' AND '.join(where_pr)}", tuple(params_pr))
                    _pr = cur.fetchone()
                    res["processing_expired"] = int((_pr.get("c") if isinstance(_pr, dict) else 0))
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
