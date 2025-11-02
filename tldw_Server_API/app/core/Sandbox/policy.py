from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List

from loguru import logger

from .models import RuntimeType, RunSpec, SessionSpec
from tldw_Server_API.app.core.config import settings as app_settings
import json
import hashlib


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


def _canonical_policy_dict(cfg: SandboxPolicyConfig) -> dict:
    """Build a canonical, stable dict capturing policy-affecting settings.

    The material intentionally avoids environment-specific paths and
    includes only values that impact sandbox behavior and security.
    """
    try:
        # Runner security toggles (booleans for determinism)
        docker_seccomp_enabled = bool(getattr(app_settings, "SANDBOX_DOCKER_SECCOMP", None))
    except Exception:
        docker_seccomp_enabled = False
    try:
        docker_apparmor_enabled = bool(getattr(app_settings, "SANDBOX_DOCKER_APPARMOR_PROFILE", None))
    except Exception:
        docker_apparmor_enabled = False
    try:
        ul_nofile = int(getattr(app_settings, "SANDBOX_ULIMIT_NOFILE", 1024))
    except Exception:
        ul_nofile = 1024
    try:
        ul_nproc = int(getattr(app_settings, "SANDBOX_ULIMIT_NPROC", 512))
    except Exception:
        ul_nproc = 512

    # Normalize supported spec versions list
    spec_versions = list(cfg.supported_spec_versions or ["1.0"])
    spec_versions = sorted(str(v) for v in spec_versions)

    material = {
        "default_runtime": cfg.default_runtime.value,
        "network_default": str(cfg.network_default),
        "artifact_ttl_hours": int(cfg.artifact_ttl_hours),
        "max_upload_mb": int(cfg.max_upload_mb),
        "max_log_bytes": int(cfg.max_log_bytes),
        "pids_limit": int(cfg.pids_limit),
        "max_cpu": float(cfg.max_cpu),
        "max_mem_mb": int(cfg.max_mem_mb),
        "workspace_cap_mb": int(cfg.workspace_cap_mb),
        "supported_spec_versions": spec_versions,
        # Runner-level security primitives
        "security": {
            "docker_seccomp": bool(docker_seccomp_enabled),
            "docker_apparmor": bool(docker_apparmor_enabled),
            "ulimit_nofile": int(ul_nofile),
            "ulimit_nproc": int(ul_nproc),
        },
    }
    return material


def compute_policy_hash(cfg: SandboxPolicyConfig) -> str:
    """Return a short, reproducible hash for the canonical policy material.

    Uses sha256 of the canonical JSON (sorted keys, compact separators) and
    returns the first 16 hex chars for brevity, as used elsewhere.
    """
    mat = _canonical_policy_dict(cfg)
    canon = json.dumps(mat, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
