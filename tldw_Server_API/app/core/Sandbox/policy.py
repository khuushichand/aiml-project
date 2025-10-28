from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from loguru import logger

from .models import RuntimeType, RunSpec, SessionSpec


@dataclass
class SandboxPolicyConfig:
    default_runtime: RuntimeType = RuntimeType.docker
    network_default: str = "deny_all"  # deny_all | allowlist (allowlist controlled elsewhere)
    artifact_ttl_hours: int = 24
    max_upload_mb: int = 64


class SandboxPolicy:
    """Evaluates and normalizes sandbox requests against admin policy.

    This v0 policy is intentionally simple and conservative: deny-all network by default,
    and prefer Docker for broad compatibility unless Firecracker is explicitly requested
    and available.
    """

    def __init__(self, cfg: Optional[SandboxPolicyConfig] = None) -> None:
        self.cfg = cfg or SandboxPolicyConfig()

    def select_runtime(self, requested: Optional[RuntimeType], firecracker_available: bool) -> RuntimeType:
        if requested:
            if requested == RuntimeType.firecracker and not firecracker_available:
                logger.info("Firecracker requested but unavailable; falling back to default runtime")
                return self.cfg.default_runtime
            return requested
        return self.cfg.default_runtime

    def apply_to_session(self, spec: SessionSpec, firecracker_available: bool) -> SessionSpec:
        spec.runtime = self.select_runtime(spec.runtime, firecracker_available)
        if not spec.network_policy:
            spec.network_policy = self.cfg.network_default
        return spec

    def apply_to_run(self, spec: RunSpec, firecracker_available: bool) -> RunSpec:
        spec.runtime = spec.runtime or self.cfg.default_runtime
        if spec.runtime == RuntimeType.firecracker and not firecracker_available:
            logger.info("Firecracker selected but unavailable; falling back to default runtime for run")
            spec.runtime = self.cfg.default_runtime
        if not spec.network_policy:
            spec.network_policy = self.cfg.network_default
        return spec

