from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta
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
from .policy import SandboxPolicy, SandboxPolicyConfig
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


class SandboxService:
    """High-level orchestrator facade for sandbox operations (scaffold).

    Provides feature discovery and minimal ID generation for sessions/runs.
    Actual execution is intentionally not implemented at this stage.
    """

    def __init__(self, policy: Optional[SandboxPolicy] = None) -> None:
        cfg = SandboxPolicyConfig.from_settings()
        self.policy = policy or SandboxPolicy(cfg)
        self._orch = SandboxOrchestrator(self.policy)

    def feature_discovery(self) -> list[dict]:
        images = [
            "python:3.11-slim",
            "node:20-alpine",
            # generic shell base left for future: e.g., "ubuntu:24.04"
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
        # Defaults pulled from policy cfg (wired to env/config)
        max_cpu = self.policy.cfg.max_cpu
        max_mem_mb = self.policy.cfg.max_mem_mb
        max_upload_mb = self.policy.cfg.max_upload_mb
        max_log_bytes = self.policy.cfg.max_log_bytes
        workspace_cap_mb = self.policy.cfg.workspace_cap_mb
        artifact_ttl_hours = self.policy.cfg.artifact_ttl_hours
        supported_spec_versions = list(self.policy.cfg.supported_spec_versions or ["1.0"])
        return [
            {
                "name": "docker",
                "available": bool(docker_available()),
                "default_images": images,
                "max_cpu": max_cpu,
                "max_mem_mb": max_mem_mb,
                "max_upload_mb": max_upload_mb,
                "max_log_bytes": max_log_bytes,
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
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
                "workspace_cap_mb": workspace_cap_mb,
                "artifact_ttl_hours": artifact_ttl_hours,
                "supported_spec_versions": supported_spec_versions,
                "notes": "Direct integration preferred; ignite is EOL",
            },
        ]

    def create_session(self, user_id: str | int, spec: SessionSpec, spec_version: str, idem_key: Optional[str], raw_body: dict) -> Session:
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
        # Apply policy then enqueue via orchestrator (idempotency-aware)
        fc_ok = firecracker_available()
        spec = self.policy.apply_to_run(spec, firecracker_available=fc_ok)
        status = self._orch.enqueue_run(user_id=user_id, spec=spec, spec_version=spec_version, idem_key=idem_key, body=raw_body)
        # Optional: Execute via Docker runner if enabled and requested
        try:
            execute_enabled = bool(getattr(app_settings, "SANDBOX_ENABLE_EXECUTION", False))
        except Exception:
            execute_enabled = False
        if execute_enabled and spec.runtime == RuntimeType.docker:
            try:
                background = bool(getattr(app_settings, "SANDBOX_BACKGROUND_EXECUTION", False))
                if background:
                    # Return early and execute in background
                    status.phase = RunPhase.starting
                    self._orch.update_run(status.id, status)
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
                            if real.artifacts:
                                self._orch.store_artifacts(status.id, real.artifacts)
                            self._orch.update_run(status.id, status)
                            # Ensure policy hash is present (compute if missing)
                            if not status.policy_hash:
                                policy_material = f"{self.policy.cfg.default_runtime}|{self.policy.cfg.network_default}|{self.policy.cfg.artifact_ttl_hours}|{self.policy.cfg.max_upload_mb}"
                                status.policy_hash = hashlib.sha256(policy_material.encode()).hexdigest()[:16]
                            # Audit completion
                            self._audit_run_completion(user_id=user_id, run_id=status.id, status=status, spec_version=spec_version, session_id=spec.session_id)
                        except Exception as e:
                            logger.warning(f"Background docker execution failed: {e}")
                    threading.Thread(target=_worker, daemon=True).start()
                else:
                    dr = DockerRunner()
                    ws = self._orch.get_session_workspace_path(spec.session_id) if spec.session_id else None
                    real = dr.start_run(status.id, spec, ws)
                    real.id = status.id
                    status.phase = real.phase
                    status.exit_code = real.exit_code
                    status.started_at = real.started_at
                    status.finished_at = real.finished_at
                    status.message = real.message
                    status.image_digest = real.image_digest
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
        # Attach a pseudo policy hash for metadata consistency
        policy_material = f"{self.policy.cfg.default_runtime}|{self.policy.cfg.network_default}|{self.policy.cfg.artifact_ttl_hours}|{self.policy.cfg.max_upload_mb}"
        ph = hashlib.sha256(policy_material.encode()).hexdigest()[:16]
        status.policy_hash = ph
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
