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

    # Optional: TTL GC for idempotency
    def gc_idempotency(self) -> int:
        """Garbage-collect expired idempotency records.

        Returns the number of records deleted. Default implementation does
        nothing and returns 0; concrete backends may override.
        """
        return 0


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

    def _gc_idem(self) -> int:
        now = time.time()
        expired = [k for k, (ts, _fp, _resp, _oid) in self._idem.items() if now - ts > self.idem_ttl_sec]
        for k in expired:
            self._idem.pop(k, None)
        return len(expired)

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

    def gc_idempotency(self) -> int:
        with self._lock:
            return self._gc_idem()

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

    def _coerce_created_at(self, value: str | int | float) -> float:
        """Coerce created_at filter to epoch seconds.

        Accepts ISO-8601 strings (including trailing 'Z'), ints, or floats.
        Raises ValueError if not parseable.
        """
        txt = str(value).strip()
        if txt.endswith("Z"):
            txt = txt[:-1] + "+00:00"
        from datetime import datetime
        try:
            return datetime.fromisoformat(txt).timestamp()
        except ValueError:
            try:
                return float(txt)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid created_at filter: {value!r}")

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

    def _gc_idem(self, con: sqlite3.Connection) -> int:
        try:
            ttl = max(1, int(self.idem_ttl_sec))
        except Exception:
            ttl = 600
        cutoff = time.time() - ttl
        cur = con.execute("SELECT COUNT(*) FROM sandbox_idempotency WHERE created_at < ?", (cutoff,))
        row = cur.fetchone()
        n = int(row[0]) if row else 0
        con.execute("DELETE FROM sandbox_idempotency WHERE created_at < ?", (cutoff,))
        return n

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

    def gc_idempotency(self) -> int:
        """One-shot TTL GC for idempotency rows; returns number of deleted rows."""
        with self._lock, self._conn() as con:
            try:
                return self._gc_idem(con)
            except Exception:
                return 0

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
        if created_at_from is not None:
            where.append("created_at >= ?")
            params.append(self._coerce_created_at(created_at_from))
        if created_at_to is not None:
            where.append("created_at <= ?")
            params.append(self._coerce_created_at(created_at_to))
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
        if created_at_from is not None:
            where.append("created_at >= ?")
            params.append(self._coerce_created_at(created_at_from))
        if created_at_to is not None:
            where.append("created_at <= ?")
            params.append(self._coerce_created_at(created_at_to))
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


class PostgresStore(SandboxStore):
    """Cluster/durable store backed by Postgres.

    - Requires psycopg (v3).
    - Uses per-operation connections (no extra pooling dependency).
    - Stores datetimes as ISO-8601 TEXT for parity with SQLite paths.
    """

    def __init__(self, dsn: str, idem_ttl_sec: int = 600) -> None:
        self.idem_ttl_sec = int(idem_ttl_sec)
        self.dsn = dsn
        self._lock = threading.RLock()
        try:
            import psycopg  # noqa: F401
            from psycopg.rows import dict_row  # noqa: F401
        except Exception as e:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgresStore") from e
        self._init_db()

    def _conn(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row)

    def _init_db(self) -> None:
        with self._conn() as con:
            with con.cursor() as cur:
                cur.execute(
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
                        resource_usage JSONB
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sandbox_idempotency (
                        endpoint TEXT,
                        user_key TEXT,
                        key TEXT,
                        fingerprint TEXT,
                        object_id TEXT,
                        response_body JSONB,
                        created_at DOUBLE PRECISION,
                        PRIMARY KEY (endpoint, user_key, key)
                    );
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sandbox_usage (
                        user_id TEXT PRIMARY KEY,
                        artifact_bytes BIGINT
                    );
                    """
                )
                # Migrations: ensure new columns exist
                def _ensure_column(table: str, col: str, coltype: str) -> None:
                    try:
                        cur.execute(
                            """
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name=%s AND column_name=%s
                            """,
                            (table, col),
                        )
                        if cur.fetchone():
                            return
                        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                    except Exception:
                        logger.debug(f"Postgres migration: could not add {table}.{col}")

                _ensure_column("sandbox_runs", "resource_usage", "JSONB")
                _ensure_column("sandbox_runs", "runtime_version", "TEXT")

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

    def check_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not key:
            return None
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                # TTL GC
                try:
                    ttl = max(1, int(self.idem_ttl_sec))
                except Exception:
                    ttl = 600
                cutoff = time.time() - ttl
                try:
                    cur.execute("DELETE FROM sandbox_idempotency WHERE created_at < %s", (cutoff,))
                except Exception:
                    pass
                cur.execute(
                    """
                    SELECT fingerprint, response_body, object_id, created_at
                    FROM sandbox_idempotency
                    WHERE endpoint=%s AND user_key=%s AND key=%s
                    """,
                    (endpoint, self._user_key(user_id), key),
                )
                row = cur.fetchone()
                if not row:
                    return None
                fp_new = self._fp(body)
                if row.get("fingerprint") == fp_new:
                    try:
                        return row.get("response_body")
                    except Exception:
                        return None
                # Conflict: include created_at epoch seconds
                ct = None
                try:
                    ct = float(row.get("created_at")) if row.get("created_at") is not None else None
                except Exception:
                    ct = None
                raise IdempotencyConflict(row.get("object_id") or "", key=key, created_at=ct)

    def store_idempotency(self, endpoint: str, user_id: Any, key: Optional[str], body: Dict[str, Any], object_id: str, response: Dict[str, Any]) -> None:
        if not key:
            return
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                try:
                    cur.execute(
                        """
                        INSERT INTO sandbox_idempotency(endpoint,user_key,key,fingerprint,object_id,response_body,created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (endpoint, user_key, key) DO NOTHING
                        """,
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
                    logger.debug(f"idempotency store failed (pg): {e}")

    def put_run(self, user_id: Any, st: RunStatus) -> None:
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sandbox_runs (id,user_id,spec_version,runtime,runtime_version,base_image,phase,exit_code,started_at,finished_at,message,image_digest,policy_hash,resource_usage)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id=EXCLUDED.user_id,
                        spec_version=EXCLUDED.spec_version,
                        runtime=EXCLUDED.runtime,
                        runtime_version=EXCLUDED.runtime_version,
                        base_image=EXCLUDED.base_image,
                        phase=EXCLUDED.phase,
                        exit_code=EXCLUDED.exit_code,
                        started_at=EXCLUDED.started_at,
                        finished_at=EXCLUDED.finished_at,
                        message=EXCLUDED.message,
                        image_digest=EXCLUDED.image_digest,
                        policy_hash=EXCLUDED.policy_hash,
                        resource_usage=EXCLUDED.resource_usage
                    """,
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
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute("SELECT * FROM sandbox_runs WHERE id=%s", (run_id,))
                row = cur.fetchone()
                if not row:
                    return None
                try:
                    ru = None
                    try:
                        ru = row.get("resource_usage") if row.get("resource_usage") else None
                        if isinstance(ru, str):
                            ru = json.loads(ru)
                    except Exception:
                        ru = None
                    st = RunStatus(
                        id=row.get("id"),
                        phase=RunPhase(row.get("phase")),
                        spec_version=row.get("spec_version"),
                        runtime=(RuntimeType(row.get("runtime")) if row.get("runtime") else None),
                        runtime_version=row.get("runtime_version"),
                        base_image=row.get("base_image"),
                        image_digest=row.get("image_digest"),
                        policy_hash=row.get("policy_hash"),
                        exit_code=row.get("exit_code"),
                        started_at=(datetime.fromisoformat(row.get("started_at")) if row.get("started_at") else None),
                        finished_at=(datetime.fromisoformat(row.get("finished_at")) if row.get("finished_at") else None),
                    )
                    st.message = row.get("message")
                    st.resource_usage = ru if isinstance(ru, dict) else None
                    return st
                except Exception as e:
                    logger.debug(f"pg get_run parse error: {e}")
                    return None

    def update_run(self, st: RunStatus) -> None:
        # UPSERT via put_run
        self.put_run(None, st)

    def get_run_owner(self, run_id: str) -> Optional[str]:
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute("SELECT user_id FROM sandbox_runs WHERE id=%s", (run_id,))
                row = cur.fetchone()
                if row and (row.get("user_id") is not None):
                    return str(row.get("user_id"))
                return None

    def get_user_artifact_bytes(self, user_id: str) -> int:
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute("SELECT artifact_bytes FROM sandbox_usage WHERE user_id=%s", (user_id,))
                row = cur.fetchone()
                if not row:
                    return 0
                try:
                    return int(row.get("artifact_bytes") or 0)
                except Exception:
                    return 0

    def increment_user_artifact_bytes(self, user_id: str, delta: int) -> None:
        if not user_id:
            return
        d = int(delta or 0)
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sandbox_usage(user_id, artifact_bytes) VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET artifact_bytes = COALESCE(sandbox_usage.artifact_bytes, 0) + EXCLUDED.artifact_bytes
                    """,
                    (user_id, d),
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
            where.append("image_digest = %s")
            params.append(image_digest)
        if user_id:
            where.append("user_id = %s")
            params.append(user_id)
        if phase:
            where.append("phase = %s")
            params.append(phase)
        if started_at_from:
            where.append("started_at >= %s")
            params.append(started_at_from)
        if started_at_to:
            where.append("started_at <= %s")
            params.append(started_at_to)
        sql = (
            "SELECT id,user_id,spec_version,runtime,runtime_version,base_image,phase,exit_code,started_at,finished_at,message,image_digest,policy_hash "
            f"FROM sandbox_runs WHERE {' AND '.join(where)} ORDER BY started_at {order} LIMIT %s OFFSET %s"
        )
        params.extend([int(limit), int(offset)])
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, tuple(params))
                items: list[dict] = []
                for row in cur.fetchall() or []:
                    items.append({
                        "id": row.get("id"),
                        "user_id": row.get("user_id"),
                        "spec_version": row.get("spec_version"),
                        "runtime": row.get("runtime"),
                        "runtime_version": row.get("runtime_version"),
                        "base_image": row.get("base_image"),
                        "phase": row.get("phase"),
                        "exit_code": row.get("exit_code"),
                        "started_at": row.get("started_at"),
                        "finished_at": row.get("finished_at"),
                        "message": row.get("message"),
                        "image_digest": row.get("image_digest"),
                        "policy_hash": row.get("policy_hash"),
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
            where.append("image_digest = %s")
            params.append(image_digest)
        if user_id:
            where.append("user_id = %s")
            params.append(user_id)
        if phase:
            where.append("phase = %s")
            params.append(phase)
        if started_at_from:
            where.append("started_at >= %s")
            params.append(started_at_from)
        if started_at_to:
            where.append("started_at <= %s")
            params.append(started_at_to)
        sql = f"SELECT COUNT(*) AS c FROM sandbox_runs WHERE {' AND '.join(where)}"
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, tuple(params))
                row = cur.fetchone()
                try:
                    return int(list(row.values())[0]) if row else 0
                except Exception:
                    return 0

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
            where.append("endpoint = %s")
            params.append(endpoint)
        if user_id:
            where.append("user_key = %s")
            params.append(user_id)
        if key:
            where.append("key = %s")
            params.append(key)
        if created_at_from:
            where.append("created_at >= %s")
            params.append(self._coerce_created_at(created_at_from))
        if created_at_to:
            where.append("created_at <= %s")
            params.append(self._coerce_created_at(created_at_to))
        sql = (
            "SELECT endpoint,user_key,key,fingerprint,object_id,created_at FROM sandbox_idempotency "
            f"WHERE {' AND '.join(where)} ORDER BY created_at {order} LIMIT %s OFFSET %s"
        )
        params.extend([int(limit), int(offset)])
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, tuple(params))
                items: list[dict] = []
                for row in cur.fetchall() or []:
                    iso_ct = None
                    try:
                        if row.get("created_at") is not None:
                            iso_ct = datetime.fromtimestamp(float(row.get("created_at")), tz=timezone.utc).isoformat()
                    except Exception:
                        iso_ct = None
                    items.append({
                        "endpoint": row.get("endpoint"),
                        "user_id": row.get("user_key"),
                        "key": row.get("key"),
                        "fingerprint": row.get("fingerprint"),
                        "object_id": row.get("object_id"),
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
            where.append("endpoint = %s")
            params.append(endpoint)
        if user_id:
            where.append("user_key = %s")
            params.append(user_id)
        if key:
            where.append("key = %s")
            params.append(key)
        if created_at_from:
            where.append("created_at >= %s")
            params.append(self._coerce_created_at(created_at_from))
        if created_at_to:
            where.append("created_at <= %s")
            params.append(self._coerce_created_at(created_at_to))
        sql = f"SELECT COUNT(*) AS c FROM sandbox_idempotency WHERE {' AND '.join(where)}"
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute(sql, tuple(params))
                row = cur.fetchone()
                try:
                    return int(list(row.values())[0]) if row else 0
                except Exception:
                    return 0

    def list_usage(
        self,
        *,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        order = "DESC" if sort_desc else "ASC"
        with self._lock, self._conn() as con:
            with con.cursor() as cur:
                cur.execute("SELECT user_id, artifact_bytes FROM sandbox_usage")
                usage_rows = {r.get("user_id"): int(r.get("artifact_bytes") or 0) for r in (cur.fetchall() or [])}
                cur.execute("SELECT user_id, resource_usage FROM sandbox_runs")
                agg: dict[str, dict] = {}
                for row in cur.fetchall() or []:
                    u = row.get("user_id")
                    if not u:
                        continue
                    if user_id and u != user_id:
                        continue
                    rs = agg.setdefault(u, {"runs_count": 0, "log_bytes": 0})
                    rs["runs_count"] += 1
                    try:
                        ru = row.get("resource_usage")
                        if isinstance(ru, str):
                            ru = json.loads(ru)
                        if ru and isinstance(ru.get("log_bytes"), int):
                            rs["log_bytes"] += int(ru.get("log_bytes") or 0)
                    except Exception:
                        pass
                users = set(usage_rows.keys()) | set(agg.keys())
                items: list[dict] = []
                for u in sorted(users, reverse=bool(sort_desc)):
                    if user_id and u != user_id:
                        continue
                    items.append({
                        "user_id": u,
                        "runs_count": int((agg.get(u) or {}).get("runs_count", 0)),
                        "log_bytes": int((agg.get(u) or {}).get("log_bytes", 0)),
                        "artifact_bytes": int(usage_rows.get(u, 0)),
                    })
                return items[offset: offset + limit]

    def count_usage(
        self,
        *,
        user_id: Optional[str] = None,
    ) -> int:
        return len(self.list_usage(user_id=user_id, limit=10**9, offset=0, sort_desc=True))


def _resolve_pg_dsn() -> Optional[str]:
    # Prefer explicit SANDBOX_STORE_PG_DSN, then env, then DATABASE_URL
    try:
        dsn = getattr(app_settings, "SANDBOX_STORE_PG_DSN", None)
    except Exception:
        dsn = None
    dsn = dsn or os.getenv("SANDBOX_STORE_PG_DSN") or os.getenv("SANDBOX_PG_DSN")
    if not dsn:
        try:
            dsn = getattr(app_settings, "DATABASE_URL", None)
        except Exception:
            dsn = None
    if not dsn:
        return None
    dsn_str = str(dsn)
    # Ignore sqlite URLs for cluster mode; require a real Postgres DSN.
    if dsn_str.strip().lower().startswith("sqlite"):
        return None
    return dsn_str


def get_store() -> SandboxStore:
    backend = None
    try:
        backend = str(getattr(app_settings, "SANDBOX_STORE_BACKEND", "memory")).strip().lower()
    except Exception:
        backend = "memory"
    if backend == "memory":
        ttl = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
        return InMemoryStore(idem_ttl_sec=ttl)
    if backend == "cluster":
        ttl = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
        dsn = _resolve_pg_dsn()
        if dsn:
            try:
                return PostgresStore(dsn=dsn, idem_ttl_sec=ttl)
            except Exception as e:
                logger.warning(f"Cluster store requested but unavailable ({e}); falling back to SQLite store")
        else:
            logger.warning("Cluster store requested but SANDBOX_STORE_PG_DSN/DATABASE_URL not set; falling back to SQLite store")
    # Default sqlite
    ttl = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
    try:
        db_path = getattr(app_settings, "SANDBOX_STORE_DB_PATH", None)
    except Exception:
        db_path = None
    return SQLiteStore(db_path=db_path, idem_ttl_sec=ttl)


def get_store_mode() -> str:
    """Return the effective store mode for feature discovery.

    Values: memory | sqlite | cluster | unknown
    """
    try:
        backend = str(getattr(app_settings, "SANDBOX_STORE_BACKEND", "memory")).strip().lower()
    except Exception:
        backend = "memory"
    if backend == "cluster":
        dsn = _resolve_pg_dsn()
        try:
            import psycopg  # noqa: F401
            deps_ok = True
        except Exception:
            deps_ok = False
        if dsn and deps_ok:
            return "cluster"
        return "sqlite"
    if backend in {"memory", "sqlite"}:
        return backend
    return "unknown"
