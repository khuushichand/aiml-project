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
from .runners.docker_runner import docker_available
from .runners.firecracker_runner import firecracker_available


class SandboxService:
    """High-level orchestrator facade for sandbox operations (scaffold).

    Provides feature discovery and minimal ID generation for sessions/runs.
    Actual execution is intentionally not implemented at this stage.
    """

    def __init__(self, policy: Optional[SandboxPolicy] = None) -> None:
        self.policy = policy or SandboxPolicy(SandboxPolicyConfig())

    def feature_discovery(self) -> list[dict]:
        images = [
            "python:3.11-slim",
            "node:20-alpine",
            # generic shell base left for future: e.g., "ubuntu:24.04"
        ]
        # Defaults (can be wired to config later)
        max_cpu = 4.0
        max_mem_mb = 8192
        max_upload_mb = self.policy.cfg.max_upload_mb
        max_log_bytes = 10 * 1024 * 1024
        workspace_cap_mb = 256
        artifact_ttl_hours = self.policy.cfg.artifact_ttl_hours
        supported_spec_versions = ["1.0"]
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

    def create_session(self, spec: SessionSpec) -> Session:
        fc_ok = firecracker_available()
        spec = self.policy.apply_to_session(spec, firecracker_available=fc_ok)
        sid = str(uuid.uuid4())
        expires = datetime.utcnow() + timedelta(hours=1)
        logger.info(f"Created sandbox session {sid} runtime={spec.runtime}")
        return Session(id=sid, runtime=spec.runtime, base_image=spec.base_image, expires_at=expires)

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

    def start_run_scaffold(self, spec: RunSpec) -> RunStatus:
        # This is a scaffold: return an immediate completed status for wiring tests
        fc_ok = firecracker_available()
        spec = self.policy.apply_to_run(spec, firecracker_available=fc_ok)
        rid = str(uuid.uuid4())
        now = datetime.utcnow()
        logger.info(
            f"Accepted sandbox run {rid} runtime={spec.runtime} base_image={spec.base_image} cmd={spec.command} (scaffold)"
        )
        # Fake a policy hash for reproducibility metadata
        policy_material = f"{self.policy.cfg.default_runtime}|{self.policy.cfg.network_default}|{self.policy.cfg.artifact_ttl_hours}|{self.policy.cfg.max_upload_mb}"
        policy_hash = hashlib.sha256(policy_material.encode()).hexdigest()[:16]
        return RunStatus(
            id=rid,
            spec_version="1.0",
            runtime=spec.runtime,
            base_image=spec.base_image,
            image_digest=None,
            policy_hash=policy_hash,
            phase=RunPhase.completed,
            exit_code=0,
            started_at=now,
            finished_at=now,
            message="Sandbox scaffold: execution not implemented",
            resource_usage=None,
        )
