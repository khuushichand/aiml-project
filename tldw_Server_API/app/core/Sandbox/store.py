from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from .models import RunPhase, RunStatus, RuntimeType
from tldw_Server_API.app.core.config import settings as app_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class IdempotencyConflict(Exception):
    def __init__(self, original_id: str, message: str = "Idempotency conflict") -> None:
        super().__init__(message)
        self.original_id = original_id


class SandboxStore:
    """Abstract store for runs, idempotency, and usage counters."""

    def check_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def store_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any], object_id: str, response: Dict[str, Any]) -> None:
        raise NotImplementedError

    def put_run(self, user_id: Any, st: RunStatus) -> None:
        raise NotImplementedError

    def get_run(self, run_id: str) -> Optional[RunStatus]:
        raise NotImplementedError

    def update_run(self, st: RunStatus) -> None:
        raise NotImplementedError

    def get_run_owner(self, run_id: str) -> Optional[str]:
        raise NotImplementedError

    def get_user_artifact_bytes(self, user_id: str) -> int:
        return 0

    def increment_user_artifact_bytes(self, user_id: str, delta: int) -> None:
        pass

    # Admin listing APIs
    def list_runs(
        self,
        *,
        image_digest: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        started_at_from: Optional[str] = None,
        started_at_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        """Return a list of run summary rows as dicts suitable for admin list endpoints.

        Each dict contains: id, user_id, spec_version, runtime, base_image, phase,
        exit_code, started_at, finished_at, message, image_digest, policy_hash
        """
        raise NotImplementedError

    def count_runs(
        self,
        *,
        image_digest: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        started_at_from: Optional[str] = None,
        started_at_to: Optional[str] = None,
    ) -> int:
        raise NotImplementedError


class InMemoryStore(SandboxStore):
    def __init__(self, idem_ttl_sec: int = 600) -> None:
        self.idem_ttl_sec = idem_ttl_sec
        self._idem: Dict[tuple[str, str, str], tuple[float, str, Dict[str, Any], str]] = {}
        self._runs: Dict[str, RunStatus] = {}
        self._owners: Dict[str, str] = {}
        self._user_bytes: Dict[str, int] = {}
        self._lock = threading.RLock()

    def _fp(self, body: Dict[str, Any]) -> str:
        try:
            canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
        except Exception:
            canon = str(body)
        import hashlib
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def _user_key(self, user_id: Any) -> str:
        try:
            return str(user_id)
        except Exception:
            return ""

    def _gc_idem(self) -> None:
        now = time.time()
        expired = [k for k, (ts, _fp, _resp, _oid) in self._idem.items() if now - ts > self.idem_ttl_sec]
        for k in expired:
            self._idem.pop(k, None)

    def check_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        with self._lock:
            self._gc_idem()
            idx = (endpoint, self._user_key(user_id), key)
            rec = self._idem.get(idx)
            if not rec:
                return None
            ts, fp_saved, resp, obj_id = rec
            fp_new = self._fp(body)
            if fp_new == fp_saved:
                return resp
            raise IdempotencyConflict(obj_id)

    def store_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any], object_id: str, response: Dict[str, Any]) -> None:
        if not key:
            return
        with self._lock:
            idx = (endpoint, self._user_key(user_id), key)
            if idx not in self._idem:
                self._idem[idx] = (time.time(), self._fp(body), response, object_id)

    def put_run(self, user_id: Any, st: RunStatus) -> None:
        with self._lock:
            self._runs[st.id] = st
            self._owners[st.id] = self._user_key(user_id)

    def get_run(self, run_id: str) -> Optional[RunStatus]:
        with self._lock:
            return self._runs.get(run_id)

    def update_run(self, st: RunStatus) -> None:
        with self._lock:
            self._runs[st.id] = st

    def get_run_owner(self, run_id: str) -> Optional[str]:
        with self._lock:
            return self._owners.get(run_id)

    def get_user_artifact_bytes(self, user_id: str) -> int:
        with self._lock:
            return int(self._user_bytes.get(user_id, 0))

    def increment_user_artifact_bytes(self, user_id: str, delta: int) -> None:
        with self._lock:
            self._user_bytes[user_id] = int(self._user_bytes.get(user_id, 0)) + int(delta)

    def list_runs(
        self,
        *,
        image_digest: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        started_at_from: Optional[str] = None,
        started_at_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        from datetime import datetime
        with self._lock:
            rows = []
            for st in self._runs.values():
                if image_digest and (st.image_digest or None) != image_digest:
                    continue
                if user_id and self._owners.get(st.id) != user_id:
                    continue
                if phase and st.phase.value != phase:
                    continue
                sa = st.started_at
                if started_at_from:
                    try:
                        dt_from = datetime.fromisoformat(started_at_from)
                        if not (sa and sa >= dt_from):
                            continue
                    except Exception:
                        pass
                if started_at_to:
                    try:
                        dt_to = datetime.fromisoformat(started_at_to)
                        if not (sa and sa <= dt_to):
                            continue
                    except Exception:
                        pass
                rows.append({
                    "id": st.id,
                    "user_id": self._owners.get(st.id),
                    "spec_version": st.spec_version,
                    "runtime": (st.runtime.value if st.runtime else None),
                    "base_image": st.base_image,
                    "phase": st.phase.value,
                    "exit_code": st.exit_code,
                    "started_at": (st.started_at.isoformat() if st.started_at else None),
                    "finished_at": (st.finished_at.isoformat() if st.finished_at else None),
                    "message": st.message,
                    "image_digest": st.image_digest,
                    "policy_hash": st.policy_hash,
                })
        def _key(r: dict):
            return r.get("started_at") or ""
        rows.sort(key=_key, reverse=bool(sort_desc))
        return rows[offset: offset + limit]

    def count_runs(
        self,
        *,
        image_digest: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        started_at_from: Optional[str] = None,
        started_at_to: Optional[str] = None,
    ) -> int:
        return len(self.list_runs(
            image_digest=image_digest,
            user_id=user_id,
            phase=phase,
            started_at_from=started_at_from,
            started_at_to=started_at_to,
            limit=10**9,
            offset=0,
            sort_desc=True,
        ))


class SQLiteStore(SandboxStore):
    def __init__(self, db_path: Optional[str] = None, idem_ttl_sec: int = 600) -> None:
        self.idem_ttl_sec = idem_ttl_sec
        if not db_path:
            try:
                proj = getattr(app_settings, "PROJECT_ROOT", ".")
            except Exception:
                proj = "."
            db_path = str(Path(str(proj)) / "tmp_dir" / "sandbox" / "meta" / "sandbox_store.db")
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA synchronous=NORMAL;")
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self) -> None:
        """
        Initialize the SQLite database schema for sandbox storage and apply a migration to add the `resource_usage` column if it is missing.

        Creates the tables used by the store: `sandbox_runs` (run metadata, including `resource_usage`), `sandbox_idempotency` (idempotency records keyed by endpoint, user_key, and key), and `sandbox_usage` (per-user artifact byte usage). After creating tables, attempts to add the `resource_usage` column to `sandbox_runs` for backfill compatibility; ignores only the specific "column already exists" error and re-raises any other migration failure.
        """
        with self._conn() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS sandbox_runs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    spec_version TEXT,
                    runtime TEXT,
                    base_image TEXT,
                    phase TEXT,
                    exit_code INTEGER,
                    started_at TEXT,
                    finished_at TEXT,
                    message TEXT,
                    image_digest TEXT,
                    policy_hash TEXT,
                    resource_usage TEXT
                );
                CREATE TABLE IF NOT EXISTS sandbox_idempotency (
                    endpoint TEXT,
                    user_key TEXT,
                    key TEXT,
                    fingerprint TEXT,
                    object_id TEXT,
                    response_body TEXT,
                    created_at REAL,
                    PRIMARY KEY (endpoint, user_key, key)
                );
                CREATE TABLE IF NOT EXISTS sandbox_usage (
                    user_id TEXT PRIMARY KEY,
                    artifact_bytes INTEGER
                );
                """
            )
            # Backfill migrations for older schemas: add resource_usage if missing
            # Only ignore the specific case where the column already exists.
            try:
                con.execute("ALTER TABLE sandbox_runs ADD COLUMN resource_usage TEXT")
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if (
                    "duplicate" in msg
                    or "already exists" in msg
                    or "duplicate column" in msg
                ):
                    logger.debug(
                        "SQLite migration: resource_usage column already exists; skipping ALTER TABLE"
                    )
                else:
                    # Log full exception (with stack trace) and re-raise to avoid masking real issues
                    logger.exception(
                        "SQLite migration failed adding resource_usage column to sandbox_runs"
                    )
                    raise

    def _fp(self, body: Dict[str, Any]) -> str:
        """
        Compute a stable SHA-256 fingerprint for a JSON-like body.

        The function canonicalizes `body` to a deterministic JSON string (keys sorted, compact separators) and falls back to `str(body)` if serialization fails, then returns the SHA-256 hex digest of that string.

        Parameters:
            body (Dict[str, Any]): The JSON-like object to fingerprint; should be JSON-serializable when possible.

        Returns:
            str: Hexadecimal SHA-256 digest of the canonicalized representation.
        """
        try:
            canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
        except Exception:
            canon = str(body)
        import hashlib
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()

    def _user_key(self, user_id: Any) -> str:
        try:
            return str(user_id)
        except Exception:
            return ""

    def _gc_idem(self, con: sqlite3.Connection) -> None:
        try:
            ttl = max(1, int(self.idem_ttl_sec))
        except Exception:
            ttl = 600
        cutoff = time.time() - ttl
        con.execute("DELETE FROM sandbox_idempotency WHERE created_at < ?", (cutoff,))

    def check_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        with self._lock, self._conn() as con:
            self._gc_idem(con)
            cur = con.execute(
                "SELECT fingerprint, response_body, object_id FROM sandbox_idempotency WHERE endpoint=? AND user_key=? AND key=?",
                (endpoint, self._user_key(user_id), key),
            )
            row = cur.fetchone()
            if not row:
                return None
            fp_new = self._fp(body)
            if row["fingerprint"] == fp_new:
                try:
                    return json.loads(row["response_body"]) if row["response_body"] else None
                except Exception:
                    return None
            raise IdempotencyConflict(row["object_id"])

    def store_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any], object_id: str, response: Dict[str, Any]) -> None:
        if not key:
            return
        with self._lock, self._conn() as con:
            try:
                con.execute(
                    "INSERT OR IGNORE INTO sandbox_idempotency(endpoint,user_key,key,fingerprint,object_id,response_body,created_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        endpoint,
                        self._user_key(user_id),
                        key,
                        self._fp(body),
                        object_id,
                        json.dumps(response, ensure_ascii=False),
                        time.time(),
                    ),
                )
            except Exception as e:
                logger.debug(f"idempotency store failed: {e}")

    def put_run(self, user_id: Any, st: RunStatus) -> None:
        """
        Persist a RunStatus for the given user, replacing any existing record with the same run id.

        Stores the run fields (id, user_id, spec_version, runtime, base_image, phase, exit_code,
        started_at, finished_at, message, image_digest, policy_hash) into the backend. Timestamps
        are stored as ISO 8601 strings; if `resource_usage` is a dict it is serialized to JSON and stored,
        otherwise `resource_usage` is stored as null.

        Parameters:
            user_id: Identifier of the user who owns the run; converted to a canonical string for storage.
            st (RunStatus): RunStatus object to persist.
        """
        with self._lock, self._conn() as con:
            con.execute(
                "REPLACE INTO sandbox_runs(id,user_id,spec_version,runtime,base_image,phase,exit_code,started_at,finished_at,message,image_digest,policy_hash,resource_usage) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    st.id,
                    self._user_key(user_id),
                    st.spec_version,
                    (st.runtime.value if st.runtime else None),
                    st.base_image,
                    st.phase.value,
                    st.exit_code,
                    (st.started_at.isoformat() if st.started_at else None),
                    (st.finished_at.isoformat() if st.finished_at else None),
                    st.message,
                    st.image_digest,
                    st.policy_hash,
                    (json.dumps(st.resource_usage) if isinstance(st.resource_usage, dict) else None),
                ),
            )

    def get_run(self, run_id: str) -> Optional[RunStatus]:
        """
        Retrieve a RunStatus by its run identifier.

        Parses stored fields (including ISO timestamps, enum fields, and JSON-encoded `resource_usage`) and returns a populated RunStatus object.

        Returns:
            `RunStatus` for the given `run_id`, or `None` if no record exists or if stored data cannot be parsed.
        """
        with self._lock, self._conn() as con:
            cur = con.execute("SELECT * FROM sandbox_runs WHERE id=?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            try:
                ru = None
                try:
                    ru = json.loads(row["resource_usage"]) if row["resource_usage"] else None
                except Exception:
                    ru = None
                st = RunStatus(
                    id=row["id"],
                    phase=RunPhase(row["phase"]),
                    spec_version=row["spec_version"],
                    runtime=(RuntimeType(row["runtime"]) if row["runtime"] else None),
                    base_image=row["base_image"],
                    image_digest=row["image_digest"],
                    policy_hash=row["policy_hash"],
                    exit_code=row["exit_code"],
                    started_at=(datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
                    finished_at=(datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None),
                    message=row["message"],
                    resource_usage=ru,
                )
                return st
            except Exception:
                return None

    def update_run(self, st: RunStatus) -> None:
        # Use same REPLACE logic
        self.put_run(self.get_run_owner(st.id), st)  # type: ignore[arg-type]

    def get_run_owner(self, run_id: str) -> Optional[str]:
        with self._lock, self._conn() as con:
            cur = con.execute("SELECT user_id FROM sandbox_runs WHERE id=?", (run_id,))
            row = cur.fetchone()
            return (row["user_id"] if row else None)

    def get_user_artifact_bytes(self, user_id: str) -> int:
        with self._lock, self._conn() as con:
            cur = con.execute("SELECT artifact_bytes FROM sandbox_usage WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            return int(row["artifact_bytes"]) if row and row["artifact_bytes"] is not None else 0

    def increment_user_artifact_bytes(self, user_id: str, delta: int) -> None:
        with self._lock, self._conn() as con:
            cur = con.execute("SELECT artifact_bytes FROM sandbox_usage WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            cur_val = int(row["artifact_bytes"]) if row and row["artifact_bytes"] is not None else 0
            new_val = cur_val + int(delta)
            con.execute(
                "REPLACE INTO sandbox_usage(user_id, artifact_bytes) VALUES (?,?)",
                (user_id, new_val),
            )

    def list_runs(
        self,
        *,
        image_digest: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        started_at_from: Optional[str] = None,
        started_at_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        order = "DESC" if sort_desc else "ASC"
        where = ["1=1"]
        params: list[Any] = []
        if image_digest:
            where.append("image_digest = ?")
            params.append(image_digest)
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        if phase:
            where.append("phase = ?")
            params.append(phase)
        if started_at_from:
            where.append("started_at >= ?")
            params.append(started_at_from)
        if started_at_to:
            where.append("started_at <= ?")
            params.append(started_at_to)
        sql = (
            "SELECT id,user_id,spec_version,runtime,base_image,phase,exit_code,started_at,finished_at,message,image_digest,policy_hash "
            f"FROM sandbox_runs WHERE {' AND '.join(where)} ORDER BY started_at {order} LIMIT ? OFFSET ?"
        )
        params.extend([int(limit), int(offset)])
        with self._lock, self._conn() as con:
            cur = con.execute(sql, tuple(params))
            items: list[dict] = []
            for row in cur.fetchall():
                items.append({
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "spec_version": row["spec_version"],
                    "runtime": row["runtime"],
                    "base_image": row["base_image"],
                    "phase": row["phase"],
                    "exit_code": row["exit_code"],
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "message": row["message"],
                    "image_digest": row["image_digest"],
                    "policy_hash": row["policy_hash"],
                })
            return items

    def count_runs(
        self,
        *,
        image_digest: Optional[str] = None,
        user_id: Optional[str] = None,
        phase: Optional[str] = None,
        started_at_from: Optional[str] = None,
        started_at_to: Optional[str] = None,
    ) -> int:
        where = ["1=1"]
        params: list[Any] = []
        if image_digest:
            where.append("image_digest = ?")
            params.append(image_digest)
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        if phase:
            where.append("phase = ?")
            params.append(phase)
        if started_at_from:
            where.append("started_at >= ?")
            params.append(started_at_from)
        if started_at_to:
            where.append("started_at <= ?")
            params.append(started_at_to)
        sql = f"SELECT COUNT(*) AS c FROM sandbox_runs WHERE {' AND '.join(where)}"
        with self._lock, self._conn() as con:
            cur = con.execute(sql, tuple(params))
            row = cur.fetchone()
            return int(row[0]) if row else 0


def get_store() -> SandboxStore:
    backend = None
    try:
        backend = str(getattr(app_settings, "SANDBOX_STORE_BACKEND", "memory")).strip().lower()
    except Exception:
        backend = "memory"
    if backend == "memory":
        ttl = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
        return InMemoryStore(idem_ttl_sec=ttl)
    # Default sqlite
    ttl = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
    try:
        db_path = getattr(app_settings, "SANDBOX_STORE_DB_PATH", None)
    except Exception:
        db_path = None
    return SQLiteStore(db_path=db_path, idem_ttl_sec=ttl)


def get_store_mode() -> str:
    """Return the configured store mode string for feature discovery.

    Values: memory | sqlite | cluster (future) | unknown
    """
    try:
        backend = str(getattr(app_settings, "SANDBOX_STORE_BACKEND", "memory")).strip().lower()
    except Exception:
        backend = "memory"
    if backend in {"memory", "sqlite", "cluster"}:
        return backend
    return "unknown"
