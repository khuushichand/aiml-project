from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta
import os
from typing import List, Optional
import hashlib

from loguru import logger

from .models import (
    RunPhase,
    RunSpec,
    RunStatus,
    RuntimeType,
    Session,
    SessionSpec,
)
from .policy import SandboxPolicy, SandboxPolicyConfig, compute_policy_hash
from .store import get_store_mode
from .orchestrator import SandboxOrchestrator, IdempotencyConflict
from .runners.docker_runner import docker_available
from .runners.firecracker_runner import firecracker_available
from .runners.docker_runner import DockerRunner
from tldw_Server_API.app.core.config import settings as app_settings
import threading
import asyncio

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    UnifiedAuditService,
    AuditEventType,
    AuditEventCategory,
    AuditSeverity,
    AuditContext,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Metrics import observe_histogram
from .streams import get_hub


class SandboxService:
    """High-level orchestrator facade for sandbox operations (scaffold).

    Provides feature discovery and minimal ID generation for sessions/runs.
    Actual execution is intentionally not implemented at this stage.
    """

    def __init__(self, policy: Optional[SandboxPolicy] = None) -> None:
        cfg = SandboxPolicyConfig.from_settings()
        self.policy = policy or SandboxPolicy(cfg)
        self._orch = SandboxOrchestrator(self.policy)
        self._supported_specs = list(self.policy.cfg.supported_spec_versions or ["1.0"])

    class InvalidSpecVersion(Exception):
        def __init__(self, provided: str, supported: list[str]) -> None:
            super().__init__(f"Unsupported spec_version '{provided}'")
            self.provided = provided
            self.supported = supported

    def _validate_spec_version(self, spec_version: Optional[str]) -> None:
        if not spec_version:
            return
        if spec_version not in self._supported_specs:
            raise SandboxService.InvalidSpecVersion(spec_version, self._supported_specs)

    def feature_discovery(self) -> list[dict]:
        images = [
            "python:3.11-slim",
            "node:20-alpine",
            # generic shell base left for future: e.g., "ubuntu:24.04"
        ]
        # Defaults pulled from policy cfg (wired to env/config)
        max_cpu = self.policy.cfg.max_cpu
        max_mem_mb = self.policy.cfg.max_mem_mb
        max_upload_mb = self.policy.cfg.max_upload_mb
        max_log_bytes = self.policy.cfg.max_log_bytes
        workspace_cap_mb = self.policy.cfg.workspace_cap_mb
        artifact_ttl_hours = self.policy.cfg.artifact_ttl_hours
        supported_spec_versions = list(self.policy.cfg.supported_spec_versions or ["1.0"])
        # Queue/backpressure defaults from app settings
        try:
            queue_max_length = int(getattr(app_settings, "SANDBOX_QUEUE_MAX_LENGTH", 100))
        except Exception:
            queue_max_length = 100
        try:
            queue_ttl_sec = int(getattr(app_settings, "SANDBOX_QUEUE_TTL_SEC", 120))
        except Exception:
            queue_ttl_sec = 120
        # Store mode advertised to clients (e.g., memory|sqlite|cluster)
        try:
            store_mode = str(get_store_mode())
        except Exception:
            store_mode = "unknown"
        return [
            {
                "name": "docker",
                "available": bool(docker_available()),
                "default_images": images,
                "max_cpu": max_cpu,
                "max_mem_mb": max_mem_mb,
                "max_upload_mb": max_upload_mb,
                "max_log_bytes": max_log_bytes,
                "queue_max_length": queue_max_length,
                "queue_ttl_sec": queue_ttl_sec,
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
                "interactive_supported": False,
                "egress_allowlist_supported": False,
                "store_mode": store_mode,
                "notes": None,
            },
            {
                "name": "firecracker",
                "available": bool(firecracker_available()),
                "default_images": images,  # firecracker images will differ; placeholder for UX
                "max_cpu": max_cpu,
                "max_mem_mb": max_mem_mb,
                "max_upload_mb": max_upload_mb,
                "max_log_bytes": max_log_bytes,
                "queue_max_length": queue_max_length,
                "queue_ttl_sec": queue_ttl_sec,
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
                "interactive_supported": False,
                "egress_allowlist_supported": False,
                "store_mode": store_mode,
                "notes": "Direct integration preferred; ignite is EOL",
            },
        ]

    def _audit_run_completion(self, *, user_id: str | int | None, run_id: str, status: RunStatus, spec_version: str, session_id: str | None) -> None:
        """Log a completion audit event in a fire-and-forget manner."""
        try:
            uid_int = None
            try:
                uid_int = int(str(user_id)) if user_id is not None else None
            except Exception:
                uid_int = None
            if uid_int is not None:
                db_path = DatabasePaths.get_audit_db_path(uid_int)
            else:
                db_path = None

            async def _alog() -> None:
                svc = UnifiedAuditService(db_path=str(db_path) if db_path else None)
                await svc.initialize()
                try:
                    ctx = AuditContext(
                        user_id=(str(user_id) if user_id is not None else None),
                        session_id=session_id,
                        method="INTERNAL",
                        endpoint="/api/v1/sandbox/runs (background)",
                    )
                    outcome = (
                        "success" if status.phase in (RunPhase.completed,) and (status.exit_code or 0) == 0 else
                        "timeout" if status.phase == RunPhase.timed_out else
                        "killed" if status.phase == RunPhase.killed else
                        "failed" if status.phase == RunPhase.failed else
                        status.phase.value
                    )
                    dur_ms = None
                    try:
                        if status.started_at and status.finished_at:
                            dur_ms = max(0.0, (status.finished_at - status.started_at).total_seconds() * 1000.0)
                    except Exception:
                        dur_ms = None
                    # Include reason_code for non-success outcomes when available
                    reason_code = None
                    try:
                        if outcome in ("timeout", "failed"):
                            reason_code = (status.message or None)
                    except Exception:
                        reason_code = None
                    await svc.log_event(
                        event_type=AuditEventType.API_RESPONSE,
                        category=AuditEventCategory.API_CALL,
                        severity=(AuditSeverity.INFO if outcome == "success" else AuditSeverity.WARNING),
                        context=ctx,
                        resource_type="sandbox.run",
                        resource_id=run_id,
                        action="run",
                        result=("success" if outcome == "success" else outcome),
                        duration_ms=dur_ms,
                        metadata={
                            "runtime": status.runtime.value if status.runtime else None,
                            "base_image": status.base_image,
                            "image_digest": status.image_digest,
                            "policy_hash": status.policy_hash,
                            "exit_code": status.exit_code,
                            "spec_version": spec_version,
                            "reason_code": reason_code,
                        },
                    )
                finally:
                    await svc.stop()

            # Run now; if we're already in an event loop, schedule task
            try:
                asyncio.run(_alog())
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.create_task(_alog())
        except Exception as e:
            logger.debug(f"audit(run.completion) failed: {e}")
        # (rest of method continues)

    def create_session(self, user_id: str | int, spec: SessionSpec, spec_version: str, idem_key: Optional[str], raw_body: dict) -> Session:
        # Validate requested spec version
        self._validate_spec_version(spec_version)
        fc_ok = firecracker_available()
        spec = self.policy.apply_to_session(spec, firecracker_available=fc_ok)
        # delegate to orchestrator (with idempotency)
        sess = self._orch.create_session(user_id=user_id, spec=spec, spec_version=spec_version, idem_key=idem_key, body=raw_body)
        return sess

    def destroy_session(self, session_id: str) -> bool:
        # No stateful sessions yet; pretend success
        logger.info(f"Destroyed sandbox session {session_id} (noop scaffold)")
        return True

    def parse_inline_files(self, files: Optional[List[dict]]) -> list[tuple[str, bytes]]:
        results: list[tuple[str, bytes]] = []
        if not files:
            return results
        for f in files:
            try:
                p = str(f.get("path", ""))
                b64 = str(f.get("content_b64", ""))
                data = base64.b64decode(b64)
                results.append((p, data))
            except Exception as e:
                logger.warning(f"Failed to parse inline file: {e}")
        return results

    def start_run_scaffold(self, user_id: str | int, spec: RunSpec, spec_version: str, idem_key: Optional[str], raw_body: dict) -> RunStatus:
        # Validate requested spec version
        self._validate_spec_version(spec_version)
        # Apply policy then enqueue via orchestrator (idempotency-aware)
        fc_ok = firecracker_available()
        spec = self.policy.apply_to_run(spec, firecracker_available=fc_ok)
        status = self._orch.enqueue_run(user_id=user_id, spec=spec, spec_version=spec_version, idem_key=idem_key, body=raw_body)
        # Emit queue-wait metric as soon as we move out of queued (or immediately after enqueue)
        # so tests that disable execution still observe this metric.
        try:
            ts = self._orch.get_enqueue_time(status.id)  # type: ignore[attr-defined]
            if ts:
                import time as _time
                qwait = max(0.0, _time.time() - float(ts))
                observe_histogram("sandbox_queue_wait_seconds", value=float(qwait), labels={"runtime": str(spec.runtime.value if spec.runtime else "unknown")})
        except Exception:
            pass
        # Optional: Execute via Docker runner if enabled and requested
        # Allow per-test overrides via env even if settings were loaded earlier
        try:
            env_exec = os.getenv("SANDBOX_ENABLE_EXECUTION")
            if env_exec is not None:
                execute_enabled = str(env_exec).strip().lower() in {"1", "true", "yes", "on", "y"}
            else:
                execute_enabled = bool(getattr(app_settings, "SANDBOX_ENABLE_EXECUTION", False))
        except Exception:
            execute_enabled = False
        if execute_enabled and spec.runtime == RuntimeType.docker:
            try:
                env_bg = os.getenv("SANDBOX_BACKGROUND_EXECUTION")
                if env_bg is not None:
                    background = str(env_bg).strip().lower() in {"1", "true", "yes", "on", "y"}
                else:
                    background = bool(getattr(app_settings, "SANDBOX_BACKGROUND_EXECUTION", False))
                if background:
                    # Return early and execute in background
                    status.phase = RunPhase.starting
                    # Best-effort status update; do not abort if orchestrator lacks method
                    try:
                        self._orch.update_run(status.id, status)  # type: ignore[attr-defined]
                    except Exception as _e:
                        logger.debug(f"sandbox: update_run(starting) skipped: {_e}")
                    # Proactively publish a 'start' event so WS subscribers connecting
                    # immediately after POST observe at least one event.
                    try:
                        get_hub().publish_event(status.id, "start", {"bg": True})
                    except Exception:
                        pass
                    # Metrics: queue wait histogram (if enqueued timestamp known)
                    try:
                        ts = self._orch.get_enqueue_time(status.id)  # type: ignore[attr-defined]
                        if ts:
                            import time as _time
                            qwait = max(0.0, _time.time() - float(ts))
                            observe_histogram("sandbox_queue_wait_seconds", value=float(qwait), labels={"runtime": "docker"})
                    except Exception:
                        pass
                    def _worker():
                        try:
                            dr = DockerRunner()
                            ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                            real = dr.start_run(status.id, spec, ws)
                            real.id = status.id
                            # Merge results
                            status.phase = real.phase
                            status.exit_code = real.exit_code
                            status.started_at = real.started_at
                            status.finished_at = real.finished_at
                            status.message = real.message
                            status.image_digest = real.image_digest
                            # Attach resource usage if produced by runner
                            try:
                                if getattr(real, "resource_usage", None):
                                    status.resource_usage = real.resource_usage  # type: ignore[assignment]
                            except Exception:
                                pass
                            if real.artifacts:
                                self._orch.store_artifacts(status.id, real.artifacts)
                            try:
                                self._orch.update_run(status.id, status)  # type: ignore[attr-defined]
                            except Exception as _e:
                                logger.debug(f"sandbox: update_run(completed) skipped: {_e}")
                            # Ensure an 'end' event is published even if the runner didn't
                            try:
                                get_hub().publish_event(status.id, "end", {"exit_code": status.exit_code})
                            except Exception:
                                pass
                            # Ensure policy hash is present (compute if missing)
                            if not status.policy_hash:
                                status.policy_hash = compute_policy_hash(self.policy.cfg)
                            # Audit completion
                            self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
                        except Exception as e:
                            logger.warning(f"Background docker execution failed: {e}")
                    threading.Thread(target=_worker, daemon=True).start()
                else:
                    dr = DockerRunner()
                    ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                    # Metrics: queue wait histogram before starting execution
                    try:
                        ts = self._orch.get_enqueue_time(status.id)  # type: ignore[attr-defined]
                        if ts:
                            import time as _time
                            qwait = max(0.0, _time.time() - float(ts))
                            observe_histogram("sandbox_queue_wait_seconds", value=float(qwait), labels={"runtime": "docker"})
                    except Exception:
                        pass
                    real = dr.start_run(status.id, spec, ws)
                    real.id = status.id
                    status.phase = real.phase
                    status.exit_code = real.exit_code
                    status.started_at = real.started_at
                    status.finished_at = real.finished_at
                    status.message = real.message
                    status.image_digest = real.image_digest
                    try:
                        if getattr(real, "resource_usage", None):
                            status.resource_usage = real.resource_usage  # type: ignore[assignment]
                    except Exception:
                        pass
                    if real.artifacts:
                        self._orch.store_artifacts(status.id, real.artifacts)
                    self._orch.update_run(status.id, status)
                    # Audit completion (sync path)
                    try:
                        self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Docker execution failed; keeping enqueue status. Error: {e}")
        else:
            # Stub artifacts even without execution
            artifacts: dict[str, bytes] = {}
            for pattern in spec.capture_patterns or []:
                artifacts[pattern] = b""
            if artifacts:
                self._orch.store_artifacts(status.id, artifacts)
        # Attach canonical policy hash for metadata consistency
        try:
            status.policy_hash = compute_policy_hash(self.policy.cfg)
        except Exception:
            status.policy_hash = None  # type: ignore[assignment]
        # Timestamps in scaffold
        now = datetime.utcnow()
        if not status.started_at:
            status.started_at = now
        if not status.finished_at and status.phase in (RunPhase.completed, RunPhase.failed, RunPhase.killed, RunPhase.timed_out):
            status.finished_at = now
        if status.exit_code is None and status.phase == RunPhase.completed:
            status.exit_code = 0
        if not status.message:
            status.message = "Sandbox scaffold: execution not implemented"
        return status

    def get_run(self, run_id: str) -> Optional[RunStatus]:
        return self._orch.get_run(run_id)

    def get_session_workspace_path(self, session_id: str) -> Optional[str]:
        return self._orch.get_session_workspace_path(session_id)

    def cancel_run(self, run_id: str) -> bool:
        st = self._orch.get_run(run_id)
        if not st:
            return False
        # If already finished, no-op
        if st.phase in (RunPhase.completed, RunPhase.failed, RunPhase.killed, RunPhase.timed_out):
            return False
        cancelled = False
        try:
            if st.runtime == RuntimeType.docker:
                cancelled = DockerRunner.cancel_run(run_id)
        except Exception as e:
            logger.debug(f"cancel_run failed: {e}")
            cancelled = False
        # Update status
        try:
            st.phase = RunPhase.killed
            st.message = "canceled_by_user"
            st.finished_at = datetime.utcnow()
            st.exit_code = None
            self._orch.update_run(run_id, st)
            # Consider the operation successful if we set killed state
            cancelled = True
        except Exception:
            pass
        # Ensure WS end event is sent even if runner didn't publish
        try:
            get_hub().publish_event(run_id, "end", {"exit_code": None, "canceled": True})
        except Exception:
            pass
        return bool(cancelled)
