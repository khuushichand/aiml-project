from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from .models import RunPhase, RunSpec, RunStatus, Session, SessionSpec
from .policy import SandboxPolicy, SandboxPolicyConfig
from tldw_Server_API.app.core.config import settings as app_settings
from pathlib import Path
import os
from typing import List


class IdempotencyConflict(Exception):
    def __init__(self, original_id: str, message: str = "Idempotency conflict") -> None:
        super().__init__(message)
        self.original_id = original_id


def _fingerprint_body(body: Dict[str, Any]) -> str:
    try:
        canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    except Exception:
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
    response_body: Dict[str, Any]
    created_at: float


class SandboxOrchestrator:
    """In-memory orchestrator with idempotency and a simple run queue.

    Not production-grade; intended to be replaced by a pluggable backend.
    """

    def __init__(self, policy: Optional[SandboxPolicy] = None) -> None:
        cfg = SandboxPolicyConfig.from_settings()
        self.policy = policy or SandboxPolicy(cfg)
        self._lock = threading.RLock()
        self._sessions: Dict[str, Session] = {}
        self._runs: Dict[str, RunStatus] = {}
        self._idem: Dict[Tuple[str, str, str], _IdemRecord] = {}
        self._queue: list[str] = []  # simple in-memory run queue (run_ids)
        try:
            self._idem_ttl_sec = int(getattr(app_settings, "SANDBOX_IDEMPOTENCY_TTL_SEC", 600))
        except Exception:
            self._idem_ttl_sec = 600
        self._session_roots: Dict[str, str] = {}
        self._artifacts: Dict[str, Dict[str, bytes]] = {}
        # Owner and usage tracking for artifact caps
        self._run_owners: Dict[str, str] = {}
        self._user_artifact_bytes: Dict[str, int] = {}

    # -----------------
    # Idempotency Core
    # -----------------
    def _user_key(self, user_id: Any) -> str:
        try:
            return str(user_id)
        except Exception:
            return ""

    def _cleanup_idem(self) -> None:
        now = time.time()
        expired: list[Tuple[str, str, str]] = []
        for k, rec in self._idem.items():
            if now - rec.created_at > self._idem_ttl_sec:
                expired.append(k)
        for k in expired:
            self._idem.pop(k, None)

    def _check_idem(self, endpoint: str, user_id: Any, idem_key: Optional[str], body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return stored response if idempotent replay matches, raise if conflicts, else None."""
        if not idem_key:
            return None
        with self._lock:
            self._cleanup_idem()
            fp = _fingerprint_body(body)
            user_key = self._user_key(user_id)
            idx = (endpoint, user_key, idem_key)
            rec = self._idem.get(idx)
            if rec is None:
                # No record yet
                return None
            # TTL check already performed by cleanup
            if rec.fingerprint == fp:
                logger.debug(f"Idempotent replay matched for endpoint={endpoint} key={idem_key}")
                return rec.response_body
            logger.info(
                f"Idempotent replay conflict for endpoint={endpoint} key={idem_key}:\n"
                f"existing_fp={rec.fingerprint} new_fp={fp}"
            )
            raise IdempotencyConflict(rec.object_id, "Idempotency-Key conflict for different request body")

    def _store_idem(self, endpoint: str, user_id: Any, idem_key: Optional[str], body: Dict[str, Any], object_id: str, response: Dict[str, Any]) -> None:
        if not idem_key:
            return
        with self._lock:
            fp = _fingerprint_body(body)
            user_key = self._user_key(user_id)
            idx = (endpoint, user_key, idem_key)
            # Only store if not present (race-safe behavior)
            if idx not in self._idem:
                self._idem[idx] = _IdemRecord(
                    key=idem_key,
                    endpoint=endpoint,
                    user_key=user_key,
                    fingerprint=fp,
                    object_id=object_id,
                    response_body=response,
                    created_at=time.time(),
                )

    # -----------------
    # Sessions
    # -----------------
    def create_session(self, user_id: Any, spec: SessionSpec, spec_version: str, idem_key: Optional[str], body: Dict[str, Any]) -> Session:
        # Check idempotency storage first
        stored = self._check_idem("sessions", user_id, idem_key, body)
        if stored is not None:
            sid = stored.get("id")
            with self._lock:
                if sid and sid in self._sessions:
                    return self._sessions[sid]
            # If missing from sessions map (unlikely), synthesize from stored
            return Session(id=stored.get("id", ""), runtime=spec.runtime or self.policy.cfg.default_runtime, base_image=spec.base_image, expires_at=None)

        # Create a new session and its workspace
        sid = str(uuid.uuid4())
        sess = Session(id=sid, runtime=spec.runtime or self.policy.cfg.default_runtime, base_image=spec.base_image, expires_at=None)
        ws_dir = self._ensure_workspace(user_id, sid)
        with self._lock:
            self._sessions[sid] = sess
            # Store idempotent response body
            resp = {"id": sid, "runtime": sess.runtime.value, "base_image": sess.base_image, "expires_at": None}
            self._store_idem("sessions", user_id, idem_key, body, sid, resp)
        return sess

    # -----------------
    # Runs
    # -----------------
    def enqueue_run(self, user_id: Any, spec: RunSpec, spec_version: str, idem_key: Optional[str], body: Dict[str, Any]) -> RunStatus:
        stored = self._check_idem("runs", user_id, idem_key, body)
        if stored is not None:
            rid = stored.get("id")
            with self._lock:
                if rid and rid in self._runs:
                    return self._runs[rid]
            # Synthesize minimal status if missing
            return RunStatus(id=rid or "", phase=RunPhase.completed, spec_version=spec_version, runtime=spec.runtime, base_image=spec.base_image)

        # In this scaffold, we create a run and immediately complete it
        rid = str(uuid.uuid4())
        status = RunStatus(id=rid, phase=RunPhase.completed, spec_version=spec_version, runtime=spec.runtime, base_image=spec.base_image, exit_code=0)
        with self._lock:
            self._runs[rid] = status
            self._queue.append(rid)
            # Track run owner for artifact caps and paths
            try:
                self._run_owners[rid] = str(user_id)
            except Exception:
                self._run_owners[rid] = ""
            self._store_idem("runs", user_id, idem_key, body, rid, {
                "id": rid,
                "phase": status.phase.value,
                "spec_version": spec_version,
                "runtime": spec.runtime.value if spec.runtime else None,
                "base_image": spec.base_image,
                "exit_code": status.exit_code,
            })
        return status

    # -----------------
    # Lookups (stubs)
    # -----------------
    def get_run(self, run_id: str) -> Optional[RunStatus]:
        with self._lock:
            return self._runs.get(run_id)

    def update_run(self, run_id: str, status: RunStatus) -> None:
        with self._lock:
            self._runs[run_id] = status

    # -----------------
    # Artifacts
    # -----------------
    def _artifact_dir(self, user_id: str, run_id: str) -> Path:
        try:
            root = getattr(app_settings, "SANDBOX_ROOT_DIR", None)
        except Exception:
            root = None
        if not root:
            try:
                proj = getattr(app_settings, "PROJECT_ROOT", ".")
            except Exception:
                proj = "."
            root = Path(str(proj)) / "tmp_dir" / "sandbox"
        return Path(str(root)) / user_id / "runs" / run_id / "artifacts"

    def _safe_rel(self, p: str) -> str:
        p = p.replace("\\", "/").lstrip("/")
        # prevent path traversal
        parts: List[str] = []
        for comp in p.split('/'):
            if comp in ("", "."):
                continue
            if comp == "..":
                parts.append("_")
            else:
                parts.append(comp)
        return "/".join(parts)

    def store_artifacts(self, run_id: str, items: Dict[str, bytes]) -> None:
        # Enforce caps and persist to filesystem under run's artifacts directory
        owner = None
        with self._lock:
            owner = self._run_owners.get(run_id, "")
        owner = owner or "unknown"
        # Caps (bytes)
        try:
            cap_run = int(getattr(app_settings, "SANDBOX_MAX_ARTIFACT_BYTES_PER_RUN_MB", 32)) * 1024 * 1024
        except Exception:
            cap_run = 32 * 1024 * 1024
        try:
            cap_user = int(getattr(app_settings, "SANDBOX_MAX_ARTIFACT_BYTES_PER_USER_MB", 128)) * 1024 * 1024
        except Exception:
            cap_user = 128 * 1024 * 1024

        # Determine remaining budget
        with self._lock:
            current_user_bytes = int(self._user_artifact_bytes.get(owner, 0))

        selected: Dict[str, bytes] = {}
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
        try:
            art_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        for path, data in selected.items():
            rel = self._safe_rel(path)
            full = art_dir / rel
            try:
                full.parent.mkdir(parents=True, exist_ok=True)
                with open(full, "wb") as f:
                    f.write(data)
            except Exception as e:
                logger.debug(f"Failed to persist artifact {rel}: {e}")

        with self._lock:
            self._artifacts[run_id] = selected
            self._user_artifact_bytes[owner] = current_user_bytes

    def list_artifacts(self, run_id: str) -> Dict[str, int]:
        # Try filesystem, fallback to memory
        owner = None
        with self._lock:
            owner = self._run_owners.get(run_id, "")
        art_dir = self._artifact_dir(owner or "unknown", run_id)
        result: Dict[str, int] = {}
        if art_dir.exists():
            for root, _dirs, files in os.walk(art_dir):
                for fn in files:
                    full = Path(root) / fn
                    rel = str(full.relative_to(art_dir)).replace(os.sep, "/")
                    try:
                        result[rel] = full.stat().st_size
                    except Exception:
                        result[rel] = 0
            if result:
                return result
        with self._lock:
            mapping = self._artifacts.get(run_id) or {}
            return {k: len(v) for k, v in mapping.items()}

    def get_artifact(self, run_id: str, path: str) -> Optional[bytes]:
        owner = None
        with self._lock:
            owner = self._run_owners.get(run_id, "")
        art_dir = self._artifact_dir(owner or "unknown", run_id)
        if path:
            rel = self._safe_rel(path)
            full = art_dir / rel
            try:
                if full.exists():
                    with open(full, "rb") as f:
                        return f.read()
            except Exception:
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
        except Exception:
            root = None
        if not root:
            try:
                proj = getattr(app_settings, "PROJECT_ROOT", ".")
            except Exception:
                proj = "."
            root = Path(str(proj)) / "tmp_dir" / "sandbox"
        ws = Path(str(root)) / str(user_id) / "sessions" / session_id / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._session_roots[session_id] = str(ws)
        return str(ws)

    def get_session_workspace_path(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._session_roots.get(session_id)
