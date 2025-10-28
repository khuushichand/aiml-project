from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from loguru import logger

from .models import RuntimeType, RunSpec, SessionSpec
from tldw_Server_API.app.core.config import settings as app_settings


@dataclass
class SandboxPolicyConfig:
    default_runtime: RuntimeType = RuntimeType.docker
    network_default: str = "deny_all"  # deny_all | allowlist (allowlist controlled elsewhere)
    artifact_ttl_hours: int = 24
    max_upload_mb: int = 64
    max_log_bytes: int = 10 * 1024 * 1024
    pids_limit: int = 256
    max_cpu: float = 4.0
    max_mem_mb: int = 8192
    workspace_cap_mb: int = 256
    supported_spec_versions: List[str] = field(default_factory=lambda: ["1.0"])

    @classmethod
    def from_settings(cls) -> "SandboxPolicyConfig":
        try:
            rt_raw = str(getattr(app_settings, "SANDBOX_DEFAULT_RUNTIME", "docker")).strip().lower()
        except Exception:
            rt_raw = "docker"
        runtime = RuntimeType.firecracker if rt_raw == "firecracker" else RuntimeType.docker
        try:
            network_default = str(getattr(app_settings, "SANDBOX_NETWORK_DEFAULT", "deny_all")).strip().lower()
        except Exception:
            network_default = "deny_all"
        def _get_int(key: str, dv: int) -> int:
            try:
                return int(getattr(app_settings, key))  # type: ignore[arg-type]
            except Exception:
                return dv
        def _get_float(key: str, dv: float) -> float:
            try:
                return float(getattr(app_settings, key))  # type: ignore[arg-type]
            except Exception:
                return dv
        def _get_list(key: str, dv: List[str]) -> List[str]:
            try:
                v = getattr(app_settings, key)
                if isinstance(v, list):
                    return [str(x) for x in v]
                s = str(v)
                return [t.strip() for t in s.split(',') if t.strip()]
            except Exception:
                return dv
        return cls(
            default_runtime=runtime,
            network_default=network_default,
            artifact_ttl_hours=_get_int("SANDBOX_ARTIFACT_TTL_HOURS", 24),
            max_upload_mb=_get_int("SANDBOX_MAX_UPLOAD_MB", 64),
            max_log_bytes=_get_int("SANDBOX_MAX_LOG_BYTES", 10 * 1024 * 1024),
            pids_limit=_get_int("SANDBOX_PIDS_LIMIT", 256),
            max_cpu=_get_float("SANDBOX_MAX_CPU", 4.0),
            max_mem_mb=_get_int("SANDBOX_MAX_MEM_MB", 8192),
            workspace_cap_mb=_get_int("SANDBOX_WORKSPACE_CAP_MB", 256),
            supported_spec_versions=_get_list("SANDBOX_SUPPORTED_SPEC_VERSIONS", ["1.0"]),
        )


class SandboxPolicy:
    """Evaluates and normalizes sandbox requests against admin policy.

    This v0 policy is intentionally simple and conservative: deny-all network by default,
    and prefer Docker for broad compatibility unless Firecracker is explicitly requested
    and available.
    """

    def __init__(self, cfg: Optional[SandboxPolicyConfig] = None) -> None:
        self.cfg = cfg or SandboxPolicyConfig.from_settings()

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
