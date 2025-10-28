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
