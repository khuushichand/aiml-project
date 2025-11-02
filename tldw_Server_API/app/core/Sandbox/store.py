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
    def __init__(self, original_id: str, key: Optional[str] = None, created_at: Optional[float] = None, message: str = "Idempotency conflict") -> None:
        super().__init__(message)
        self.original_id = original_id
        self.key = key
        # created_at is expressed as epoch seconds (float) at the store layer
        self.created_at = created_at


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

    # Admin: Idempotency listing
    def list_idempotency(
        self,
        *,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        raise NotImplementedError

    def count_idempotency(
        self,
        *,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
    ) -> int:
        raise NotImplementedError

    # Admin: Usage aggregates per user
    def list_usage(
        self,
        *,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        raise NotImplementedError

    def count_usage(
        self,
        *,
        user_id: Optional[str] = None,
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
            # include key and created_at (epoch seconds) for richer error details upstream
            raise IdempotencyConflict(obj_id, key=key, created_at=ts)

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
                    "runtime_version": getattr(st, "runtime_version", None),
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

    def list_idempotency(
        self,
        *,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        with self._lock:
            rows = []
            for (ep, uid, k), (ts, fp, resp, oid) in self._idem.items():
                if endpoint and ep != endpoint:
                    continue
                if user_id and uid != user_id:
                    continue
                if key and k != key:
                    continue
                if created_at_from:
                    try:
                        from datetime import datetime
                        dt_from = datetime.fromisoformat(created_at_from)
                        if ts < dt_from.timestamp():
                            continue
                    except Exception:
                        pass
                if created_at_to:
                    try:
                        from datetime import datetime
                        dt_to = datetime.fromisoformat(created_at_to)
                        if ts > dt_to.timestamp():
                            continue
                    except Exception:
                        pass
                from datetime import datetime, timezone
                rows.append({
                    "endpoint": ep,
                    "user_id": uid,
                    "key": k,
                    "fingerprint": fp,
                    "object_id": oid,
                    "created_at": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                })
        rows.sort(key=lambda r: r.get("created_at") or "", reverse=bool(sort_desc))
        return rows[offset: offset + limit]

    def count_idempotency(
        self,
        *,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
    ) -> int:
        return len(self.list_idempotency(
            endpoint=endpoint,
            user_id=user_id,
            key=key,
            created_at_from=created_at_from,
            created_at_to=created_at_to,
            limit=10**9,
            offset=0,
            sort_desc=True,
        ))

    def list_usage(
        self,
        *,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        # Aggregate runs_count and log_bytes from runs; artifact_bytes from _user_bytes
        with self._lock:
            users = set(self._owners.values())
            if user_id:
                users = {u for u in users if u == user_id}
            items: list[dict] = []
            for uid in sorted(users):
                runs = [r for r_id, r in self._runs.items() if self._owners.get(r_id) == uid]
                runs_count = len(runs)
                log_bytes = 0
                for st in runs:
                    try:
                        if st.resource_usage and isinstance(st.resource_usage.get("log_bytes"), int):
                            log_bytes += int(st.resource_usage.get("log_bytes") or 0)
                    except Exception:
                        continue
                art_bytes = int(self._user_bytes.get(uid, 0))
                items.append({
                    "user_id": uid,
                    "runs_count": int(runs_count),
                    "log_bytes": int(log_bytes),
                    "artifact_bytes": int(art_bytes),
                })
        items.sort(key=lambda r: r.get("user_id") or "", reverse=bool(sort_desc))
        return items[offset: offset + limit]

    def count_usage(
        self,
        *,
        user_id: Optional[str] = None,
    ) -> int:
        return len(self.list_usage(user_id=user_id, limit=10**9, offset=0, sort_desc=True))


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
                    runtime_version TEXT,
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
            # Migration: add runtime_version if missing
            try:
                con.execute("ALTER TABLE sandbox_runs ADD COLUMN runtime_version TEXT")
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if (
                    "duplicate" in msg
                    or "already exists" in msg
                    or "duplicate column" in msg
                ):
                    logger.debug(
                        "SQLite migration: runtime_version column already exists; skipping ALTER TABLE"
                    )
                else:
                    logger.exception(
                        "SQLite migration failed adding runtime_version column to sandbox_runs"
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
                "SELECT fingerprint, response_body, object_id, created_at FROM sandbox_idempotency WHERE endpoint=? AND user_key=? AND key=?",
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
            # include key and created_at (epoch seconds) from the row for richer error details upstream
            try:
                ct = float(row["created_at"]) if row["created_at"] is not None else None
            except Exception:
                ct = None
            raise IdempotencyConflict(row["object_id"], key=key, created_at=ct)

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
                "REPLACE INTO sandbox_runs(id,user_id,spec_version,runtime,runtime_version,base_image,phase,exit_code,started_at,finished_at,message,image_digest,policy_hash,resource_usage) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    st.id,
                    self._user_key(user_id),
                    st.spec_version,
                    (st.runtime.value if st.runtime else None),
                    (st.runtime_version if getattr(st, "runtime_version", None) else None),
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
                runtime_version=(row["runtime_version"] if "runtime_version" in row.keys() else None),
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
            "SELECT id,user_id,spec_version,runtime,runtime_version,base_image,phase,exit_code,started_at,finished_at,message,image_digest,policy_hash "
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
                    "runtime_version": row["runtime_version"],
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

    def list_idempotency(
        self,
        *,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        order = "DESC" if sort_desc else "ASC"
        where = ["1=1"]
        params: list[Any] = []
        if endpoint:
            where.append("endpoint = ?")
            params.append(endpoint)
        if user_id:
            where.append("user_key = ?")
            params.append(user_id)
        if key:
            where.append("key = ?")
            params.append(key)
        if created_at_from:
            where.append("created_at >= ?")
            # if provided ISO, parse to epoch seconds; else assume float
            try:
                from datetime import datetime
                params.append(datetime.fromisoformat(created_at_from).timestamp())
            except Exception:
                params.append(float(created_at_from))
        if created_at_to:
            where.append("created_at <= ?")
            try:
                from datetime import datetime
                params.append(datetime.fromisoformat(created_at_to).timestamp())
            except Exception:
                params.append(float(created_at_to))
        sql = (
            "SELECT endpoint,user_key,key,fingerprint,object_id,created_at FROM sandbox_idempotency "
            f"WHERE {' AND '.join(where)} ORDER BY created_at {order} LIMIT ? OFFSET ?"
        )
        params.extend([int(limit), int(offset)])
        items: list[dict] = []
        with self._lock, self._conn() as con:
            cur = con.execute(sql, tuple(params))
            for row in cur.fetchall():
                try:
                    from datetime import datetime, timezone
                    iso_ct = datetime.fromtimestamp(float(row["created_at"]), tz=timezone.utc).isoformat()
                except Exception:
                    iso_ct = None
                items.append({
                    "endpoint": row["endpoint"],
                    "user_id": row["user_key"],
                    "key": row["key"],
                    "fingerprint": row["fingerprint"],
                    "object_id": row["object_id"],
                    "created_at": iso_ct,
                })
        return items

    def count_idempotency(
        self,
        *,
        endpoint: Optional[str] = None,
        user_id: Optional[str] = None,
        key: Optional[str] = None,
        created_at_from: Optional[str] = None,
        created_at_to: Optional[str] = None,
    ) -> int:
        where = ["1=1"]
        params: list[Any] = []
        if endpoint:
            where.append("endpoint = ?")
            params.append(endpoint)
        if user_id:
            where.append("user_key = ?")
            params.append(user_id)
        if key:
            where.append("key = ?")
            params.append(key)
        if created_at_from:
            where.append("created_at >= ?")
            try:
                from datetime import datetime
                params.append(datetime.fromisoformat(created_at_from).timestamp())
            except Exception:
                params.append(float(created_at_from))
        if created_at_to:
            where.append("created_at <= ?")
            try:
                from datetime import datetime
                params.append(datetime.fromisoformat(created_at_to).timestamp())
            except Exception:
                params.append(float(created_at_to))
        sql = f"SELECT COUNT(*) FROM sandbox_idempotency WHERE {' AND '.join(where)}"
        with self._lock, self._conn() as con:
            cur = con.execute(sql, tuple(params))
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def list_usage(
        self,
        *,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        # Aggregate in Python to avoid JSON1 dependence
        with self._lock, self._conn() as con:
            # Gather artifact bytes per user
            art: dict[str, int] = {}
            cur = con.execute("SELECT user_id, artifact_bytes FROM sandbox_usage")
            for row in cur.fetchall():
                u = row["user_id"]
                if user_id and u != user_id:
                    continue
                art[u] = int(row["artifact_bytes"]) if row["artifact_bytes"] is not None else 0
            # Gather runs and log_bytes from runs table
            cur2 = con.execute("SELECT user_id, resource_usage FROM sandbox_runs")
            agg: dict[str, dict] = {}
            for row in cur2.fetchall():
                u = row["user_id"]
                if not u:
                    continue
                if user_id and u != user_id:
                    continue
                rs = agg.setdefault(u, {"runs_count": 0, "log_bytes": 0})
                rs["runs_count"] += 1
                try:
                    import json as _json
                    ru = _json.loads(row["resource_usage"]) if row["resource_usage"] else None
                    if ru and isinstance(ru.get("log_bytes"), int):
                        rs["log_bytes"] += int(ru.get("log_bytes") or 0)
                except Exception:
                    pass
            # Build items
            users = set(art.keys()) | set(agg.keys())
            items: list[dict] = []
            for u in users:
                items.append({
                    "user_id": u,
                    "runs_count": int((agg.get(u) or {}).get("runs_count", 0)),
                    "log_bytes": int((agg.get(u) or {}).get("log_bytes", 0)),
                    "artifact_bytes": int(art.get(u, 0)),
                })
        items.sort(key=lambda r: r.get("user_id") or "", reverse=bool(sort_desc))
        return items[offset: offset + limit]

    def count_usage(
        self,
        *,
        user_id: Optional[str] = None,
    ) -> int:
        return len(self.list_usage(user_id=user_id, limit=10**9, offset=0, sort_desc=True))


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
