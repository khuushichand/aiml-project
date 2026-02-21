from __future__ import annotations

import contextlib
import json
import os
import shutil
import stat
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.core.testing import is_truthy

from .models import RunPhase, RunSpec, RunStatus, Session, SessionSpec
from .policy import SandboxPolicy, SandboxPolicyConfig
from .store import IdempotencyConflict as StoreIdemConflict
from .store import get_store

_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS = (
    AssertionError,
    AttributeError,
    ConnectionError,
    FileNotFoundError,
    ImportError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    PermissionError,
    RuntimeError,
    TimeoutError,
    TypeError,
    ValueError,
    UnicodeDecodeError,
    json.JSONDecodeError,
)

_OWNER_ONLY_DIR_MODE = stat.S_IRWXU


class IdempotencyConflict(Exception):
    def __init__(self, original_id: str, key: str | None = None, prior_created_at: str | None = None, message: str = "Idempotency conflict") -> None:
        super().__init__(message)
        self.original_id = original_id
        self.key = key
        # ISO 8601 timestamp string (UTC) preferred at orchestrator/api layers
        self.prior_created_at = prior_created_at


def _fingerprint_body(body: dict[str, Any]) -> str:
    try:
        canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
        # Fallback: string-ify unsafely
        canon = str(body)
    import hashlib

    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


@dataclass
class _IdemRecord:
    key: str
    endpoint: str
    user_key: str
    fingerprint: str
    object_id: str
    response_body: dict[str, Any]
    created_at: float


class SandboxOrchestrator:
    """In-memory orchestrator with idempotency and a simple run queue.

    Not production-grade; intended to be replaced by a pluggable backend.
    """

    def __init__(self, policy: SandboxPolicy | None = None) -> None:
        cfg = SandboxPolicyConfig.from_settings()
        self.policy = policy or SandboxPolicy(cfg)
        self._lock = threading.RLock()
        self._sessions: dict[str, Session] = {}
        self._session_owners: dict[str, str] = {}
        # Store backend for runs/idempotency/usage
        self._store = get_store()
        # in-memory run queue of (run_id, enqueue_timestamp)
        self._queue: list[tuple[str, float]] = []
        self._enqueue_index: dict[str, float] = {}
        try:
            self._idem_ttl_sec = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            self._idem_ttl_sec = 600
        # Queue policy
        try:
            import os as _os
            self._queue_max = int(_os.getenv("SANDBOX_QUEUE_MAX_LENGTH") or getattr(app_settings, "SANDBOX_QUEUE_MAX_LENGTH", 100))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            self._queue_max = 100
        try:
            import os as _os
            self._queue_ttl = int(_os.getenv("SANDBOX_QUEUE_TTL_SEC") or getattr(app_settings, "SANDBOX_QUEUE_TTL_SEC", 120))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            self._queue_ttl = 120
        self._session_roots: dict[str, str] = {}
        self._artifacts: dict[str, dict[str, bytes]] = {}

    # -----------------
    # Idempotency Core
    # -----------------
    def _user_key(self, user_id: Any) -> str:
        try:
            return str(user_id)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            return ""



    def _check_idem(self, endpoint: str, user_id: Any, idem_key: str | None, body: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self._store.check_idempotency(endpoint, user_id, idem_key, body)
        except StoreIdemConflict as e:
            # Convert store-level epoch seconds into ISO 8601 for API surfaces
            iso_ct: str | None = None
            try:
                if getattr(e, "created_at", None) is not None:
                    from datetime import datetime, timezone
                    iso_ct = datetime.fromtimestamp(float(e.created_at), tz=timezone.utc).isoformat()
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                iso_ct = None
            raise IdempotencyConflict(e.original_id, key=getattr(e, "key", None), prior_created_at=iso_ct) from e

    def _store_idem(self, endpoint: str, user_id: Any, idem_key: str | None, body: dict[str, Any], object_id: str, response: dict[str, Any]) -> None:
        self._store.store_idempotency(endpoint, user_id, idem_key, body, object_id, response)

    # -----------------
    # Sessions
    # -----------------
    def create_session(self, user_id: Any, spec: SessionSpec, spec_version: str, idem_key: str | None, body: dict[str, Any]) -> Session:
        # Check idempotency storage first
        stored = self._check_idem("sessions", user_id, idem_key, body)
        if stored is not None:
            sid = stored.get("id")
            with self._lock:
                if sid and sid in self._sessions:
                    return self._sessions[sid]
                if sid:
                    with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
                        self._session_owners.setdefault(sid, self._user_key(user_id))
            if sid:
                with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
                    self._ensure_workspace(user_id, sid)
            # If missing from sessions map (unlikely), synthesize from stored
            return Session(id=stored.get("id", ""), runtime=spec.runtime or self.policy.cfg.default_runtime, base_image=spec.base_image, expires_at=None)

        # Create a new session (workspace optional in scaffold)
        sid = str(uuid.uuid4())
        expires_at: datetime | None = None
        try:
            ttl_sec = int(getattr(app_settings, "SANDBOX_SESSION_TTL_SEC", 0))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            ttl_sec = 0
        if ttl_sec and ttl_sec > 0:
            expires_at = datetime.utcnow() + timedelta(seconds=int(ttl_sec))
        sess = Session(id=sid, runtime=spec.runtime or self.policy.cfg.default_runtime, base_image=spec.base_image, expires_at=expires_at)
        with self._lock:
            self._sessions[sid] = sess
            with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
                self._session_owners[sid] = self._user_key(user_id)
            # Store idempotent response body
            resp = {"id": sid, "runtime": sess.runtime.value, "base_image": sess.base_image, "expires_at": (sess.expires_at.isoformat() if sess.expires_at else None)}
            self._store_idem("sessions", user_id, idem_key, body, sid, resp)
        with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
            self._ensure_workspace(user_id, sid)
        return sess

    # -----------------
    # Runs
    # -----------------
    def enqueue_run(self, user_id: Any, spec: RunSpec, spec_version: str, idem_key: str | None, body: dict[str, Any]) -> RunStatus:
        # Check idempotency
        stored = self._check_idem("runs", user_id, idem_key, body)
        if stored is not None:
            rid = stored.get("id", "")
            # Return stored status if available
            try:
                st = self._store.get_run(rid)
                if st:
                    return st
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                pass
            # Otherwise synthesize minimal queued status
            return RunStatus(id=rid, phase=RunPhase.queued, spec_version=spec_version, runtime=spec.runtime, base_image=spec.base_image)

        # Enforce queue capacity: prune TTL then check max length
        self._prune_queue_ttl()
        with self._lock:
            # Read effective queue capacity at call time to honor per-test env overrides
            try:
                import os as _os
                effective_queue_max = int(_os.getenv("SANDBOX_QUEUE_MAX_LENGTH") or getattr(app_settings, "SANDBOX_QUEUE_MAX_LENGTH", 100))
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                effective_queue_max = 100
            # If max length is <= 0, treat as no capacity (force backpressure)
            if effective_queue_max <= 0 or len(self._queue) >= effective_queue_max:
                raise QueueFull(retry_after=max(1, int(getattr(app_settings, "SANDBOX_QUEUE_TTL_SEC", 120))))

        # Create new run in queued state
        rid = str(uuid.uuid4())
        status = RunStatus(id=rid, phase=RunPhase.queued, spec_version=spec_version, runtime=spec.runtime, base_image=spec.base_image)
        # Optional: estimated start time based on queue length and a per-run estimate
        try:
            from datetime import datetime, timedelta
            per_run = int(getattr(app_settings, "SANDBOX_QUEUE_ESTIMATED_WAIT_PER_RUN_SEC", 5))
            with self._lock:
                q_len = len(self._queue)
            status.estimated_start_time = datetime.utcnow() + timedelta(seconds=max(0, q_len) * max(0, per_run))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            pass

        # Enqueue and persist
        with self._lock:
            ts = time.time()
            self._queue.append((rid, ts))
            self._enqueue_index[rid] = ts
        try:
            self._store.put_run(user_id, status)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"store.put_run failed: {e}")
        self._store_idem("runs", user_id, idem_key, body, rid, {
            "id": rid,
            "phase": status.phase.value,
            "spec_version": spec_version,
            "runtime": spec.runtime.value if spec.runtime else None,
            "base_image": spec.base_image,
            "exit_code": status.exit_code,
        })
        return status

    def _prune_queue_ttl(self) -> None:
        """Drop queued runs older than TTL and mark them expired."""
        try:
            ttl = max(1, int(self._queue_ttl))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            ttl = 120
        now = time.time()
        expired: list[str] = []
        with self._lock:
            kept: list[tuple[str, float]] = []
            for rid, ts in self._queue:
                if now - ts > ttl:
                    expired.append(rid)
                else:
                    kept.append((rid, ts))
            self._queue = kept
            for rid in expired:
                with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
                    self._enqueue_index.pop(rid, None)
        if not expired:
            return
        from datetime import datetime
        for rid in expired:
            try:
                st = self._store.get_run(rid)
                if st and st.phase == RunPhase.queued:
                    st.phase = RunPhase.failed
                    st.message = "queue_ttl_expired"
                    st.finished_at = datetime.utcnow()
                    self._store.update_run(st)
                    # Metrics: TTL expiry, include runtime label if available
                    try:
                        from tldw_Server_API.app.core.Metrics import increment_counter as _inc
                        rt_label = None
                        try:
                            rt_label = st.runtime.value if getattr(st, "runtime", None) else None
                        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                            rt_label = None
                        labels = {"component": "sandbox", "reason": "queue_ttl_expired"}
                        if rt_label:
                            labels["runtime"] = rt_label
                        _inc("sandbox_queue_ttl_expired_total", labels=labels)
                    except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                        pass
                    try:
                        from .streams import get_hub
                        get_hub().publish_event(rid, "end", {"exit_code": None, "reason": "queue_ttl_expired"})
                    except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                        pass
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                continue

    def get_enqueue_time(self, run_id: str) -> float | None:
        with self._lock:
            return self._enqueue_index.get(run_id)

    # -----------------
    # Lookups (stubs)
    # -----------------
    def get_run(self, run_id: str) -> RunStatus | None:
        try:
            return self._store.get_run(run_id)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"store.get_run failed: {e}")
            return None

    def update_run(self, run_id: str, status: RunStatus) -> None:
        try:
            self._store.update_run(status)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"store.update_run failed: {e}")
        # Cleanup enqueue index when leaving queued phase
        try:
            if status.phase != RunPhase.queued:
                with self._lock:
                    self._enqueue_index.pop(run_id, None)
                    if self._queue:
                        self._queue = [(rid, ts) for (rid, ts) in self._queue if rid != run_id]
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            pass

    def get_run_owner(self, run_id: str) -> str | None:
        try:
            return self._store.get_run_owner(run_id)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"store.get_run_owner failed: {e}")
            return None

    def get_session_owner(self, session_id: str) -> str | None:
        with self._lock:
            return self._session_owners.get(session_id)

    def _prune_expired_sessions(self) -> None:
        now = datetime.utcnow()
        expired: list[str] = []
        with self._lock:
            for sid, sess in list(self._sessions.items()):
                if sess.expires_at and sess.expires_at <= now:
                    expired.append(sid)
        for sid in expired:
            try:
                self.destroy_session(sid)
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                continue

    def destroy_session(self, session_id: str) -> bool:
        ws_path = None
        removed = False
        with self._lock:
            if session_id in self._sessions:
                self._sessions.pop(session_id, None)
                removed = True
            ws_path = self._session_roots.pop(session_id, None)
            self._session_owners.pop(session_id, None)
        if ws_path:
            with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
                shutil.rmtree(ws_path, ignore_errors=True)
        return removed

    # -----------------
    # Artifacts
    # -----------------
    def _artifact_dir(self, user_id: str, run_id: str) -> Path:
        # Prefer an explicit shared artifacts root for cluster deployments
        root = os.getenv("SANDBOX_SHARED_ARTIFACTS_DIR")
        if not root:
            try:
                root = getattr(app_settings, "SANDBOX_ROOT_DIR", None)
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                root = None
        if not root:
            try:
                proj = getattr(app_settings, "PROJECT_ROOT", ".")
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                proj = "."
            root = Path(str(proj)) / "tmp_dir" / "sandbox"
        return Path(str(root)) / user_id / "runs" / run_id / "artifacts"

    def _safe_rel(self, p: str) -> str:
        p = p.replace("\\", "/").lstrip("/")
        # prevent path traversal
        parts: list[str] = []
        for comp in p.split('/'):
            if comp in ("", "."):
                continue
            if comp == "..":
                parts.append("_")
            else:
                parts.append(comp)
        return "/".join(parts)

    def store_artifacts(self, run_id: str, items: dict[str, bytes]) -> None:
        # Enforce caps and persist to filesystem under run's artifacts directory
        owner = None
        try:
            owner = self._store.get_run_owner(run_id)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            owner = None
        owner = owner or "unknown"
        # Caps (bytes)
        try:
            cap_run = int(getattr(app_settings, "SANDBOX_MAX_ARTIFACT_BYTES_PER_RUN_MB", 32)) * 1024 * 1024
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            cap_run = 32 * 1024 * 1024
        try:
            cap_user = int(getattr(app_settings, "SANDBOX_MAX_ARTIFACT_BYTES_PER_USER_MB", 128)) * 1024 * 1024
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            cap_user = 128 * 1024 * 1024

        # Determine remaining budget
        try:
            current_user_bytes = int(self._store.get_user_artifact_bytes(owner))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            current_user_bytes = 0

        selected: dict[str, bytes] = {}
        total_run = 0
        # Deterministic order
        for path in sorted(items.keys()):
            data = items[path]
            sz = len(data)
            if total_run + sz > cap_run:
                break
            if current_user_bytes + sz > cap_user:
                break
            selected[path] = data
            total_run += sz
            current_user_bytes += sz

        # Persist selected to FS and memory map for backward compatibility
        art_dir = self._artifact_dir(owner, run_id)
        with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
            art_dir.mkdir(parents=True, exist_ok=True)
        for path, data in selected.items():
            rel = self._safe_rel(path)
            full = art_dir / rel
            try:
                full.parent.mkdir(parents=True, exist_ok=True)
                with open(full, "wb") as f:
                    f.write(data)
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
                logger.debug(f"Failed to persist artifact {rel}: {e}")

        with self._lock:
            self._artifacts[run_id] = selected
        with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
            self._store.increment_user_artifact_bytes(owner, int(total_run))

    def list_artifacts(self, run_id: str) -> dict[str, int]:
        # Try filesystem, fallback to memory
        owner = None
        try:
            owner = self._store.get_run_owner(run_id)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            owner = None
        art_dir = self._artifact_dir((owner or "unknown"), run_id)
        result: dict[str, int] = {}
        if art_dir.exists():
            for root, _dirs, files in os.walk(art_dir):
                for fn in files:
                    full = Path(root) / fn
                    rel = str(full.relative_to(art_dir)).replace(os.sep, "/")
                    try:
                        result[rel] = full.stat().st_size
                    except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                        result[rel] = 0
            if result:
                return result
        with self._lock:
            mapping = self._artifacts.get(run_id) or {}
            return {k: len(v) for k, v in mapping.items()}

    def get_artifact(self, run_id: str, path: str) -> bytes | None:
        owner = None
        try:
            owner = self._store.get_run_owner(run_id)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            owner = None
        art_dir = self._artifact_dir((owner or "unknown"), run_id)
        if path:
            rel = self._safe_rel(path)
            full = art_dir / rel
            try:
                if full.exists():
                    with open(full, "rb") as f:
                        return f.read()
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                pass
        with self._lock:
            mapping = self._artifacts.get(run_id) or {}
            return mapping.get(path)

    # -----------------
    # Workspaces
    # -----------------
    def _ensure_workspace(self, user_id: Any, session_id: str) -> str:
        try:
            root = getattr(app_settings, "SANDBOX_ROOT_DIR", None)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            root = None
        if not root:
            try:
                proj = getattr(app_settings, "PROJECT_ROOT", ".")
            except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
                proj = "."
            root = Path(str(proj)) / "tmp_dir" / "sandbox"
        ws = Path(str(root)) / str(user_id) / "sessions" / session_id / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        try:
            bind_workspace = is_truthy(
                str(
                    os.getenv("SANDBOX_DOCKER_BIND_WORKSPACE")
                    or getattr(app_settings, "SANDBOX_DOCKER_BIND_WORKSPACE", "")
                ).strip().lower()
            )
            if bind_workspace:
                os.chmod(ws, _OWNER_ONLY_DIR_MODE)
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS:
            pass
        with self._lock:
            self._session_roots[session_id] = str(ws)
        return str(ws)

    def get_session_workspace_path(self, session_id: str) -> str | None:
        with contextlib.suppress(_SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS):
            self._prune_expired_sessions()
        with self._lock:
            return self._session_roots.get(session_id)

    # -----------------
    # Admin listing helpers
    # -----------------
    def list_runs(
        self,
        *,
        image_digest: str | None = None,
        user_id: str | None = None,
        phase: str | None = None,
        started_at_from: str | None = None,
        started_at_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
        sort_desc: bool = True,
    ) -> list[dict]:
        try:
            return self._store.list_runs(
                image_digest=image_digest,
                user_id=user_id,
                phase=phase,
                started_at_from=started_at_from,
                started_at_to=started_at_to,
                limit=limit,
                offset=offset,
                sort_desc=sort_desc,
            )
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"store.list_runs failed: {e}")
            return []

    def count_runs(
        self,
        *,
        image_digest: str | None = None,
        user_id: str | None = None,
        phase: str | None = None,
        started_at_from: str | None = None,
        started_at_to: str | None = None,
    ) -> int:
        try:
            return int(self._store.count_runs(
                image_digest=image_digest,
                user_id=user_id,
                phase=phase,
                started_at_from=started_at_from,
                started_at_to=started_at_to,
            ))
        except _SANDBOX_ORCH_NONCRITICAL_EXCEPTIONS as e:
            logger.debug(f"store.count_runs failed: {e}")
            return 0


class QueueFull(Exception):
    def __init__(self, retry_after: int = 30) -> None:
        super().__init__("queue_full")
        self.retry_after = int(retry_after)
